import logging
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class TestLogging(unittest.TestCase):
    def test_output_is_written_off_the_caller_thread_and_drained_on_stop(self):
        calls = []
        caller = threading.current_thread()

        class RecordingHandler(logging.Handler):
            def emit(self, record):
                calls.append((record.getMessage(), threading.current_thread()))

        logger = logging.Logger("test-dokey-logging")
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(main, "root", Path(directory)),
            patch.object(main.logging, "getLogger", return_value=logger),
            patch.object(main.logging, "StreamHandler", RecordingHandler),
            patch.object(
                main, "TimedRotatingFileHandler", return_value=RecordingHandler()
            ),
            patch.object(main.atexit, "register"),
        ):
            listener = main.init_logging()
            try:
                logger.info("key handled")
                logger.info(
                    "usage",
                    extra={
                        "usage": {
                            "event": "binding",
                            "binding": "common.j",
                            "action": "keys",
                            "repeat": False,
                        }
                    },
                )
            finally:
                listener.stop()
                for handler in listener.handlers:
                    handler.close()
            self.assertTrue((Path(directory) / "logs" / "usage.jsonl").exists())
            self.assertEqual(
                1, len(list((Path(directory) / "logs").glob("usage-summary-*.json")))
            )
        self.assertEqual(2, sum(message == "key handled" for message, _ in calls))
        self.assertFalse(any(message == "usage" for message, _ in calls))
        for _, thread in calls:
            self.assertIsNot(thread, caller)
