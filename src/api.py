"""Jembatan JS <-> Python untuk pywebview (js_api).

Semua method yang di-expose ke JS tidak boleh diawali underscore.
Event dari thread worker dikirim ke JS lewat evaluate_js (thread-safe).
"""
import json
import os
import threading

import webview

import core.applog as applog
import core.deps as deps
import core.engine as engine
import core.registry as registry
import core.settings as settings

_emit_lock = threading.Lock()


def push_js(event, payload):
    """Kirim event ke frontend. Dipanggil dari thread mana pun."""
    win = webview.windows[0] if webview.windows else None
    if win is None:
        applog.debug("push_js[%s] DIBUANG: tidak ada window" % event)
        return
    data = json.dumps({"event": event, **payload})
    try:
        with _emit_lock:
            win.evaluate_js("window.__onEvent(%s)" % data)
        applog.debug("push_js[%s] terkirim (%d byte)" % (event, len(data)))
    except Exception as e:
        applog.error("push_js[%s] GAGAL: %r" % (event, e))


def _task_emitter(payload):
    push_js("task", payload)


FILE_FILTERS = (
    # pywebview mewajibkan ekstensi dipisah ";" TANPA spasi —
    # format salah melempar ValueError dari parse_file_type (dialog mati diam-diam)
    "File yang didukung (*.png;*.jpg;*.jpeg;*.webp;*.gif;*.bmp;*.tiff;*.tif;"
    "*.ico;*.avif;*.heic;*.heif;*.pdf;*.docx;*.xlsx;*.pptx;*.txt;*.md;*.html;"
    "*.htm;*.csv;*.mp3;*.wav;*.flac;*.ogg;*.m4a;*.aac;*.wma;*.opus;*.mp4;"
    "*.mkv;*.webm;*.mov;*.avi;*.flv;*.wmv;*.m4v;*.ts;*.3gp;*.ogv)",
    "Semua file (*.*)",
)


class Api:
    # ---- dialog file ----------------------------------------------------
    def select_files(self):
        applog.debug("select_files: buka dialog")
        result = webview.windows[0].create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=True,
            file_types=list(FILE_FILTERS))
        out = list(result or [])
        applog.debug("select_files: %d file dipilih" % len(out))
        return out

    def select_folder(self):
        result = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER)
        return result[0] if result else ""

    # ---- konversi -------------------------------------------------------
    def add_tasks(self, items):
        return engine.add_tasks(items)

    def targets_for(self, ext):
        """Format target valid untuk ekstensi + paket yang kurang per target."""
        ext = (ext or "").lower()
        cat = registry.category_of(ext)
        out = []
        for t in registry.targets_for(ext):
            need = registry.deps_for_target(cat, t, ext) if cat else []
            missing = registry.missing_modules(need)
            if cat == "media" and not _ffmpeg_ok():
                missing.append("ffmpeg")
            out.append({"target": t, "missing": missing})
        return {"category": cat, "targets": out}

    def snapshot(self):
        return engine.snapshot()

    def cancel(self, task_id):
        return engine.cancel(task_id)

    def cancel_all(self):
        return engine.cancel_all()

    def clear_finished(self):
        return engine.clear_finished()

    # ---- settings -------------------------------------------------------
    def get_settings(self):
        return settings.load()

    def set_settings(self, patch):
        cfg = settings.update(**(patch or {}))
        if "workers" in (patch or {}):
            engine.rebuild_pool()
        return cfg

    def reset_settings(self):
        """Kembalikan semua pengaturan ke default (riwayat dipertahankan)."""
        cfg = settings.reset()
        engine.rebuild_pool()
        applog.debug("settings direset ke default via UI")
        return cfg

    def clear_history(self):
        cfg = settings.clear_history()
        applog.debug("riwayat dibersihkan via UI")
        return cfg

    def get_log_path(self):
        return applog.path()

    def clear_logs(self):
        applog.debug("log dibersihkan via UI")
        applog.clear()
        return True

    # ---- dependencies ---------------------------------------------------
    def get_deps(self):
        return deps.check()

    def install_deps(self, packages):
        """pip install di background; log live ke UI via event dep_log."""
        if not packages:
            return {"started": False, "reason": "tidak ada paket"}
        if _install_running[0]:
            return {"started": False, "reason": "install masih berjalan"}

        def on_output(line):
            push_js("dep_log", {"line": line})

        def on_done(code):
            deps.invalidate()
            push_js("dep_done", {"code": code,
                                 "status": deps.check(refresh=True)})
            _install_running[0] = False

        _install_running[0] = True
        deps.install(packages, on_output, on_done)
        return {"started": True, "packages": packages}

    def ffmpeg_guide(self):
        return {
            "detected": _ffmpeg_ok(),
            "command": "winget install --id Gyan.FFmpeg -e",
            "note": "ffmpeg bukan paket pip. Jalankan command di PowerShell, "
                    "lalu tutup dan buka lagi aplikasi (atau klik Refresh).",
    }

    # ---- util ------------------------------------------------------------
    def open_path(self, path):
        if path and os.path.exists(path):
            os.startfile(path)  # noqa: S606 — Windows-only app, path dari UI sendiri
            return True
        return False

    def on_drop_event(self, event):
        """Handler DOMEventHandler untuk event drop.

        Path file asli HANYA ada di sisi Python (pywebview menuntelnya
        sebagai pywebviewFullPath); WebView2 menyembunyikannya dari JS.
        Path dikirim ke JS via event bridge "files_dropped".
        """
        applog.debug("DROP EVENT DITERIMA, type=%s" % type(event).__name__)
        try:
            applog.debug("DROP RAW: %s" % json.dumps(
                event, default=str)[:2000])
        except Exception:
            applog.debug("DROP RAW (tidak serializable): %r" % (event,))

        def _files_from(d):
            if not isinstance(d, dict):
                return []
            return (d.get("dataTransfer", {}) or {}).get("files", []) or \
                   (d.get("domTransfer", {}) or {}).get("files", [])

        raw = _files_from(event if isinstance(event, dict)
                          else getattr(event, "__dict__", {}))
        paths = []
        for f in raw:
            p = f.get("pywebviewFullPath") if isinstance(f, dict) else None
            applog.debug("DROP file entry: full=%r exists=%s" %
                         (p, bool(p) and os.path.exists(p)))
            if p and os.path.exists(p):
                paths.append(p)
        applog.debug("DROP parsed: %d path valid dari %d entry" %
                     (len(paths), len(raw)))
        if paths:
            push_js("files_dropped", {"paths": paths})
        return True

    def log(self, line):
        """Log dari sisi JS (dipanggil pywebview.api.log)."""
        applog.debug("[js] %s" % line)
        return True

    def ping(self):
        return "pong"


def _ffmpeg_ok():
    import shutil
    return shutil.which("ffmpeg") is not None


_install_running = [False]
