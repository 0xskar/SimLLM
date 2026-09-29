from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Awaitable, Callable

from simllm.db import logs_repo

BroadcastFn = Callable[..., Awaitable[None]]


class JsonLinesFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload)


def configure_logging(log_dir: Path, save_name: str) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    run_file = log_dir / f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.jsonl"

    logger = logging.getLogger("simllm")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    file_handler = RotatingFileHandler(run_file, maxBytes=10_000_000, backupCount=5)
    file_handler.setFormatter(JsonLinesFormatter())
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(console_handler)

    return logger


def log_event(logger: logging.Logger, category: str, message: str, **fields) -> None:
    logger.info(message, extra={"extra_fields": {"category": category, **fields}})


async def record_log_event(
    conn: sqlite3.Connection | None,
    logger: logging.Logger | None,
    broadcast_fn: BroadcastFn | None,
    *,
    category: str,
    level: str,
    message: str,
    tick: int,
    sim_time: str,
    **fields,
) -> None:
    """The one place a log entry gets fanned out to all three destinations:
    the rotating JSONL file, the events_log table (for GET /api/logs
    backfill), and the live WS 'log' event. Used by both the simulation
    engine and any REST route that wants to log a user-initiated action
    (see routes_sim.py, routes_saves.py) -- category "system" is reserved
    for the latter.
    """
    if logger is not None:
        log_event(logger, category, message, **fields)
    if conn is not None:
        logs_repo.add_event(
            conn,
            tick=tick,
            sim_datetime=sim_time,
            category=category,
            agent_id=fields.get("agent_id"),
            payload={"level": level, "message": message, **fields},
        )
    if broadcast_fn is not None:
        await broadcast_fn(
            "log", {"level": level, "category": category, "message": message, **fields}, tick=tick, sim_time=sim_time
        )
