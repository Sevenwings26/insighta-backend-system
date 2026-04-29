import time
import logging
from fastapi import Request

logger = logging.getLogger("insighta")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


async def logging_middleware(request: Request, call_next):
    start_time = time.perf_counter()

    response = await call_next(request)

    duration = time.perf_counter() - start_time

    logger.info(
        f"{request.method} "
        f"{request.url.path} "
        f"{response.status_code} "
        f"{duration:.4f}s"
    )

    return response
