import httpx

_timeout = httpx.Timeout(
    timeout=30.0,
)
client = httpx.Client(timeout=_timeout)
async_client = httpx.AsyncClient(timeout=_timeout)
