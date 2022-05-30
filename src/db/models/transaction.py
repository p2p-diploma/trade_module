import datetime
import enum
import uuid
from decimal import Decimal
from typing import Union

from sqlalchemy import Column, DateTime, Enum, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped

from db.base_class import Base


class TransactionStatus(enum.Enum):
    CREATED = 10
    ON_PAYMENT_WAIT = 20
    ON_APPROVE = 30
    EXPIRED = 40
    SUCCESS = 50
    CANCELED = 99

    @classmethod
    @property
    def status_order(cls) -> list["TransactionStatus"]:
        return [cls.CREATED, cls.ON_PAYMENT_WAIT, cls.ON_APPROVE, cls.SUCCESS]

    @property
    def next(self) -> Union["TransactionStatus", None]:
        order = self.status_order
        next_status_index = order.index(self) + 1
        if next_status_index >= len(order):
            return None
        return order[next_status_index]


class CryptoType(enum.Enum):
    ERC20 = "erc20"
    ETH = "eth"


class FiatType(enum.Enum):
    KZT = "kzt"
    USD = "usd"


class SellType(enum.Enum):
    SELL = "sell"
    BUY = "buy"


class Transaction(Base):
    id: Mapped[UUID] = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    initiator: Mapped[str] = Column(String, index=True)  # Current approving user
    seller_wallet: Mapped[str] = Column(String, index=True)
    buyer_wallet: Mapped[str] = Column(String, index=True)
    seller_email: Mapped[str] = Column(String, index=True, nullable=False)
    buyer_email: Mapped[str] = Column(String, index=True, nullable=False)

    amount: Mapped[Decimal] = Column(Numeric(precision=14, scale=6), nullable=False)
    crypto_type: Mapped[CryptoType] = Column(Enum(CryptoType), nullable=False)
    fiat_amount: Mapped[Decimal] = Column(Numeric(precision=14, scale=6), nullable=False)
    fiat_type: Mapped[FiatType] = Column(Enum(FiatType), nullable=False)
    sell_type: Mapped[SellType] = Column(Enum(SellType), nullable=False)

    status: Mapped[TransactionStatus] = Column(
        Enum(TransactionStatus), default=TransactionStatus.CREATED, nullable=False
    )
    created_at: Mapped[datetime.datetime] = Column(DateTime, default=datetime.datetime.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = Column(DateTime, onupdate=datetime.datetime.now())
    closed_on: Mapped[datetime.datetime] = Column(DateTime, nullable=True)
    hash: Mapped[str] = Column(String, nullable=True, index=True, unique=True)
