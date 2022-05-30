import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, validator
from pydantic.schema import UUID

from db.models.transaction import CryptoType, FiatType, SellType, TransactionStatus


class TransactionBase(BaseModel):
    seller_wallet: Optional[str] = None
    buyer_wallet: Optional[str] = None
    seller_email: Optional[str] = None
    buyer_email: Optional[str] = None
    initiator: Optional[str] = None
    amount: Optional[Decimal]
    fiat_amount: Optional[Decimal]
    fiat_type: FiatType = FiatType.KZT
    status: TransactionStatus = TransactionStatus.CREATED
    crypto_type: CryptoType = CryptoType.ETH
    sell_type: SellType = SellType.SELL
    created_at: datetime.datetime = datetime.datetime.now()
    closed_on: Optional[datetime.datetime]
    updated_at: Optional[datetime.datetime]
    hash: Optional[str]


class TransactionCreate(BaseModel):
    seller_wallet: str
    seller_email: EmailStr
    amount: Decimal
    price: Decimal
    crypto_type: CryptoType
    fiat_type: FiatType
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
