"""Registry: mapping ekstensi → kategori, dan matriks konversi per kategori.

Semua import berat dilakukan LAZY (di dalam fungsi) supaya startup <1 detik.
"""
import os

# --- Ekstensi → kategori ---
EXT_CATEGORIES = {
    # gambar
    ".png": "images", ".jpg": "images", ".jpeg": "images", ".webp": "images",
    ".gif": "images", ".bmp": "images", ".tiff": "images", ".tif": "images",
    ".ico": "images", ".avif": "images", ".heic": "images", ".heif": "images",
    # dokumen
    ".pdf": "documents", ".docx": "documents", ".xlsx": "documents",
    ".pptx": "documents", ".txt": "documents", ".md": "documents",
    ".html": "documents", ".htm": "documents", ".csv": "documents",
    # media — semua ditangani ffmpeg; diisi dinamis lewat is_media()
    ".mp3": "media", ".wav": "media", ".flac": "media", ".ogg": "media",
    ".m4a": "media", ".aac": "media", ".wma": "media", ".opus": "media",
    ".mp4": "media", ".mkv": "media", ".webm": "media", ".mov": "media",
    ".avi": "media", ".flv": "media", ".wmv": "media", ".m4v": "media",
    ".ts": "media", ".3gp": "media", ".ogv": "media",
}

IMAGE_TARGETS = ["png", "jpg", "webp", "avif", "gif", "bmp", "tiff", "ico"]
DOC_TARGETS = ["pdf", "txt", "md", "html", "csv", "docx", "xlsx", "pptx"]
MEDIA_TARGETS = {
    "audio": ["mp3", "wav", "flac", "ogg", "m4a", "aac", "opus"],
    "video": ["mp4", "mkv", "webm", "mov", "avi", "gif"],
}

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus"}
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".wmv", ".m4v",
              ".ts", ".3gp", ".ogv"}

# Matriks dokumen: source → target yang realistis (konversi berbasis teks)
DOC_MATRIX = {
    ".pdf": ["txt", "md"],
    ".docx": ["txt", "md", "html", "pdf"],
    ".xlsx": ["csv", "html", "pdf"],
    ".csv": ["xlsx", "html", "pdf"],
    ".pptx": ["txt", "pdf"],
    ".txt": ["pdf", "md", "html", "docx"],
    ".md": ["html", "txt", "docx", "pdf"],
    ".html": ["txt", "md", "pdf"],
}

PDF_OPS = ["merge", "split", "rotate", "compress", "extract_text"]


def category_of(ext):
    return EXT_CATEGORIES.get(ext.lower())


def is_media(ext):
    return EXT_CATEGORIES.get(ext.lower()) == "media"


def targets_for(ext):
    """Daftar format target yang VALID untuk ekstensi (tanpa cek dependensi)."""
    ext = ext.lower()
    cat = EXT_CATEGORIES.get(ext)
    if cat == "images":
        # format sama tetap valid (use case: resize/watermark/kompresi)
        # HEIC hanya jadi sumber (decode-only), bukan target
        return [t for t in IMAGE_TARGETS if not (t == "heic")]
    if cat == "documents":
        return DOC_MATRIX.get(ext, [])
    if cat == "media":
        # format sama tetap valid (use case: trim, kompresi ulang)
        if ext in AUDIO_EXTS:
            return list(MEDIA_TARGETS["audio"])  # audio tidak jadi video
        # video → video + audio (use case: extract audio)
        return list(MEDIA_TARGETS["video"]) + list(MEDIA_TARGETS["audio"])
    return []


# module → nama pip-nya (untuk pesan "install dulu")
MODULE_PIP = {
    "PIL": "Pillow", "pillow_avif": "pillow-avif-plugin",
    "pillow_heif": "pillow-heif", "pymupdf": "PyMuPDF", "fitz": "PyMuPDF",
    "docx": "python-docx", "openpyxl": "openpyxl", "pptx": "python-pptx",
    "markdown": "markdown",
}


def missing_modules(modules):
    """Dari daftar nama module, kembalikan yang belum terpasang (nama pip)."""
    import importlib.util
    missing = []
    for m in modules:
        try:
            if importlib.util.find_spec(m) is None:
                missing.append(MODULE_PIP.get(m, m))
        except (ImportError, ValueError):
            missing.append(MODULE_PIP.get(m, m))
    return missing


def deps_for_target(category, target, src_ext=""):
    """Daftar pip-package yang DIBUTUHKAN untuk (kategori, target, sumber)."""
    ext = src_ext.lower()
    if category == "images":
        need = ["PIL"]
        if target == "avif":
            need.append("pillow_avif")
        return need
    if category == "documents":
        need = []
        if target == "pdf" or ext == ".pdf":
            # sumber .pdf selalu butuh pymupdf (termasuk op merge/split/
            # rotate/compress/extract_text, dan pdf -> txt/md)
            need.append("pymupdf")
        if ext == ".docx" or target == "docx":
            need.append("docx")
        if ext == ".xlsx" or target == "xlsx":
            need.append("openpyxl")
        if ext == ".pptx":
            need.append("pptx")
        if target == "md" or ext == ".md":
            need.append("markdown")
        return need
    return []  # media: dicek via shutil.which("ffmpeg") di converter


def output_name(src_path, target, pattern="{name}", overwrite=False):
    """Nama file output dari pola penamaan. Return (path, exists)."""
    import re
    base = os.path.splitext(os.path.basename(src_path))[0]
    date = __import__("datetime").date.today().isoformat()
    name = (pattern.replace("{name}", base)
            .replace("{format}", target)
            .replace("{date}", date))
    # pola bebas dari user — buang karakter yang ilegal untuk nama file
    name = re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "output"
    return f"{name}.{target}", os.path.exists(f"{name}.{target}")
