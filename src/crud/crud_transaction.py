from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from db.models import Transaction
from db.models.transaction import CryptoType
from schemas.transaction import TransactionCreate, TransactionUpdate


class CRUDTransaction(CRUDBase[Transaction, TransactionCreate, TransactionUpdate]):
    async def create_transaction(self, db: AsyncSession, *, transaction_data: dict) -> Transaction:
        transaction_data["crypto_type"] = (
            CryptoType.ETH if transaction_data["crypto_type"] == "eth" else CryptoType.ERC20
        )
        transaction_data.pop("sell_type")

        db_obj = self.model(**transaction_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


transactions = CRUDTransaction(Transaction)
