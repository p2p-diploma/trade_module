import traceback

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.cors import CORSMiddleware

from api.v1.api import api_router
from core.config import app_settings
from core.dependencies import get_session
from exceptions import APIException, SomethingWentWrongException


def create_app() -> FastAPI:
    app = FastAPI(title="Trade Service")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthcheck")
    def healthcheck(session: AsyncSession = Depends(get_session)) -> None:
        pass

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> Response:
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exception: APIException) -> Response:
        return ORJSONResponse(
            content=APIException.Schema(
                code=exception.default_code,
                detail=exception.default_detail,
            ).dict(),
            status_code=exception.default_status_code,
        )

    @app.exception_handler(Exception)
    async def exception_handler(request: Request, exception: Exception) -> Response:
        if not isinstance(exception, APIException):
            exception = SomethingWentWrongException()
        return ORJSONResponse(
            content=APIException.Schema(
                code=exception.default_code,
                detail=exception.default_detail,
            ).dict(),
            status_code=exception.default_status_code,
        )

    app.include_router(api_router, prefix=app_settings.API_V1_STR)

    return app
