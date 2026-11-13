"""Test suite Convertly — jalankan: venv/Scripts/python.exe tests/run_tests.py

Generate sampel, uji semua jalur konversi gambar/dokumen/media + engine
end-to-end. Tidak butuh window; exit code 0 = semua pass.
"""
import math
import os
import struct
import subprocess
import sys
import time
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)

IN = "tests/tmp_out"

results = []


def run(label, fn):
    try:
        fn()
        results.append(("PASS", label, ""))
    except Exception as e:
        results.append(("FAIL", label, str(e)[:120]))


def prog(*a):
    pass


# ---------- generate sampel ----------
def gen_samples():
    os.makedirs(IN, exist_ok=True)
    from PIL import Image
    Image.new("RGB", (320, 200), (200, 60, 120)).save(f"{IN}/sample.png")
    Image.new("RGB", (320, 200), (60, 120, 200)).save(f"{IN}/sample.jpg")

    from openpyxl import Workbook
    wb = Workbook()
    wb.active.append(["nama", "nilai"])
    wb.active.append(["a", 1])
    wb.save(f"{IN}/sample.xlsx")

    import docx
    d = docx.Document()
    d.add_heading("Judul Doc", level=1)
    d.add_paragraph("Paragraf pertama.")
    d.save(f"{IN}/sample.docx")

    with open(f"{IN}/sample.txt", "w", encoding="utf-8") as f:
        f.write("Baris pertama\n\n# Heading\nIsi teks.\n")
    with open(f"{IN}/sample.md", "w", encoding="utf-8") as f:
        f.write("# Judul\n\nTeks **bold**.\n")
    import csv
    with open(f"{IN}/sample.csv", "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([["x", "y"], ["1", "2"]])

    with wave.open(f"{IN}/tone.wav", "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / 22050)))
            for i in range(22050 * 3 // 2)))

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-shortest",
         f"{IN}/vid.mp4"], check=True, creationflags=flags)


# ---------- uji konversi ----------
def test_converters():
    import core.converters.images as imgs
    import core.converters.documents as docs
    import core.converters.media as media

    run("png->webp", lambda: imgs.convert(f"{IN}/sample.png", f"{IN}/o.webp",
        "webp", {"quality": 80}, prog))
    run("png->png resize+wm", lambda: imgs.convert(f"{IN}/sample.png",
        f"{IN}/o2.png", "png", {"resize_pct": "50", "watermark_text": "T"},
        prog))
    run("jpg->png", lambda: imgs.convert(f"{IN}/sample.jpg", f"{IN}/o.png",
        "png", {}, prog))
    run("png->avif", lambda: imgs.convert(f"{IN}/sample.png", f"{IN}/o.avif",
        "avif", {"quality": 70}, prog))
    run("docx->pdf", lambda: docs.convert(f"{IN}/sample.docx",
        f"{IN}/o.pdf", "pdf", {}, prog))
    run("xlsx->csv", lambda: docs.convert(f"{IN}/sample.xlsx", f"{IN}/o.csv",
        "csv", {}, prog))
    run("csv->xlsx", lambda: docs.convert(f"{IN}/sample.csv", f"{IN}/o.xlsx",
        "xlsx", {}, prog))
    run("txt->pdf", lambda: docs.convert(f"{IN}/sample.txt", f"{IN}/t.pdf",
        "pdf", {}, prog))
    run("md->html", lambda: docs.convert(f"{IN}/sample.md", f"{IN}/o.html",
        "html", {}, prog))
    run("pdf->txt", lambda: docs.convert(f"{IN}/t.pdf", f"{IN}/back.txt",
        "txt", {}, prog))
    run("txt->docx", lambda: docs.convert(f"{IN}/sample.txt", f"{IN}/o.docx",
        "docx", {}, prog))

    if media.ffmpeg_available():
        run("wav->mp3", lambda: media.convert(f"{IN}/tone.wav", f"{IN}/o.mp3",
            "mp3", {"audio_bitrate": "192k"}, prog))
        run("mp4->webm", lambda: media.convert(f"{IN}/vid.mp4", f"{IN}/o.webm",
            "webm", {}, prog))
        run("mp4->mp3 extract", lambda: media.convert(f"{IN}/vid.mp4",
            f"{IN}/oa.mp3", "mp3", {}, prog))
        run("mp4->mp4 trim", lambda: media.convert(f"{IN}/vid.mp4",
            f"{IN}/ot.mp4", "mp4", {"trim_start": "0.5", "trim_end": "1.5",
                                    "crf": "30"}, prog))
    else:
        print("SKIP media (ffmpeg tidak ada)")

    content = open(f"{IN}/back.txt", encoding="utf-8").read()
    run("pdf->txt konten", lambda: (_ for _ in ()).throw(
        AssertionError("teks hilang")) if "Heading" not in content else None)


def test_engine():
    import core.engine as engine

    events = []
    engine.setup(lambda p: events.append(p))
    # bersihkan output lama supaya overwrite tidak mengganggu
    for f in ("sample.webp", "sample_converted.png"):
        p = os.path.join(IN, f)
        if os.path.exists(p):
            os.remove(p)

    res = engine.add_tasks([
        {"src": f"{IN}/sample.png", "target": "webp", "options": {}},
        {"src": f"{IN}/sample.png", "target": "exe", "options": {}},   # invalid
        {"src": f"{IN}/tidakada.png", "target": "png", "options": {}},  # tidak ada
    ])
    run("add_tasks reject invalid", lambda: (_ for _ in ()).throw(
        AssertionError("reject salah"))
        if not (len(res["added"]) == 1 and len(res["rejected"]) == 2) else None)

    deadline = time.time() + 60
    while time.time() < deadline:
        snap = engine.snapshot()
        if all(t["status"] in ("done", "error", "cancelled") for t in snap):
            break
        time.sleep(0.2)
    run("engine webp done", lambda: (_ for _ in ()).throw(
        AssertionError(str(engine.snapshot())))
        if not any(t["status"] == "done" and t["target"] == "webp"
                   for t in engine.snapshot()) else None)
    run("progress event", lambda: (_ for _ in ()).throw(
        AssertionError("tidak ada")) if not events else None)


if __name__ == "__main__":
    gen_samples()
    test_converters()
    test_engine()
    fails = 0
    for st, label, err in results:
        print(st, label, err)
        fails += st == "FAIL"
    print("TOTAL:", len(results), "FAIL:", fails)
    sys.exit(1 if fails else 0)
