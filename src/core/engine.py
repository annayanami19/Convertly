"""Task queue konversi: thread pool + event status ke UI.

api.py memasukkan task; engine menjalankan converter di thread pool.
Converter boleh mem-polling engine.is_cancelled(task_id) untuk cancel.
"""
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import core.settings as settings
import core.registry as registry
from core.converters import images, documents, media
from core.errors import TaskCancelled

_converters = {"images": images, "documents": documents, "media": media}

_tasks = {}
_order = []
_lock = threading.RLock()
_cancelled = set()
_emit = None
_pool = None


def setup(emitter):
    global _emit, _pool
    _emit = emitter
    if _pool is None:
        _pool = ThreadPoolExecutor(max_workers=max(1, settings.load()["workers"]))


def _emit_task(task, status, **extra):
    payload = {
        "id": task["id"],
        "name": os.path.basename(task["src"]),
        "target": task["target"],
        "category": task["category"],
        "status": status,
    }
    payload.update(extra)
    if _emit:
        _emit(payload)


def is_cancelled(tid):
    return tid in _cancelled


def _output_for(task):
    src = task["src"]
    pattern = settings.load()["naming_pattern"]
    name, _ = registry.output_name(src, task["target"], pattern)
    out_dir = settings.resolve_output_dir()  # default 'output convert', auto-create
    dst = os.path.join(out_dir, name)
    # tabrakan sumber = output (mis. png->png pola {name}) → beri suffix
    if os.path.abspath(dst) == os.path.abspath(src):
        base, ext2 = os.path.splitext(dst)
        dst = base + "_converted" + ext2
    return dst


def add_tasks(items):
    """items = [{src, target, options}] — validasi + enqueue.

    Return {added: [...], rejected: [{src, reason}]}.
    """
    added, rejected = [], []
    with _lock:
        for it in items:
            src = it["src"]
            ext = os.path.splitext(src)[1].lower()
            cat = registry.category_of(ext)
            if cat is None:
                rejected.append({"src": src, "reason": "format tidak didukung"})
                continue
            is_pdf_op = (ext == ".pdf" and it["target"] == "pdf"
                         and it.get("options", {}).get("op") in registry.PDF_OPS)
            if it["target"] not in registry.targets_for(ext) and not is_pdf_op:
                rejected.append({"src": src,
                                 "reason": "target ." + it["target"] +
                                           " tidak valid untuk " + ext})
                continue
            need = registry.deps_for_target(cat, it["target"], ext)
            missing = registry.missing_modules(need)
            if cat == "media" and not media.ffmpeg_available():
                missing.append("ffmpeg")
            if missing:
                rejected.append({
                    "src": src,
                    "reason": "paket belum terpasang: " + ", ".join(missing),
                })
                continue
            if not os.path.isfile(src):
                rejected.append({"src": src, "reason": "file tidak ada"})
                continue
            dst = _output_for({"src": src, "target": it["target"]})
            if os.path.abspath(src) == os.path.abspath(dst):
                rejected.append({"src": src, "reason": "sumber = output (dilarang)"})
                continue
            tid = "t%d_%d" % (len(_order), time.time_ns() % 10**9)
            task = {
                "id": tid, "src": src, "target": it["target"],
                "options": it.get("options", {}),
                "category": cat, "status": "queued",
            }
            _tasks[tid] = task
            _order.append(tid)
            added.append(_public_task(task))
    if _pool and added:
        for t in added:
            _pool.submit(_run_task, _tasks[t["id"]])
    return {"added": added, "rejected": rejected}


def _run_task(task):
    tid = task["id"]
    if tid in _cancelled:
        _cancelled.discard(tid)
        with _lock:
            task["status"] = "cancelled"
        _emit_task(task, "cancelled")
        return
    with _lock:
        task["status"] = "running"
    _emit_task(task, "running")

    src = task["src"]
    dst = _output_for(task)
    overwrite = settings.load()["overwrite"]

    def on_prog(pct, note=""):
        _emit_task(task, "progress", progress=pct, note=note)

    try:
        if os.path.exists(dst) and not overwrite:
            raise FileExistsError("output sudah ada (overwrite dimatikan)")
        _converters[task["category"]].convert(src, dst, task["target"],
                                              task["options"], on_prog,
                                              cancel_fn=lambda: is_cancelled(tid))
        with _lock:
            task["status"] = "done"
            task["dst"] = dst
        _emit_task(task, "done", dst=dst)
    except TaskCancelled:
        _cancelled.discard(tid)
        with _lock:
            task["status"] = "cancelled"
        _emit_task(task, "cancelled")
        try:
            os.remove(dst)
        except OSError:
            pass
    except Exception as e:
        with _lock:
            task["status"] = "error"
            task["error"] = str(e)
        _emit_task(task, "error", error=str(e))
        settings.add_history({
            "time": datetime.now().isoformat(timespec="seconds"),
            "src": os.path.basename(src),
            "target": task["target"],
            "dst": dst,
            "status": "error",
            "error": str(e),
        })
        return
    settings.add_history({
        "time": datetime.now().isoformat(timespec="seconds"),
        "src": os.path.basename(src),
        "target": task["target"],
        "dst": dst,
        "status": "done",
    })


def cancel(tid):
    with _lock:
        t = _tasks.get(tid)
        if t is None:
            return False
        if t["status"] in ("queued", "running"):
            _cancelled.add(tid)
    return True


def cancel_all():
    with _lock:
        for tid in _order:
            t = _tasks[tid]
            if t["status"] in ("queued", "running"):
                _cancelled.add(tid)
    return True


def clear_finished():
    with _lock:
        done_ids = [tid for tid in _order
                    if _tasks[tid]["status"] in ("done", "error", "cancelled")]
        removed = 0
        for tid in done_ids:
            del _tasks[tid]
            _order.remove(tid)
            removed += 1
    return {"removed": removed}


def snapshot():
    with _lock:
        return [_public_task(_tasks[tid]) for tid in _order]


def _public_task(task):
    out = {k: task.get(k) for k in
           ("id", "src", "name", "target", "category", "status", "dst", "error",
            "progress")}
    if not out.get("name"):
        out["name"] = os.path.basename(task.get("src", ""))
    return out


def rebuild_pool():
    global _pool
    with _lock:
        _pool.shutdown(wait=False, cancel_futures=True)
        _pool = ThreadPoolExecutor(max_workers=max(1, settings.load()["workers"]))
        for tid in _order:
            if _tasks[tid]["status"] == "queued":
                _pool.submit(_run_task, _tasks[tid])
