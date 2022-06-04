from decimal import ROUND_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from db.models import Transaction
from db.models.transaction import CryptoType, FiatType, SellType
from schemas.transaction import TransactionCreate, TransactionUpdate


class CRUDTransaction(CRUDBase[Transaction, TransactionCreate, TransactionUpdate]):
    async def create_transaction(self, db: AsyncSession, *, transaction_data: dict[str, Any]) -> Transaction:
        transaction_data["fiat_type"] = FiatType(transaction_data["fiat_type"])
        transaction_data["crypto_type"] = CryptoType(transaction_data["crypto_type"])
        transaction_data["sell_type"] = SellType(transaction_data["sell_type"])

        transaction_data["fiat_amount"] = Decimal(transaction_data["amount"]).quantize(
            Decimal(".0001"), rounding=ROUND_UP
        ) * Decimal(transaction_data.pop("price")).quantize(Decimal(".0001"), rounding=ROUND_UP).quantize(
            Decimal(".0001"), rounding=ROUND_UP
        )

        db_obj = self.model(**transaction_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_multi_by_email(
        self, db: AsyncSession, *, email: str, offset: int = 0, limit: int = 100
    ) -> list[Transaction]:
        query = (
            select(self.model)
            .filter((self.model.buyer_email == email) | (self.model.seller_email == email))
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(query)
        res = result.scalars().all()
        return res


transactions = CRUDTransaction(Transaction)
