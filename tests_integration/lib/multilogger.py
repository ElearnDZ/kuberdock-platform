import logging
import os
from contextlib import contextmanager
from tempfile import NamedTemporaryFile


@contextmanager
def lock(handler):
    handler.acquire()
    yield
    handler.release()


class FilePerThreadHandler(logging.Handler):
    """
    Logging handler which automatically outputs log to the file depending on a
    thread log was sent from. Allows to print logs produced by each thread
    separately.

    Used in integration tests where tests are executed in different
    pipelines, in different threads
    """

    def __init__(self):
        super(FilePerThreadHandler, self).__init__()
        self.files = {}

    def flush(self):
        with lock(self):
            for fp in self.files.values():
                fp.flush()

    def _get_or_open(self, key):
        with lock(self):
            try:
                return self.files[key]
            except KeyError:
                fp = NamedTemporaryFile('w+', delete=False)
                self.files[key] = fp
                return fp

    def emit(self, record):
        try:
            fp = self._get_or_open(record.threadName)
            msg = self.format(record)
            fp.write('{}\n'.format(msg.encode('utf-8')))
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    def close(self):
        for fp in self.files.values():
            fp.close()
            os.unlink(fp.name)
        self.files = {}

    @property
    def thread_names(self):
        return self.files.keys()

    def get_thread_log(self, thread_name):
        fp = self.files[thread_name]
        fp.seek(0)
        return fp.read()


def init_handler(logger, live_log=False):
    log_format = '%(threadName)s %(message)s'

    if not live_log:
        logger.handlers = []
    handler = FilePerThreadHandler()
    handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(handler)

    return handler
