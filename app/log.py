import inspect
import logging
import sys
from typing import TYPE_CHECKING

import loguru

if TYPE_CHECKING:
    from loguru import Logger, Record

logger: "Logger" = loguru.logger


# https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
class LoguruHandler(logging.Handler):  # pragma: no cover
    """logging 与 loguru 之间的桥梁，将 logging 的日志转发到 loguru。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def default_filter(record: "Record") -> bool:
    log_level = record["extra"].get("log_level", "INFO")
    levelno = logger.level(log_level).no if isinstance(log_level, str) else log_level
    return record["level"].no >= levelno


log_format = "<g>{time:HH:mm:ss}</g> [<lvl>{level}</lvl>] <c><u>{name}</u></c> | {message}"
logger.remove()
logger_id_console = logger.add(
    sys.stdout,
    level=0,
    diagnose=False,
    filter=default_filter,
    format=log_format,
)
logger_id_file = logger.add(
    "./logs/{time:YYYY-MM-DD}.log",
    rotation="00:00",
    level="DEBUG",
    diagnose=True,
    filter=default_filter,
    format=log_format,
)
