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
from core.dependencies import get_async_client
from db.models.transaction import Transaction, TransactionStatus
from exceptions import (
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
                app_settings.CRYPTO_SERVICE_API,
                f"/wallets/{crypto_type}/{blockchain_id}/p2p/{balance_url}",
            ),
        )
        response.raise_for_status()

        response_data = Decimal(response.text)

        return response_data < amount

    async def _increase_seller_wallet_balance(
        self, amount: Decimal, blockchain_id: str, crypto_type: str, sell_type: str
    ) -> None:
        balance_increase_url: str = "increaseToSell" if sell_type == "sell" else "increaseToBuy"

        response = await self._async_client.get(
            urljoin(
                app_settings.CRYPTO_SERVICE_API,
                f"/wallets/p2p/{balance_increase_url}",
            ),
            params={"wallet_id": blockchain_id, "amount": amount, "currencyType": crypto_type},
        )
        response.raise_for_status()

    async def _reduce_seller_wallet_balance(
        self, amount: Decimal, blockchain_id: str, crypto_type: str, sell_type: str
    ) -> None:
        balance_increase_url: str = "reduceToSell" if sell_type == "sell" else "reduceToBuy"

        response = await self._async_client.get(
            urljoin(
                app_settings.CRYPTO_SERVICE_API,
                f"/wallets/p2p/{balance_increase_url}",
            ),
            params={"wallet_id": blockchain_id, "amount": amount, "currencyType": crypto_type},
        )

        response.raise_for_status()

    async def create_transaction(
        self, db: AsyncSession, *, obj_in: TransactionCreate, active_user_wallet: tuple[str, str]
    ) -> Transaction:
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
            args=(str(transaction.id),), eta=(datetime.datetime.now() + datetime.timedelta(minutes=app_settings.TRANSACTION_EXPIRE_TIME))
        )
        return await crud.transactions.update(db=db, db_obj=transaction, obj_in=transaction_obj)

    async def _create_sell_transaction(
        self, db: AsyncSession, *, obj_in: TransactionCreate, buyer_wallet: tuple[str, str]
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
        obj_in_data["initiator"] = buyer_wallet[1]

        # if not self._is_balance_enough(obj_in.amount, seller_wallet[0], obj_in.crypto_type, 'sell'):
        #     raise APIException(detail="Not enough balance for trade")

        transaction = await crud.transactions.create_transaction(db=db, transaction_data=obj_in_data)
        # TODO transaction atomic
        # await self._reduce_seller_wallet_balance(
        #     amount=obj_in.amount,
        #     blockchain_id=buyer_wallet[0],
        #     crypto_type=obj_in.crypto_type,
        #     sell_type="sell",
        # )

        return transaction

    async def _create_buy_transaction(
        self, db: AsyncSession, *, obj_in: TransactionCreate, seller_wallet: tuple[str, str]
    ) -> Transaction:
        obj_in_data = jsonable_encoder(obj_in)
        obj_in_data["buyer_wallet"] = obj_in_data["seller_wallet"]
        obj_in_data["seller_wallet"] = seller_wallet[1]
        obj_in_data["initiator"] = obj_in_data["seller_wallet"]

        # if not self._is_balance_enough(obj_in.amount, buyer_wallet[0], obj_in.crypto_type, 'buy'):
        #     raise APIException(detail="Not enough balance for trade")

        transaction = await crud.transactions.create_transaction(db=db, transaction_data=obj_in_data)

        # await self._reduce_seller_wallet_balance(
        #     amount=obj_in.amount,
        #     blockchain_id=seller_wallet[0],
        #     crypto_type=obj_in.crypto_type,
        #     sell_type="buy",
        # )

        return transaction

    def _get_new_initiator(self, transaction: Transaction) -> str:
        if transaction.initiator == transaction.seller_wallet:
            return transaction.buyer_wallet

        return transaction.seller_wallet

    async def _transfer_on_success(
        self, wallet_id: str, transaction: Transaction, crypto_type: str
    ) -> tuple[str, datetime.datetime]:
        response = await self._async_client.get(
            urljoin(
                app_settings.CRYPTO_SERVICE_API,
                f"/transfer/{crypto_type}/from_p2p",
            ),
            params={"walletId": wallet_id, "recipient": transaction.buyer_wallet, "amount": transaction.amount},
        )
        response.raise_for_status()

        response_data = response.json()

        return response_data["hash"], datetime.datetime.strptime(response_data["time"], "")

    async def approve_trade_payment(
        self, db: AsyncSession, trade_id: UUID, current_user_wallet: tuple[str, str]
    ) -> Transaction:
        transaction = await crud.transactions.get(db, trade_id)

        if transaction.status == TransactionStatus.EXPIRED:
            raise TransactionPaymentTimeExpired()

        if transaction.initiator != current_user_wallet[1]:
            raise TransactionInitiatorException()

        if transaction.status not in [TransactionStatus.ON_PAYMENT_WAIT, TransactionStatus.ON_APPROVE]:
            raise TransactionStatusPermitted()

        new_initiator = self._get_new_initiator(transaction)
        hash = None
        closed_on = None

        if transaction.status.next == TransactionStatus.SUCCESS:
            hash, closed_on = self._transfer_on_success(
                current_user_wallet[0], transaction, transaction.crypto_type
            )

        transaction_obj = TransactionUpdate(
            status=transaction.status.next, initiator=new_initiator, hash=hash, closed_on=closed_on
        )

        return await crud.transactions.update(db=db, db_obj=transaction, obj_in=transaction_obj)

    async def cancel_transaction(
        self, db: AsyncSession, trade_id: UUID, current_user_wallet: tuple[str, str]
    ) -> Transaction:
        transaction = await crud.transactions.get(db, trade_id)

        if transaction.status not in [TransactionStatus.ON_PAYMENT_WAIT, TransactionStatus.CREATED]:
            raise TransactionStatusPermitted()

        if transaction.initiator != current_user_wallet[1]:
            raise TransactionInitiatorException()

        hash = None
        closed_on = datetime.datetime.now()

        transaction_obj = TransactionUpdate(status=TransactionStatus.CANCELED, hash=hash, closed_on=closed_on)

        return await crud.transactions.update(db=db, db_obj=transaction, obj_in=transaction_obj)