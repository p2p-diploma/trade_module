from http.client import HTTPException
from typing import Any, Optional

from pydantic import BaseModel
from starlette import status


class APIException(HTTPException):
    class Schema(BaseModel):
        code: str
        detail: str

    default_status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_code: str = "internal_error"
    default_detail: str = "Internal Error."

    def __init__(
        self,
        status_code: Optional[int] = None,
        detail: Optional[str] = None,
        headers: Optional[dict[str, Any]] = None,
    ):
        if status_code is None:
            status_code = self.default_status_code
        if detail is None:
            detail = self.default_detail
        super().__init__(status_code, detail, headers)


class NotFound(APIException):
    default_status_code = status.HTTP_404_NOT_FOUND
    default_code = "not_found"
    default_detail = "Not Found."
