"""Logger aplikasi — app.log di folder project (append, buka-tutup per baris).

Dipakai khusus untuk mendiagnosis jalur yang tidak terlihat saat jalan
via pythonw (tanpa console): drag & drop, bridge JS, error startup.
"""
import logging
import os

_log = None


def get():
    global _log
    if _log is None:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "app.log")
        _log = logging.getLogger("convertly")
        _log.setLevel(logging.DEBUG)
        if not _log.handlers:
            h = logging.FileHandler(path, encoding="utf-8")
            h.setFormatter(logging.Formatter(
                "%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S"))
            _log.addHandler(h)
        _log.propagate = False
    return _log


def debug(msg):
    get().debug(msg)


def error(msg):
    get().error(msg)


def path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "app.log")


def clear():
    """Kosongkan app.log (handler ditutup lalu file di-truncate)."""
    global _log
    logger = get()
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    _log = None  # inisialisasi ulang (mode append) pada pemanggilan berikut
    with open(path(), "w", encoding="utf-8") as f:
        f.write("")
