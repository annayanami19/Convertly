"""Entry point Convertly — jendela native pywebview (WebView2).

start.bat menjalankan file ini via pythonw; PID ditulis ke .pid agar
stop.bat/uninstall.bat bisa mematikan prosesnya.
"""
import atexit
import os
import sys

CODE_DIR = os.path.dirname(os.path.abspath(__file__))   # .../src
BASE_DIR = os.path.dirname(CODE_DIR)                     # root repo
os.chdir(BASE_DIR)  # artefak runtime (config.json, app.log, .pid) di root
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

import webview  # noqa: E402

from api import Api, _task_emitter  # noqa: E402
import core.applog as applog  # noqa: E402
import core.engine as engine  # noqa: E402
import core.settings as settings  # noqa: E402

PID_FILE = os.path.join(BASE_DIR, ".pid")


def _write_pid():
    with open(PID_FILE, "w", encoding="ascii") as f:
        f.write(str(os.getpid()))


def _cleanup_pid():
    try:
        os.remove(PID_FILE)
    except OSError:
        pass


def main():
    # AppUserModelID sendiri: taskbar tidak mengikat icon ke pythonw.exe
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "imp.convertly.1")
    except Exception:
        pass

    applog.debug("=" * 60)
    applog.debug("APP START pid=%s pywebview=%s" % (os.getpid(),
                 getattr(webview, "__version__", "?")))
    settings.load()          # muat config awal
    engine.setup(_task_emitter)  # pool worker + emitter progress
    _write_pid()
    atexit.register(_cleanup_pid)

    theme = settings.load().get("theme", "dark")
    bg = "#0b0f1a" if theme == "dark" else "#f4f1ea"
    api_instance = Api()
    window = webview.create_window(
        "Convertly",
        os.path.join(CODE_DIR, "ui", "index.html"),
        js_api=api_instance,
        width=1200, height=780,
        min_size=(940, 620),
        background_color=bg,
    )

    def _bind_drop():
        """Path file drop HANYA tersedia di sisi Python (pywebview 5+):
        event drop ditangkap DOMEventHandler, pywebviewFullPath dikirim
        ke JS via bridge. WebView2 menyembunyikan path dari JavaScript.
        """
        import traceback
        from webview.dom import DOMEventHandler
        try:
            applog.debug("bind: window.events.loaded fired")
            doc = window.dom.document
            applog.debug("bind: document=%r" % doc)
            doc.events.drop += DOMEventHandler(
                api_instance.on_drop_event,
                prevent_default=True, stop_propagation=True)
            applog.debug("bind: drop handler TERPASANG di document")
        except Exception:
            applog.error("bind drop GAGAL:\n" + traceback.format_exc())
        _force_taskbar_icon()

    def _force_taskbar_icon():
        """Lapisan paksa: WM_SETICON langsung ke handle Form WinForms.
        webview.start(icon=...) sudah memasang Form.Icon, tapi ini
        menjamin title bar + taskbar memakai icon aplikasi.
        """
        import ctypes
        import time
        import traceback
        try:
            ico = os.path.join(CODE_DIR, "ui", "assets", "icon.ico")
            if not os.path.exists(ico):
                applog.error("taskbar icon: file tidak ada: %s" % ico)
                return
            u32 = ctypes.windll.user32
            hicon = u32.LoadImageW(None, ico, 1, 0, 0, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
            if not hicon:
                applog.error("taskbar icon: LoadImageW gagal")
                return
            for _ in range(50):  # tunggu Form handle (maks ~5 dtk)
                hwnd = getattr(getattr(window, "native", None), "Handle", None)
                if hwnd:
                    # pythonnet System.IntPtr tidak mendukung int() langsung
                    hwnd = int(hwnd.ToInt64()) if hasattr(hwnd, "ToInt64") \
                        else int(hwnd)
                    u32.SendMessageW(hwnd, 0x80, 1, hicon)  # WM_SETICON ICON_BIG
                    u32.SendMessageW(hwnd, 0x80, 0, hicon)  # WM_SETICON ICON_SMALL
                    applog.debug("taskbar icon dipasang via WM_SETICON hwnd=%d" % hwnd)
                    return
                time.sleep(0.1)
            applog.error("taskbar icon: window handle tidak ditemukan")
        except Exception:
            applog.error("taskbar icon GAGAL:\n" + traceback.format_exc())

    window.events.loaded += _bind_drop
    icon_path = os.path.join(CODE_DIR, "ui", "assets", "icon.ico")
    webview.start(icon=icon_path if os.path.exists(icon_path) else None)
    applog.debug("APP EXIT normal")


if __name__ == "__main__":
    main()
