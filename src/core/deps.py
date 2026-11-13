"""Dependency manager: cek paket per fitur + install via pip dari dalam aplikasi.

Fitur yang dependensinya belum terpasang → converter-nya disabled sampai user
mengklik Install (panel Dependencies). App tidak pernah meng-install otomatis.
"""
import importlib.util
import shutil
import subprocess
import sys
import threading

# feature_key → daftar paket penunjang. Paket WAJIB fitur itu ada di requirements.txt
# juga (di-install start.bat); pengecekan in-app untuk kasus venv rusak/user hapus.
FEATURE_DEPS = {
    "images": [
        {"module": "PIL", "pip": "Pillow", "required": True},
        {"module": "pillow_avif", "pip": "pillow-avif-plugin", "required": False,
         "label": "AVIF"},
        {"module": "pillow_heif", "pip": "pillow-heif", "required": False,
         "label": "HEIC/HEIF"},
    ],
    "documents": [
        {"module": "pymupdf", "pip": "PyMuPDF", "required": True},
        {"module": "docx", "pip": "python-docx", "required": False, "label": "DOCX"},
        {"module": "openpyxl", "pip": "openpyxl", "required": False, "label": "XLSX"},
        {"module": "pptx", "pip": "python-pptx", "required": False, "label": "PPTX"},
        {"module": "markdown", "pip": "markdown", "required": False, "label": "Markdown"},
    ],
    "media": [
        # ffmpeg binary eksternal — tidak bisa lewat pip
        {"module": None, "pip": None, "required": True, "label": "ffmpeg",
         "binary": "ffmpeg"},
    ],
}

_status = None
_lock = threading.Lock()


def _check_package(pkg):
    if pkg.get("binary"):
        path = shutil.which(pkg["binary"])
        return {**pkg, "installed": bool(path), "path": path or ""}
    spec = importlib.util.find_spec(pkg["module"])
    installed = spec is not None
    version = ""
    if installed:
        mod = importlib.import_module(pkg["module"])
        version = getattr(mod, "__version__", "") or ""
    return {**pkg, "installed": installed, "version": version}


def check(refresh=False):
    """Return {feature: {ready, required_missing, packages: [...]}}."""
    global _status
    with _lock:
        if _status is None or refresh:
            _status = {}
            for feature, pkgs in FEATURE_DEPS.items():
                results = [_check_package(p) for p in pkgs]
                required_missing = [p["pip"] or p["label"]
                                    for p in results
                                    if p["required"] and not p["installed"]]
                _status[feature] = {
                    "ready": not required_missing,
                    "required_missing": required_missing,
                    "packages": results,
                }
        return {k: {**v, "packages": list(v["packages"])} for k, v in _status.items()}


def invalidate():
    """Paksa cek ulang saat pemanggilan check() berikutnya."""
    global _status
    with _lock:
        _status = None


def install(packages, on_output=None, on_done=None):
    """Jalankan pip install di thread terpisah. packages = daftar nama pip.

    on_output(line) dipanggil per baris output; on_done(returncode) di akhir.
    """
    def _worker():
        cmd = [sys.executable, "-m", "pip", "install", *packages]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line and on_output:
                on_output(line)
        code = proc.wait()
        invalidate()
        if on_done:
            on_done(code)

    threading.Thread(target=_worker, daemon=True).start()
