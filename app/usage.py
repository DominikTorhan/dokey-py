"""Local usage records. Serialization and disk I/O run on the logging worker."""

import hashlib
import json
import logging
import time
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from logging.handlers import TimedRotatingFileHandler

from app.events import CMDEvent, SendEvent, WriteEvent
from app.keys import FIRST_STEPS, Keys
from app.version import VERSION

SESSION_ID = uuid.uuid4().hex
logger = logging.getLogger(__name__)


def record(event, **fields):
    logger.info("usage", extra={"usage": {"event": event, **fields}})


def configuration(config, mouse_config):
    """Fingerprint the effective configuration, including user overrides.

    The hashed payload stays in memory. The manifest contains IDs and types,
    never command lines or text-expansion contents.
    """

    def encode(value):
        if isinstance(value, Keys):
            return value.name.lower()
        if isinstance(value, dict):
            return {str(encode(k)): encode(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [encode(v) for v in value]
        if hasattr(value, "__dict__"):
            return {"type": type(value).__name__, "value": encode(vars(value))}
        return value

    payload = json.dumps(
        encode([vars(config), mouse_config.positions]), sort_keys=True
    ).encode("utf-8")
    bindings = {f"prefix.{key.name.lower()}": "prefix" for key in FIRST_STEPS}
    bindings.update(
        {
            "control.off_mode": "mode",
            "control.change_mode": "mode",
            "control.mouse_mode": "mode",
            "control.help": "help",
            "control.diagnostics": "diagnostics",
            "control.exit": "exit",
            "control.clear_screen": "clear_screen",
        }
    )
    for section in ("common", "special"):
        for key in getattr(config, section):
            if key is not None:
                bindings[f"{section}.{key.name.lower()}"] = "keys"
    for first, entries in config.two_step_events.items():
        if first is None:
            continue
        for key, event in entries.items():
            if key is None:
                continue
            kind = {
                SendEvent: "keys",
                CMDEvent: "command",
                WriteEvent: "text",
            }[type(event)]
            bindings[f"two_step.{first.name.lower()}.{key.name.lower()}"] = kind
    for name in mouse_config.positions:
        key = Keys.from_string(name)
        if key is not None:
            bindings[f"mouse.{key.name.lower()}"] = "mouse"
    return hashlib.sha256(payload).hexdigest(), bindings


class DiagnosticFilter(logging.Filter):
    def filter(self, record):
        record.session_id = SESSION_ID
        return not hasattr(record, "usage")


class UsageHandler(logging.Handler):
    """JSONL details for seven rotations; per-session daily counts for 60 days.

    Snapshots are replaced atomically once per minute of activity and at shutdown.
    Separate session files avoid overwriting another running instance's totals.
    """

    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self.details = TimedRotatingFileHandler(
            directory / "usage.jsonl",
            when="midnight",
            backupCount=7,
            encoding="utf-8",
            delay=True,
            utc=True,
        )
        self.day = None
        self.config = None
        self.bindings = {}
        self.features = {}
        self.counts = Counter()
        self.started = None
        self.updated = None
        self.last_flush = time.monotonic()
        self.dirty = False
        self.session_ended = False
        self.write_failed = False

    def emit(self, log_record):
        if not hasattr(log_record, "usage"):
            return
        try:
            self._emit(log_record)
        except Exception:
            self.handleError(log_record)

    def _emit(self, log_record):
        timestamp = datetime.fromtimestamp(log_record.created, timezone.utc)
        day = timestamp.date().isoformat()
        if day != self.day:
            self.flush()
            self.day = day
            self.counts.clear()
            self.started = timestamp.isoformat()
            self._expire(timestamp.date())
        fields = log_record.usage
        if fields["event"] == "session_start":
            self.config = fields["config"]
            self.bindings = fields["bindings"]
            self.features = fields["features"]
        if fields["event"] == "session_end":
            self.session_ended = True
        self.updated = timestamp.isoformat()
        data = {
            "schema": 1,
            "timestamp": self.updated,
            "session": SESSION_ID,
            "version": VERSION,
            "config": self.config,
            **fields,
        }
        # A fresh record avoids changing the record shared with other handlers.
        detail = logging.makeLogRecord({"msg": json.dumps(data, sort_keys=True)})
        self.details.handle(detail)
        if fields["event"] not in ("session_start", "session_end"):
            key = json.dumps(fields, sort_keys=True)
            self.counts[key] += 1
        self.dirty = True
        if (
            fields["event"] in ("session_start", "session_end")
            or time.monotonic() - self.last_flush >= 60
        ):
            self.flush()

    def flush(self):
        self.acquire()
        try:
            if not self.dirty:
                return
            data = {
                "schema": 1,
                "date": self.day,
                "session": SESSION_ID,
                "version": VERSION,
                "config": self.config,
                "bindings": self.bindings,
                "features": self.features,
                "first_record": self.started,
                "last_record": self.updated,
                "session_ended": self.session_ended,
                "counts": [
                    {**json.loads(key), "count": count}
                    for key, count in sorted(self.counts.items())
                ],
            }
            path = self.directory / f"usage-summary-{self.day}-{SESSION_ID}.json"
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            temporary.replace(path)
            self.dirty = False
            self.last_flush = time.monotonic()
            self.write_failed = False
        except OSError as error:
            # Do not let an unavailable log directory interrupt input processing
            # or interpreter shutdown. Detailed records may still be available.
            self.last_flush = time.monotonic()
            if not self.write_failed:
                self.write_failed = True
                logger.error("Could not save usage summary: %s", type(error).__name__)
        finally:
            self.release()

    def _expire(self, today):
        cutoff = today - timedelta(days=59)
        for path in self.directory.glob("usage-summary-????-??-??-*.json"):
            try:
                recorded = date.fromisoformat(path.name[14:24])
                session = path.name[25:-5]
                if len(session) == 32 and all(
                    c in "0123456789abcdef" for c in session
                ):
                    if recorded < cutoff:
                        path.unlink()
            except (ValueError, OSError):
                continue

    def close(self):
        self.flush()
        self.details.close()
        super().close()
