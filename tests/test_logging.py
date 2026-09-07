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
            patch.object(main, "TimedRotatingFileHandler", return_value=RecordingHandler()),
            patch.object(main.atexit, "register"),
        ):
            listener = main.init_logging()
            try:
                logger.info("key handled")
            finally:
                listener.stop()
        self.assertEqual(2, sum(message == "key handled" for message, _ in calls))
        for _, thread in calls:
            self.assertIsNot(thread, caller)
