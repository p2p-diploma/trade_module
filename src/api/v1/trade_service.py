import datetime
from decimal import Decimal
from urllib.parse import urljoin
from uuid import UUID

import httpx
from fastapi import Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

import crud
from core.celery_app import set_transaction_expire_timer
from core.config import app_settings
from core.dependencies import get_async_client, send_transaction_status_notification
from core.logger_config import service_logger
from db.models.transaction import CryptoType, Transaction, TransactionStatus
from exceptions import (
    AccessDenied,
    APIException,
    NotFound,
    TradeForYourselfException,
    TransactionInitiatorException,
    TransactionPaymentTimeExpired,
    TransactionStatusPermitted,
)
from schemas import TransactionCreate
from schemas.transaction import SellType, TransactionUpdate


class TradeService:
    def __init__(
        self,
        request: Request,
        async_client: httpx.AsyncClient = Depends(get_async_client),
    ):
        self.request = request
        self._async_client = async_client

    async def _is_balance_enough(
        self, amount: Decimal, blockchain_id: str, crypto_type: str, sell_type: str
    ) -> bool:
        balance_url: str = "amountToSell" if sell_type == "sell" else "amountToBuy"

        response = await self._async_client.get(
            urljoin(
                app_settings.WALLET_SERVICE_API,
                f"/api/v1/wallets/{crypto_type}/{blockchain_id}/p2p/{balance_url}",
            ),
        )

        service_logger.info(
            f"Is balance enough for {blockchain_id} status code: {response.status_code}; Text: {response.text}"
        )

        response.raise_for_status()

        response_data = Decimal(response.text)

        return response_data >= amount

    async def _get_seller_id(self, seller_email: str) -> str:
        response = await self._async_client.get(
            urljoin(
                app_settings.WALLET_SERVICE_API,
                f"/api/v1/wallets/eth/email/{seller_email}/p2p",
            ),
        )

        service_logger.info(f"Get Seller ID status code: {response.status_code}; Text: {response.text}")

        response.raise_for_status()

        response_data = response.json()

        return response_data["id"]

    async def _increase_seller_wallet_balance(
        self, amount: Decimal, blockchain_id: str, crypto_type: str, sell_type: str
    ) -> None:
        balance_increase_url: str = "increaseToSell" if sell_type == "sell" else "increaseToBuy"

        response = await self._async_client.put(
            urljoin(
                app_settings.WALLET_SERVICE_API,
                f"/api/v1/wallets/{crypto_type}/p2p/{balance_increase_url}",
            ),
            json={"walletId": blockchain_id, "amount": float(amount)},  # type: ignore
            headers={"Content-Type": "application/json"},
        )

        service_logger.info(
            f"Increase seller wallet balance status code: {response.status_code}; Text: {response.text}"
        )

        response.raise_for_status()

    async def _reduce_seller_wallet_balance(
        self, amount: Decimal, blockchain_id: str, crypto_type: str, sell_type: str
    ) -> None:
        balance_reduce_url: str = "reduceToSell" if sell_type == "sell" else "reduceToBuy"

        response = await self._async_client.put(
            urljoin(app_settings.WALLET_SERVICE_API, f"/api/v1/wallets/{crypto_type}/p2p/{balance_reduce_url}"),
            json={"walletId": blockchain_id, "amount": float(amount)},  # type: ignore
            headers={"Content-Type": "application/json"},
        )

        service_logger.info(
            f"Reduce seller wallet balance status code: {response.status_code}; Text: {response.text}"
        )

        response.raise_for_status()

    async def create_transaction(
        self, db: AsyncSession, *, obj_in: TransactionCreate, active_user_wallet: tuple[str, str, str]
    ) -> Transaction:
        if obj_in.seller_email == active_user_wallet[2] or obj_in.seller_wallet == active_user_wallet[1]:
            raise TradeForYourselfException()

        if obj_in.sell_type == SellType.SELL:
            transaction = await self._create_sell_transaction(
                db, obj_in=obj_in, buyer_wallet=active_user_wallet
            )
        else:
            transaction = await self._create_buy_transaction(
                db, obj_in=obj_in, seller_wallet=active_user_wallet
            )

        transaction_obj = TransactionUpdate(status=TransactionStatus.ON_PAYMENT_WAIT)
        set_transaction_expire_timer.apply_async(
            args=(str(transaction.id),),
            eta=(datetime.datetime.now() + datetime.timedelta(minutes=app_settings.TRANSACTION_EXPIRE_TIME)),
        )

        transaction = await crud.transactions.update(db=db, db_obj=transaction, obj_in=transaction_obj)

        await send_transaction_status_notification(transaction)

        return transaction

    async def _create_sell_transaction(
        self, db: AsyncSession, *, obj_in: TransactionCreate, buyer_wallet: tuple[str, str, str]
    ) -> Transaction:
        """
        Creates a Transaction for a sell from a sell lot.
        :param db: Database Session instance
        :param obj_in: Transaction Scheme
        :param buyer_wallet: The wallet address of a buyer client
        :return: Transaction object
        """
        obj_in_data = jsonable_encoder(obj_in)

        obj_in_data["buyer_wallet"] = buyer_wallet[1]
        obj_in_data["buyer_email"] = buyer_wallet[2]

        obj_in_data["initiator"] = buyer_wallet[2]

        seller_wallet_id = await self._get_seller_id(obj_in.seller_email)

        if not await self._is_balance_enough(obj_in.amount, seller_wallet_id, obj_in.crypto_type.value, "sell"):
            raise APIException(detail="Not enough balance for trade")

        transaction = await crud.transactions.create_transaction(db=db, transaction_data=obj_in_data)
        await self._reduce_seller_wallet_balance(
            amount=obj_in.amount,
            blockchain_id=seller_wallet_id,
            crypto_type=obj_in.crypto_type.value,
            sell_type="sell",
        )
        service_logger.info("Created transaction successfully")
        return transaction

    async def _create_buy_transaction(
        self, db: AsyncSession, *, obj_in: TransactionCreate, seller_wallet: tuple[str, str, str]
    ) -> Transaction:
        obj_in_data = jsonable_encoder(obj_in)
        obj_in_data["buyer_wallet"] = obj_in_data["seller_wallet"]
        obj_in_data["buyer_email"] = obj_in_data["seller_email"]

        obj_in_data["seller_wallet"] = seller_wallet[1]
        obj_in_data["seller_email"] = seller_wallet[2]

        obj_in_data["initiator"] = obj_in_data["buyer_email"]

        if not await self._is_balance_enough(obj_in.amount, seller_wallet[0], obj_in.crypto_type.value, "buy"):
            raise APIException(detail="Not enough balance for trade")

        transaction = await crud.transactions.create_transaction(db=db, transaction_data=obj_in_data)

        await self._reduce_seller_wallet_balance(
            amount=obj_in.amount,
            blockchain_id=seller_wallet[0],
            crypto_type=obj_in.crypto_type.value,
            sell_type="buy",
        )

        return transaction

    def _get_new_initiator(self, transaction: Transaction) -> str:
        if transaction.initiator == transaction.seller_wallet:
            return transaction.buyer_email

        return transaction.seller_email

    async def _transfer_on_success(
        self, wallet_id: str, transaction: Transaction, crypto_type: CryptoType
    ) -> tuple[str, datetime.datetime]:
        recipient_wallet_id = await self._get_seller_id(transaction.buyer_email)
        response = await self._async_client.post(
            urljoin(
                app_settings.CRYPTO_SERVICE_API,
                f"/api/v1/{crypto_type.value}/transfer/from_p2p",
            ),
            json={
                "walletId": wallet_id,
                "recipientId": recipient_wallet_id,
                "amount": float(transaction.amount),  # type: ignore
            },
        )
        response.raise_for_status()

        response_data = response.json()
        # 2022-06-04T20:54:19
        return response_data["transactionHash"], datetime.datetime.strptime(
            response_data["transactionDate"].split(".")[0], "%Y-%m-%dT%H:%M:%S"
        )

    async def approve_trade_payment(
        self, db: AsyncSession, trade_id: UUID, current_user_wallet: tuple[str, str, str]
    ) -> Transaction:
        transaction = await crud.transactions.get(db, trade_id)

        if transaction is None:
            raise NotFound()

        if transaction.status == TransactionStatus.EXPIRED:
            raise TransactionPaymentTimeExpired()

        if transaction.initiator != current_user_wallet[2]:
            raise TransactionInitiatorException()

        if transaction.status not in [TransactionStatus.ON_PAYMENT_WAIT, TransactionStatus.ON_APPROVE]:
            raise TransactionStatusPermitted()

        new_initiator = self._get_new_initiator(transaction)
        hash = None
        closed_on = None

        if transaction.status.next == TransactionStatus.SUCCESS:
            hash, closed_on = await self._transfer_on_success(
                current_user_wallet[0], transaction, transaction.crypto_type
            )

        transaction_obj = TransactionUpdate(
            status=transaction.status.next, initiator=new_initiator, hash=hash, closed_on=closed_on
        )

        transaction = await crud.transactions.update(db=db, db_obj=transaction, obj_in=transaction_obj)

        await send_transaction_status_notification(transaction)

        return transaction

    async def cancel_transaction(
        self, db: AsyncSession, trade_id: UUID, current_user_wallet: tuple[str, str, str]
    ) -> Transaction:
        transaction = await crud.transactions.get(db, trade_id)

        if transaction is None:
            raise NotFound()

        if transaction.status not in [TransactionStatus.ON_PAYMENT_WAIT, TransactionStatus.CREATED]:
            raise TransactionStatusPermitted()

        if transaction.buyer_email != current_user_wallet[2]:
            raise TransactionInitiatorException()

        hash = None
        closed_on = datetime.datetime.now()

        transaction_obj = TransactionUpdate(status=TransactionStatus.CANCELED, hash=hash, closed_on=closed_on)

        transaction = await crud.transactions.update(db=db, db_obj=transaction, obj_in=transaction_obj)

        seller_wallet_id = await self._get_seller_id(transaction.seller_email)

        await self._increase_seller_wallet_balance(
            amount=transaction.amount,
            blockchain_id=seller_wallet_id,
            crypto_type=transaction.crypto_type.value,
            sell_type=transaction.sell_type.value,
        )

        return transaction

    async def get_transactions(self, db: AsyncSession, email: str, role: str, offset: int) -> list[Transaction]:
        match role:
            case "U":
                transactions = await crud.transactions.get_multi_by_email(db, email=email, offset=offset)
            case "A" | "SU":
                transactions = await crud.transactions.get_multi(db, skip=offset)
            case _:
                return []

        return transactions

    async def get_certain_transaction(
        self, db: AsyncSession, transaction_id: UUID, email: str, role: str
    ) -> Transaction:
        transaction = await crud.transactions.get(db, id=transaction_id)

        if transaction is None:
            raise NotFound()

        if (
            role == "U"
            and (transaction.buyer_email != email and transaction.seller_email != email)
            and role not in ["A", "SU"]
        ):
            raise AccessDenied()

        return transaction
