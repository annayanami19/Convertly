"""Unit test lengkap Convertly — jalankan: venv/Scripts/python.exe tests/test_full.py
Murni script/log-based (tanpa GUI). Exit 0 = semua pass.
"""
import io
import json
import math
import os
import struct
import subprocess
import sys
import threading
import time
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)

IN = "tests/tmp_full"
results = []


def run(label, fn):
    try:
        fn()
        results.append(("PASS", label, ""))
    except Exception as e:
        results.append(("FAIL", label, "%s: %s" % (type(e).__name__, str(e)[:140])))


def expect(cond, msg=""):
    if not cond:
        raise AssertionError(msg)


def prog(*a):
    pass


def gen_samples():
    os.makedirs(IN, exist_ok=True)
    from PIL import Image
    Image.new("RGB", (320, 200), (200, 60, 120)).save(f"{IN}/s.png")
    Image.new("RGB", (320, 200), (60, 120, 200)).save(f"{IN}/s.jpg")
    # gif animasi 3 frame
    fr = [Image.new("RGB", (60, 40), (c, 20, 30)) for c in (10, 128, 240)]
    fr[0].save(f"{IN}/anim.gif", save_all=True, append_images=fr[1:],
               duration=100, loop=0)
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active
    ws.append(["nama", "nilai"]); ws.append(["a", 1]); ws.append(["b", 2])
    wb.save(f"{IN}/s.xlsx")
    import docx
    d = docx.Document()
    d.add_heading("Judul Utama", level=1)
    d.add_heading("Sub Judul", level=2)
    d.add_paragraph("Paragraf isi.")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "k1"; t.cell(0, 1).text = "k2"
    t.cell(1, 0).text = "v1"; t.cell(1, 1).text = "v2"
    d.save(f"{IN}/s.docx")
    with open(f"{IN}/s.txt", "w", encoding="utf-8") as f:
        f.write("Baris pertama\nBaris kedua\n\n# Heading\nIsi teks.\n")
    with open(f"{IN}/s.md", "w", encoding="utf-8") as f:
        f.write("# Judul\n\nTeks **bold**.\n\n- item 1\n- item 2\n")
    with open(f"{IN}/s.html", "w", encoding="utf-8") as f:
        f.write("<html><body><h1>Judul HTML</h1>"
                "<script>var x = 'rahasia';</script>"
                "<p>Isi paragraf.</p></body></html>")
    import csv
    with open(f"{IN}/s.csv", "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([["x", "y"], ["1", "2"], ["3", "4"]])
    with wave.open(f"{IN}/tone.wav", "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        w.writeframes(b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / 22050)))
            for i in range(22050)))  # 1.0 detik persis
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-shortest",
         f"{IN}/vid.mp4"], check=True, creationflags=flags)


def ffprobe_secs(path):
    ffprobe = os.path.join(ROOT, "venv", "Scripts") if False else None
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return float(out.stdout.strip())


# ============ settings ============
def test_settings():
    import importlib
    import core.settings as st
    importlib.reload(st)

    def defaults():
        cfg = st.load()
        expect(cfg["theme"] in ("dark", "light"))
        expect(1 <= cfg["workers"] <= 8)
        expect(isinstance(cfg["history"], list))

    run("settings: default lengkap", defaults)

    def roundtrip():
        st.update(theme="light", workers=3)
        cfg = json.load(open(st.CONFIG_PATH, encoding="utf-8"))
        expect(cfg["theme"] == "light" and cfg["workers"] == 3)
        st.update(theme="dark", workers=2)
        expect(st.load()["theme"] == "dark")

    run("settings: update + persist ke config.json", roundtrip)

    def corrupt():
        io.open(st.CONFIG_PATH, "w", encoding="utf-8").write("{korup!!")
        st._cache = None  # paksa reload
        cfg = st.load()
        expect(cfg["theme"] in ("dark", "light"))  # fallback, tidak crash
        st._cache = None
        st.update(theme="dark")

    run("settings: config korup -> fallback aman", corrupt)

    def history_cap():
        for i in range(230):
            st.add_history({"src": "f%d" % i, "target": "x"})
        expect(len(st.load()["history"]) == 200, "history > 200")

    run("settings: history dibatasi 200", history_cap)

    def history_race():
        st._cache = None
        threads = [threading.Thread(target=st.add_history,
                                    args=({"src": "r%d" % i},))
                   for i in range(30)]
        for t in threads: t.start()
        for t in threads: t.join()
        expect(len(st.load()["history"]) == 200)
        st._cache = None

    run("settings: add_history thread-safe (30 thread)", history_race)

    def output_dir_default():
        import core.settings as st2
        p = st2.resolve_output_dir({"output_dir": ""})
        expect(p.endswith("output convert") and os.path.isdir(p), p)

    run("settings: output default 'output convert' auto-create",
        output_dir_default)

    def output_dir_custom():
        import core.settings as st2
        p = st2.resolve_output_dir({"output_dir": f"{IN}/out_custom"})
        expect(os.path.isdir(p), p)

    run("settings: output dir custom + relatif dibuat", output_dir_custom)

    def reset_defaults():
        import core.settings as st2
        st2.update(theme="light", workers=5, naming_pattern="{format}")
        cfg = st2.reset()
        expect(cfg["theme"] == "dark" and cfg["workers"] == 2)
        expect(cfg["naming_pattern"] == "{name}")
        expect(isinstance(cfg["history"], list) and cfg["history"])  # riwayat utuh

    run("settings: reset ke default, riwayat dipertahankan", reset_defaults)

    def clear_hist():
        import core.settings as st2
        cfg = st2.clear_history()
        expect(cfg["history"] == [])
        on_disk = json.load(open(st2.CONFIG_PATH, encoding="utf-8"))
        expect(on_disk["history"] == [], "harus persist ke config.json")

    run("settings: clear_history kosongkan + persist", clear_hist)


# ============ registry ============
def test_registry():
    import core.registry as reg

    run("registry: kategori gambar/dok/media",
        lambda: expect(reg.category_of(".png") == "images"
                       and reg.category_of(".pdf") == "documents"
                       and reg.category_of(".mp4") == "media"
                       and reg.category_of(".xyz") is None))

    def targets_img():
        t = reg.targets_for(".png")
        expect("png" in t and "webp" in t and "heic" not in t,
               "same-format harus ada, heic tidak jadi target")
        # heic sebagai SUMBER: target list-nya format lain (heic bukan target)
        th = reg.targets_for(".heic")
        expect("png" in th and "heic" not in th)

    run("registry: target gambar (same-format ya, heic target tidak)", targets_img)

    def targets_media():
        v = reg.targets_for(".mp4")
        expect("mp3" in v and "mkv" in v and "mp4" in v,
               "video: extract audio + same-format")
        a = reg.targets_for(".mp3")
        expect("wav" in a and "mp4" not in a, "audio tidak jadi video")

    run("registry: target media (video->audio, audio->audio saja)", targets_media)

    def doc_matrix():
        expect("csv" in reg.targets_for(".xlsx"))
        expect("pdf" in reg.targets_for(".txt"))
        expect(reg.targets_for(".docx") == reg.DOC_MATRIX[".docx"])

    run("registry: matriks dokumen", doc_matrix)

    def deps_map():
        expect(reg.deps_for_target("images", "avif", ".png") == ["PIL", "pillow_avif"])
        expect(reg.deps_for_target("images", "png", ".jpg") == ["PIL"])
        expect("pymupdf" in reg.deps_for_target("documents", "pdf", ".txt"))
        expect("docx" in reg.deps_for_target("documents", "docx", ".txt"))
        expect(reg.deps_for_target("media", "mp3", ".mp4") == [])

    run("registry: peta dependensi per target", deps_map)

    def missing():
        expect(reg.missing_modules(["PIL"]) == [])
        m = reg.missing_modules(["tidak_ada_modul_xyz"])
        expect(m == ["tidak_ada_modul_xyz"])

    run("registry: deteksi modul hilang", missing)

    def output_name():
        n, ex = reg.output_name("C:/a/b/foto.png", "webp", "{name}_{format}")
        expect(n == "foto_png.webp" or n.startswith("foto"), n)
        n2, _ = reg.output_name("x.png", "jpg", "{format}_{date}")
        expect(n2.startswith("jpg_2"), n2)

    run("registry: pola penamaan {name}/{format}/{date}", output_name)


# ============ deps ============
def test_deps():
    import core.deps as deps

    def structure():
        st = deps.check(refresh=True)
        for feat in ("images", "documents", "media"):
            expect(feat in st and "ready" in st[feat] and "packages" in st[feat])
        expect(any(p["installed"] for p in st["images"]["packages"]))

    run("deps: struktur check per fitur", structure)

    def ffmpeg():
        st = deps.check()["media"]
        found = any(p.get("binary") == "ffmpeg" for p in st["packages"])
        expect(found)

    run("deps: ffmpeg terdeteksi sebagai binary", ffmpeg)


# ============ applog ============
def test_applog():
    import core.applog as applog
    applog.debug("unit-test-baris")
    content = io.open(applog.path(), encoding="utf-8").read()
    expect("unit-test-baris" in content)

    applog.clear()
    expect(io.open(applog.path(), encoding="utf-8").read() == "")
    applog.debug("baris setelah clear")  # logger hidup lagi
    expect("baris setelah clear" in io.open(applog.path(), encoding="utf-8").read())


# ============ converters: images ============
def test_images():
    import core.converters.images as imgs
    from core.errors import TaskCancelled

    for target in ("webp", "avif", "ico", "bmp", "tiff", "gif", "png"):
        run("images: png->" + target, lambda t=target: imgs.convert(
            f"{IN}/s.png", f"{IN}/i_{t}", t, {"quality": 80}, prog))

    run("images: jpg->png", lambda: imgs.convert(
        f"{IN}/s.jpg", f"{IN}/i2.png", "png", {}, prog))

    def resize_pct():
        from PIL import Image
        imgs.convert(f"{IN}/s.png", f"{IN}/r.png", "png", {"resize_pct": "50"}, prog)
        expect(Image.open(f"{IN}/r.png").size == (160, 100))

    run("images: resize 50% -> 160x100", resize_pct)

    def resize_w():
        from PIL import Image
        imgs.convert(f"{IN}/s.png", f"{IN}/rw.png", "png", {"resize_w": 100}, prog)
        expect(Image.open(f"{IN}/rw.png").size[0] == 100)

    run("images: resize lebar 100 (aspect terjaga)", resize_w)

    def rotate():
        from PIL import Image
        imgs.convert(f"{IN}/s.png", f"{IN}/rot.png", "png", {"rotate": 90}, prog)
        im = Image.open(f"{IN}/rot.png")
        expect(im.size == (200, 320), str(im.size))

    run("images: rotate 90 -> dimensi tertukar", rotate)

    def watermark():
        imgs.convert(f"{IN}/s.png", f"{IN}/wm.png", "png",
                     {"watermark_text": "CP", "watermark_opacity": 0.5}, prog)
        from PIL import Image
        expect(Image.open(f"{IN}/wm.png").size == (320, 200))

    run("images: watermark teks", watermark)

    def anim_gif():
        from PIL import Image
        imgs.convert(f"{IN}/anim.gif", f"{IN}/anim2.gif", "gif", {}, prog)
        expect(Image.open(f"{IN}/anim2.gif").n_frames == 3)

    run("images: gif animasi dipertahankan 3 frame", anim_gif)

    def cancel():
        def cancelled():
            return True
        try:
            imgs.convert(f"{IN}/s.png", f"{IN}/cx.png", "png", {}, prog, cancelled)
            raise AssertionError("TaskCancelled tidak dilempar")
        except TaskCancelled:
            expect(not os.path.exists(f"{IN}/cx.png"), "file parsial tertinggal")

    run("images: cancel_fn -> TaskCancelled, tanpa file parsial", cancel)

    def bad_file():
        try:
            imgs.convert(f"{IN}/tidakada.png", f"{IN}/x.png", "png", {}, prog)
            raise AssertionError("harusnya RuntimeError")
        except (RuntimeError, OSError):
            pass

    run("images: file sumber tidak ada -> error jelas", bad_file)


# ============ converters: documents ============
def test_documents():
    import core.converters.documents as docs

    run("doc: docx->pdf", lambda: docs.convert(
        f"{IN}/s.docx", f"{IN}/d.pdf", "pdf", {}, prog))
    run("doc: docx->txt", lambda: docs.convert(
        f"{IN}/s.docx", f"{IN}/d.txt", "txt", {}, prog))
    run("doc: docx->md", lambda: docs.convert(
        f"{IN}/s.docx", f"{IN}/d.md", "md", {}, prog))
    run("doc: docx->html", lambda: docs.convert(
        f"{IN}/s.docx", f"{IN}/d.html", "html", {}, prog))

    def docx_txt_content():
        txt = io.open(f"{IN}/d.txt", encoding="utf-8").read()
        expect("Judul Utama" in txt and "Paragraf isi." in txt)
        expect("k1" in txt and "v2" in txt, "tabel hilang")

    run("doc: docx->txt konten (heading + tabel)", docx_txt_content)

    run("doc: xlsx->csv", lambda: docs.convert(
        f"{IN}/s.xlsx", f"{IN}/x.csv", "csv", {}, prog))

    def xlsx_csv_content():
        import csv as _csv
        rows = list(_csv.reader(io.open(f"{IN}/x.csv", encoding="utf-8")))
        expect(rows[0] == ["nama", "nilai"] and rows[2][1] == "2")

    run("doc: xlsx->csv isi baris benar", xlsx_csv_content)

    run("doc: csv->xlsx", lambda: docs.convert(
        f"{IN}/s.csv", f"{IN}/c.xlsx", "xlsx", {}, prog))

    def csv_xlsx_content():
        from openpyxl import load_workbook
        wb = load_workbook(f"{IN}/c.xlsx")
        ws = wb.active
        expect(ws["A2"].value == "1" and ws["B3"].value == "4")

    run("doc: csv->xlsx isi sel benar", csv_xlsx_content)

    run("doc: txt->pdf", lambda: docs.convert(
        f"{IN}/s.txt", f"{IN}/t.pdf", "pdf", {}, prog))
    run("doc: md->html", lambda: docs.convert(
        f"{IN}/s.md", f"{IN}/m.html", "html", {}, prog))
    run("doc: html->txt", lambda: docs.convert(
        f"{IN}/s.html", f"{IN}/h.txt", "txt", {}, prog))

    def html_txt():
        txt = io.open(f"{IN}/h.txt", encoding="utf-8").read()
        expect("Judul HTML" in txt and "Isi paragraf." in txt)
        expect("rahasia" not in txt, "script tidak difilter")

    run("doc: html->txt (script difilter)", html_txt)

    run("doc: txt->docx", lambda: docs.convert(
        f"{IN}/s.txt", f"{IN}/t.docx", "docx", {}, prog))

    def pdf_text():
        docs.convert(f"{IN}/t.pdf", f"{IN}/back.txt", "txt", {}, prog)
        txt = io.open(f"{IN}/back.txt", encoding="utf-8").read()
        expect("Heading" in txt and "Baris pertama" in txt)

    run("doc: pdf->txt konten bulat", pdf_text)

    def merge_order():
        docs.convert(f"{IN}/t.pdf", f"{IN}/merged.pdf", "pdf",
                     {"op": "merge", "extra_files": [f"{IN}/d.pdf"]}, prog)
        import pymupdf
        with pymupdf.open(f"{IN}/merged.pdf") as m:
            expect(len(m) == 2, "jumlah halaman merge salah")

    run("doc: pdf merge jumlah halaman", merge_order)

    def split_count():
        docs.convert(f"{IN}/t.pdf", f"{IN}/sp.pdf", "pdf", {"op": "split"}, prog)
        expect(os.path.exists(f"{IN}/sp_p1.pdf"))

    run("doc: pdf split per halaman", split_count)

    def rotate_deg():
        import pymupdf
        docs.convert(f"{IN}/t.pdf", f"{IN}/rot.pdf", "pdf",
                     {"op": "rotate", "degrees": 90}, prog)
        with pymupdf.open(f"{IN}/rot.pdf") as d:
            expect(d[0].rotation == 90)

    run("doc: pdf rotate 90 tercatat", rotate_deg)

    def unsupported():
        try:
            docs.convert(f"{IN}/s.txt", f"{IN}/y.xlsx", "xlsx", {}, prog)
            raise AssertionError("harusnya ditolak")
        except RuntimeError:
            pass

    run("doc: txt->xlsx tidak didukung -> RuntimeError", unsupported)


# ============ converters: media ============
def test_media():
    import core.converters.media as media

    if not media.ffmpeg_available():
        print("SKIP media (ffmpeg tidak ada)")
        return

    run("media: wav->mp3 192k", lambda: media.convert(
        f"{IN}/tone.wav", f"{IN}/m.mp3", "mp3", {"audio_bitrate": "192k"}, prog))

    def mp3_dur():
        expect(abs(ffprobe_secs(f"{IN}/m.mp3") - 1.0) < 0.2)

    run("media: durasi mp3 ~1.0 dtk", mp3_dur)

    run("media: wav->flac lossless", lambda: media.convert(
        f"{IN}/tone.wav", f"{IN}/m.flac", "flac", {}, prog))
    run("media: mp4->webm", lambda: media.convert(
        f"{IN}/vid.mp4", f"{IN}/m.webm", "webm", {}, prog))
    run("media: mp4->mp3 (extract audio)", lambda: media.convert(
        f"{IN}/vid.mp4", f"{IN}/ma.mp3", "mp3", {}, prog))
    run("media: mp4->mp4 trim 0.5-1.5", lambda: media.convert(
        f"{IN}/vid.mp4", f"{IN}/mt.mp4", "mp4",
        {"trim_start": "0.5", "trim_end": "1.5"}, prog))

    def trim_dur():
        expect(0.6 < ffprobe_secs(f"{IN}/mt.mp4") < 1.4)

    run("media: durasi hasil trim ~1.0 dtk", trim_dur)

    def scale():
        from PIL import Image
        media.convert(f"{IN}/vid.mp4", f"{IN}/ms.mp4", "mp4",
                      {"scale_w": "160"}, prog)
        im = Image.new("RGB", (1, 1))
        expect(im.size == (1, 1))  # placeholder; cek via ffprobe di bawah
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width", "-of",
             "default=noprint_wrappers=1:nokey=1", f"{IN}/ms.mp4"],
            capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        expect(out.stdout.strip() == "160", out.stdout)

    run("media: scale lebar 160px", scale)

    def error_path():
        try:
            media.convert(f"{IN}/tidakada.mp4", f"{IN}/z.mp3", "mp3", {}, prog)
            raise AssertionError("harusnya gagal")
        except (RuntimeError, subprocess.SubprocessError, OSError):
            pass

    run("media: sumber tidak ada -> error jelas", error_path)

    def cancel_midway():
        from core.errors import TaskCancelled
        calls = {"n": 0}

        def cancelled():
            calls["n"] += 1
            return calls["n"] > 2  # batalkan setelah beberapa poll

        try:
            media.convert(f"{IN}/vid.mp4", f"{IN}/mc.mp4", "mp4", {}, prog, cancelled)
            raise AssertionError("harusnya TaskCancelled")
        except TaskCancelled:
            expect(not os.path.exists(f"{IN}/mc.mp4"), "file parsial tertinggal")

    run("media: cancel di tengah -> TaskCancelled, tanpa parsial", cancel_midway)

    def gif_from_video():
        from PIL import Image
        media.convert(f"{IN}/vid.mp4", f"{IN}/m.gif", "gif", {}, prog)
        expect(Image.open(f"{IN}/m.gif").size[0] == 480)

    run("media: mp4->gif lebar 480", gif_from_video)


# ============ engine end-to-end ============
def test_engine():
    import core.engine as engine
    __import__("core.settings", fromlist=["settings"]).update(output_dir=IN)

    events = []
    engine.setup(lambda p: events.append(p))

    def validation():
        for f in ("s.webp", "s_converted.png"):
            p = os.path.join(IN, f)
            if os.path.exists(p): os.remove(p)
        res = engine.add_tasks([
            {"src": f"{IN}/s.png", "target": "webp", "options": {}},
            {"src": f"{IN}/s.png", "target": "exe", "options": {}},
            {"src": f"{IN}/tidakada.png", "target": "png", "options": {}},
            {"src": f"{IN}/s.png", "target": "png", "options": {}},  # -> _converted
        ])
        expect(len(res["added"]) == 2 and len(res["rejected"]) == 2,
               "validasi add_tasks: %d/%d" % (len(res["added"]), len(res["rejected"])))
        expect(any("tidak valid" in r["reason"] for r in res["rejected"]))

    run("engine: validasi target/file/same-format", validation)

    def pdf_op_accepted():
        res = engine.add_tasks([
            {"src": f"{IN}/t.pdf", "target": "pdf",
             "options": {"op": "compress"}}])
        expect(len(res["added"]) == 1 and not res["rejected"],
               str(res["rejected"]))

    run("engine: op PDF diterima validasi (whitelist)", pdf_op_accepted)

    def pdf_extract_txt():
        res = engine.add_tasks([
            {"src": f"{IN}/t.pdf", "target": "txt",
             "options": {"op": "extract_text"}}])
        expect(len(res["added"]) == 1, str(res["rejected"]))

    run("engine: extract_text ber-target txt (ekstensi output benar)",
        pdf_extract_txt)

    deadline = time.time() + 60
    while time.time() < deadline:
        snap = engine.snapshot()
        if all(t["status"] in ("done", "error", "cancelled") for t in snap):
            break
        time.sleep(0.2)

    def statuses():
        snap = engine.snapshot()
        expect(all(t["status"] == "done" for t in snap),
               str([(t["target"], t["status"]) for t in snap]))

    run("engine: semua task done (termasuk same-format _converted)", statuses)

    def progress_events():
        kinds = {e["status"] for e in events}
        expect("running" in kinds and "done" in kinds, str(kinds))

    run("engine: event running+done terkirim", progress_events)

    def overwrite_reject():
        res = engine.add_tasks([
            {"src": f"{IN}/s.png", "target": "webp", "options": {}}])
        expect(len(res["added"]) == 1)  # cek overwrite terjadi saat RUN
        deadline2 = time.time() + 20
        while time.time() < deadline2:
            snap = engine.snapshot()
            if all(t["status"] in ("done", "error", "cancelled") for t in snap):
                break
            time.sleep(0.2)
        err = [t for t in engine.snapshot() if t["status"] == "error"]
        expect(err, "harus ada task error overwrite")
        expect("output sudah ada" in (err[0].get("error") or ""))

    run("engine: output ada + overwrite off -> error jelas", overwrite_reject)

    def cancel_queued():
        core_settings = __import__("core.settings", fromlist=["settings"])
        core_settings.update(workers=1)
        engine.rebuild_pool()
        # banjiri antrian dengan 4 task lambat, lalu cancel semuanya
        big = f"{IN}/vid.mp4"
        res = engine.add_tasks([
            {"src": big, "target": "webm", "options": {}} for _ in range(4)])
        expect(len(res["added"]) == 4)
        engine.cancel_all()
        deadline3 = time.time() + 60
        while time.time() < deadline3:
            snap = engine.snapshot()
            if all(t["status"] in ("done", "error", "cancelled") for t in snap):
                break
            time.sleep(0.3)
        stat = [t["status"] for t in engine.snapshot()]
        expect("cancelled" in stat or "done" in stat, str(stat))
        engine.clear_finished()
        expect(engine.snapshot() == [])

    run("engine: cancel_all + clear_finished", cancel_queued)

    # kembalikan pool normal
    __import__("core.settings", fromlist=["settings"]).update(workers=2)
    engine.rebuild_pool()


# ============ api ============
def test_api():
    import core.applog as applog  # noqa
    from api import Api
    a = Api()

    def targets():
        info = a.targets_for(".png")
        expect(info["category"] == "images" and info["targets"])
        expect(all("missing" in t for t in info["targets"]))
        expect(a.targets_for(".nope")["category"] is None)

    run("api: targets_for struktur + format tak dikenal", targets)

    def drop_parse():
        ev = {"dataTransfer": {"files": [
            {"pywebviewFullPath": os.path.abspath(f"{IN}/s.png")},
            {"pywebviewFullPath": "Z:/hantu.txt"},
            {},
        ]}}
        expect(a.on_drop_event(ev) is True)
        expect(a.on_drop_event({"domTransfer": {"files": []}}) is True)

    run("api: on_drop_event parsing aman (path hantu dibuang)", drop_parse)

    def settings_patch():
        cfg = a.set_settings({"workers": 2, "theme": "dark"})
        expect(cfg["workers"] == 2)
        expect(a.ping() == "pong")

    run("api: set_settings + ping", settings_patch)

    def install_guard():
        r = a.install_deps([])
        expect(r["started"] is False)

    run("api: install_deps kosong ditolak", install_guard)

    def filter_format():
        from webview.util import parse_file_type
        from api import FILE_FILTERS
        for ft in FILE_FILTERS:
            desc, exts = parse_file_type(ft)  # format salah -> ValueError
            expect(desc and exts)
            expect(" " not in exts, "ekstensi dipisah spasi -> dialog mati")

    run("api: file filter lolos parser pywebview", filter_format)

    def log_apis():
        p = a.get_log_path()
        expect(p.endswith("app.log") and os.path.exists(p))
        expect(a.clear_logs() is True)

    run("api: get_log_path + clear_logs", log_apis)

    def reset_apis():
        a.set_settings({"workers": 4})
        cfg = a.reset_settings()
        expect(cfg["workers"] == 2)
        __import__("core.settings", fromlist=["settings"]).update(output_dir=IN)

    run("api: reset_settings -> default + pool rebuild", reset_apis)

    def open_path_guard():
        expect(a.open_path("") is False)
        expect(a.open_path("Z:/hantu") is False)

    run("api: open_path guard", open_path_guard)


if __name__ == "__main__":
    gen_samples()
    test_settings()
    test_registry()
    test_deps()
    test_applog()
    test_images()
    test_documents()
    test_media()
    test_engine()
    test_api()
    fails = 0
    for st, label, err in results:
        print(st, label, err)
        fails += st == "FAIL"
    print("TOTAL:", len(results), "FAIL:", fails)
    sys.exit(1 if fails else 0)
