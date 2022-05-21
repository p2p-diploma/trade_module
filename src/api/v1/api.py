from fastapi import APIRouter

from api.v1.endpoints import trade

api_router = APIRouter()
api_router.include_router(trade.router, tags=["Trades"], prefix="/trade")
