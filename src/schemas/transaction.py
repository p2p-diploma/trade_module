import datetime
import enum
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, validator
from pydantic.schema import UUID

from db.models.transaction import CryptoType, TransactionStatus


class SellType(enum.Enum):
    SELL = "sell"
    BUY = "buy"


class TransactionBase(BaseModel):
    seller_wallet: Optional[str] = None
    buyer_wallet: Optional[str] = None
    amount: Optional[Decimal]
    status: TransactionStatus = TransactionStatus.CREATED
    crypto_type: CryptoType = CryptoType.ETH
    created_at: datetime.datetime = datetime.datetime.now()
    closed_on: Optional[datetime.datetime]
    hash: Optional[str]


class TransactionCreate(BaseModel):
    seller_wallet: str
    seller_email: EmailStr
    amount: Decimal
    crypto_type: str
    sell_type: SellType


class TransactionUpdate(BaseModel):
    status: TransactionStatus
    initiator: Optional[str]
    closed_on: Optional[datetime.datetime]
    hash: Optional[str]


class TransactionInDBBase(TransactionBase):
    id: Optional[UUID] = None
    status: str  # type: ignore

    @validator("status", pre=True)
    def transaction_status_to_str(cls, v: int) -> str:
        return TransactionStatus(v).name

    class Config:
        orm_mode = True


class Transaction(TransactionInDBBase):
    pass
