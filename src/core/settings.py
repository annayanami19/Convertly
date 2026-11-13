"""Pemuat/penyimpan config.json — dipakai api.py dan settings UI."""
import json
import os
import threading

# src/core/settings.py -> root repo = tiga tingkat ke atas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULTS = {
    "theme": "dark",
    "workers": 2,
    "output_dir": "",           # kosong = folder yang sama dengan file sumber
    "naming_pattern": "{name}",  # {name}, {format}, {date}
    "overwrite": False,
    "default_quality": 85,
    "history": [],              # maks 200 entri terakhir
}

_lock = threading.RLock()  # reentrant: add_history memanggil load+save di dalam lock
_cache = None


def load():
    global _cache
    with _lock:
        if _cache is None:
            data = {}
            if os.path.exists(CONFIG_PATH):
                try:
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except (json.JSONDecodeError, OSError):
                    data = {}  # config korup → mulai dari default, jangan crash
            merged = dict(DEFAULTS)
            merged.update(data)
            # history dibatasi
            if not isinstance(merged["history"], list):
                merged["history"] = []
            _cache = merged
        return dict(_cache)


def save(cfg):
    global _cache
    with _lock:
        _cache = dict(cfg)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(_cache, f, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG_PATH)  # atomik — aman dari config setengah tertulis
    return True


def update(**kwargs):
    cfg = load()
    cfg.update(kwargs)
    save(cfg)
    return cfg


def add_history(entry):
    # atomik: read-modify-write di bawah satu lock (dipanggil worker paralel)
    with _lock:
        cfg = load()
        hist = cfg.get("history", [])
        hist.insert(0, entry)
        cfg["history"] = hist[:200]
        save(cfg)


def clear_history():
    """Kosongkan seluruh riwayat (atomik)."""
    with _lock:
        cfg = load()
        cfg["history"] = []
        save(cfg)
        return dict(cfg)


def resolve_output_dir(cfg=None):
    """Folder output efektif. Default: 'output convert' di folder aplikasi,
    dibuat otomatis bila belum ada. Path relatif dihitung dari folder aplikasi.
    """
    cfg = cfg or load()
    out = (cfg.get("output_dir") or "").strip()
    if out:
        out_path = out if os.path.isabs(out) else os.path.join(BASE_DIR, out)
    else:
        out_path = os.path.join(BASE_DIR, "output convert")
    os.makedirs(out_path, exist_ok=True)
    return out_path


def reset():
    """Kembalikan pengaturan ke default. Riwayat dipertahankan."""
    with _lock:
        cfg = load()
        hist = cfg.get("history", [])
        fresh = dict(DEFAULTS)
        fresh["history"] = hist
        save(fresh)
        return dict(fresh)
