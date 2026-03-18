from __future__ import annotations

import logging
import sys
from pythonjsonlogger import jsonlogger


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"levelname": "level", "asctime": "ts"},
    )
    handler.setFormatter(formatter)

    # Reset handlers
    root.handlers = []
    root.addHandler(handler)

    # Quieter logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
