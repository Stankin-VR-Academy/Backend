import logging
import sys

from loguru import logger

logger.remove()


# Перехват стандартных логов и перенаправление в loguru
class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Получаем соответствующий уровень loguru
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Находим вызывающего модуль
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


# Перехватываем все стандартные логи
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

# Отключаем логгеры uvicorn, чтобы они не выводили дублирующие сообщения
for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
    logging_logger = logging.getLogger(logger_name)
    logging_logger.handlers = [InterceptHandler()]
    logging_logger.propagate = False


def format_extra(record):
    """Форматирование extra значений с разделителем |."""
    extra = record["extra"]
    # Исключаем стандартные поля loguru
    extra_filtered = {
        k: v for k, v in extra.items() if k not in ["name", "function", "line", "file_path", "clickable_path"]
    }

    if not extra_filtered:
        return ""

    # Форматируем значения через разделитель |
    values = [f"{k}={v}" for k, v in extra_filtered.items()]
    return " | " + " | ".join(values)


def format_path(record):
    line = record["line"]
    function = record["function"]
    file = record["file"]

    path = f"{file}:{function}:{line}"
    return path


LOG_FORMAT = (
    "<green>{time:DD.MM.YYYY HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[path]}</cyan> | "
    "<level>{message}</level>"
    "{extra[formatted]}"
)


def formatter(record):
    """Кастомный форматтер для логов."""
    record["extra"]["formatted"] = format_extra(record)
    record["extra"]["path"] = format_path(record)
    return LOG_FORMAT + "\n"


logger.add(
    sys.stdout,
    format=formatter,
    level="INFO",
    colorize=True,
    backtrace=True,
    diagnose=True,
    enqueue=True,
)


def get_logger(extra_context: dict = None):
    """Получить логгер с дополнительным контекстом."""
    if extra_context:
        return logger.bind(**extra_context)
    return logger


__all__ = ["logger", "get_logger"]
