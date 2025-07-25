import inspect
import logging.config
import re
import sys
from typing import TYPE_CHECKING

import loguru

from app.utils import escape_tag

if TYPE_CHECKING:
    from loguru import Logger

logger: "Logger" = loguru.logger


_ANSI_TO_LOGURU_TAG = {
    # Fore
    "\033[30m": "<black>",
    "\033[31m": "<red>",
    "\033[32m": "<green>",
    "\033[33m": "<yellow>",
    "\033[34m": "<blue>",
    "\033[35m": "<magenta>",
    "\033[36m": "<cyan>",
    "\033[37m": "<white>",
    # Back
    "\033[40m": "<BLACK>",
    "\033[41m": "<RED>",
    "\033[42m": "<GREEN>",
    "\033[43m": "<YELLOW>",
    "\033[44m": "<BLUE>",
    "\033[45m": "<MAGENTA>",
    "\033[46m": "<CYAN>",
    "\033[47m": "<WHITE>",
    # Style
    # "\033[0m": "</>",  # RESET
    "\033[1m": "<bold>",
    "\033[2m": "<dim>",
    "\033[3m": "<italic>",
    "\033[4m": "<underline>",
    "\033[5m": "<blink>",
    "\033[7m": "<reverse>",
    "\033[8m": "<hidden>",
    "\033[9m": "<strike>",
}
_ANSI_RESET = "\033[0m"
_ANSI_PATTERN = re.compile(r"(\033\[\d+(;\d+)*m)")


def _ansi_to_loguru_tag(text: str) -> str:
    result: list[str] = []
    open_tags: list[str] = []
    last_end = 0

    for match in _ANSI_PATTERN.finditer(text):
        start, end = match.start(), match.end()
        ansi_code = text[start:end]

        if start > last_end:
            result.append(text[last_end:start])

        if ansi_code == _ANSI_RESET:
            result.append("</>" * len(open_tags))
            open_tags = []
        elif ansi_code in _ANSI_TO_LOGURU_TAG:
            loguru_tag = _ANSI_TO_LOGURU_TAG[ansi_code]
            result.append(loguru_tag)
            open_tags.append(loguru_tag)

        last_end = end

    if last_end < len(text):
        result.append(text[last_end:])

    return "".join(result)


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

        kwds = {"depth": depth, "exception": record.exc_info}
        if colored := record.__dict__.get("color_message"):  # uvicorn color log
            record.msg = _ansi_to_loguru_tag(escape_tag(colored))
            kwds["colors"] = True

        logger.opt(**kwds).log(level, record.getMessage())


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"default": {"class": "app.log.LoguruHandler"}},
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "httpx": {"handlers": ["default"], "level": "INFO", "propagate": False},
    },
}


log_format = "<g>{time:HH:mm:ss}</g> [<lvl>{level}</lvl>] <c><u>{name}</u></c> | {message}"
logger.remove()
logger_id_console = logger.add(
    sys.stdout,
    level="DEBUG",
    diagnose=False,
    # diagnose=True,  # 生产环境应设置为 False
    enqueue=True,
    format=log_format,
)
logger_id_file = logger.add(
    "./logs/{time:YYYY-MM-DD}.log",
    rotation="00:00",
    level="DEBUG",
    diagnose=True,
    enqueue=True,
    format=log_format,
)


def configure_logging() -> None:
    """配置日志记录器。"""
    logging.config.dictConfig(LOGGING_CONFIG)
