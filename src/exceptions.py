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


class TransactionStatusPermitted(APIException):
    default_status_code = status.HTTP_400_BAD_REQUEST
    default_code = "status_permitted"
    default_detail = "Transaction status is not processable"


class TransactionInitiatorException(APIException):
    default_status_code = status.HTTP_403_FORBIDDEN
    default_code = "not_initiator"
    default_detail = "Your are not the trade initiator"


class NotEnoughBalanceException(APIException):
    default_status_code = status.HTTP_400_BAD_REQUEST
    default_code = "not_enough_balance"
    default_detail = "Not enough balance for trade"


class TransactionPaymentTimeExpired(APIException):
    default_status_code = status.HTTP_400_BAD_REQUEST
    default_code = "time_expired"
    default_detail = "Payment time expired"


class SomethingWentWrongException(APIException):
    default_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_code = "something_went_wrong"
    default_detail = "Sorry. Something Went Wrong. Please, contact us!"
