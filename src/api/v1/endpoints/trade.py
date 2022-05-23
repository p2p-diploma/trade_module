from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

import schemas
from api.v1.trade_service import TradeService
from core import dependencies

router = APIRouter()


@router.post("/", response_model=schemas.Transaction)
async def create_transaction(
    *,
    db: AsyncSession = Depends(dependencies.get_session),
    current_user_wallet: tuple[str, str, str] = Depends(dependencies.get_current_user_wallet),
    transaction_in: schemas.TransactionCreate,
    trade_service: TradeService = Depends()
) -> Any:
    transaction = await trade_service.create_transaction(
        db=db, obj_in=transaction_in, active_user_wallet=current_user_wallet
    )

    return transaction


@router.post("/approve_payment/{trade_id}", response_model=schemas.Transaction)
async def approve_payment(
    trade_id: UUID,
    db: AsyncSession = Depends(dependencies.get_session),
    current_user_wallet: tuple[str, str, str] = Depends(dependencies.get_current_user_wallet),
    trade_service: TradeService = Depends(),
) -> Any:
    transaction = await trade_service.approve_trade_payment(
        db=db, current_user_wallet=current_user_wallet, trade_id=trade_id
    )
    return transaction


@router.post("/cancel_transaction/{trade_id}", response_model=schemas.Transaction)
async def cancel_transaction(
    trade_id: UUID,
    db: AsyncSession = Depends(dependencies.get_session),
    current_user_wallet: tuple[str, str, str] = Depends(dependencies.get_current_user_wallet),
    trade_service: TradeService = Depends(),
) -> Any:
    transaction = await trade_service.cancel_transaction(
        db=db, current_user_wallet=current_user_wallet, trade_id=trade_id
    )
    return transaction
