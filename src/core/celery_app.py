import asyncio
import datetime

from celery import Celery

import crud
from core import dependencies
from core.config import app_settings
from db.models.transaction import TransactionStatus
from schemas import TransactionUpdate

celery = Celery(__name__, broker=app_settings.BROKER_HOST, backend=app_settings.BROKER_HOST)


async def expire_transaction(
    trade_id: str,
) -> None:
    db = dependencies.async_session()

    transaction = await crud.transactions.get(db, trade_id)

    if transaction is None:
        return

    if transaction.status != TransactionStatus.ON_PAYMENT_WAIT:
        return

    transaction_obj = TransactionUpdate(status=TransactionStatus.EXPIRED, closed_on=datetime.datetime.now())

    await crud.transactions.update(db=db, db_obj=transaction, obj_in=transaction_obj)


@celery.task(name="transaction_expire_timer")
def set_transaction_expire_timer(trade_id: str) -> None:
    asyncio.run(expire_transaction(trade_id))
