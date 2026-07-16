"""日志配置。"""

from __future__ import annotations

import logging


LOGGER_NAME = "pysectool"


def get_logger() -> logging.Logger:
    """获取 pysectool 日志记录器。"""
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger


def configure_logging(*, verbose: bool = False, quiet: bool = False) -> None:
    """配置 pysectool 日志级别与输出格式。

    Args:
        verbose: 是否输出 DEBUG 级别日志。
        quiet: 是否只输出 ERROR 及以上级别日志。
    """
    logger = get_logger()
    logger.handlers.clear()

    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logger.setLevel(level)

    handler = logging.StreamHandler()
    handler.setLevel(level)

    if verbose:
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    else:
        fmt = "%(message)s"

    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)

    # 避免重复向上传播导致重复输出
    logger.propagate = False
