"""Converter gambar via Pillow — convert format, resize, kompresi, watermark,
rotate/flip. HEIC/AVIF via plugin lazy-import (deps.py yang mengecek).
"""
import os

from PIL import Image

# Plugin decode opsional — diimport bila ada, abaikan bila tidak
try:
    import pillow_avif  # noqa: F401
except ImportError:
    pillow_avif = None
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pillow_heif = None

from core.errors import TaskCancelled  # noqa: E402

# Format yang butuh mode RGB (tanpa alpha)
_RGB_ONLY = {"jpg", "jpeg"}
# WebP/AVIF dukung animasi decode; konversi ambil frame pertama bila animasi
_ALPHA_FORMATS = {"png", "webp", "avif", "gif", "tiff", "ico"}


def _require(cond, msg):
    if not cond:
        raise RuntimeError(msg)


def _check_cancel(cancel_fn):
    if cancel_fn and cancel_fn():
        raise TaskCancelled()


def convert(src, dst, target, options, on_prog, cancel_fn=None):
    """Konversi satu gambar. options: quality, resize_w/resize_h/resize_pct,
    watermark_text/watermark_image/watermark_opacity, rotate, flip_h, flip_v.
    """
    quality = int(options.get("quality") or 85)
    Image.MAX_IMAGE_PIXELS = None  # file user besar dianggap disengaja

    with Image.open(src) as im:
        im.load()
        _check_cancel(cancel_fn)
        on_prog(10, "membuka")

        # animasi (gif/webp) → frame pertama untuk format statis
        frames = None
        try:
            getattr(im, "n_frames", 1)
            if target == "gif" and im.n_frames > 1:
                frames = []
                for i in range(im.n_frames):
                    im.seek(i)
                    frames.append(im.convert("RGBA") if target in _ALPHA_FORMATS
                                  else im.convert("RGB"))
                    _check_cancel(cancel_fn)
            elif im.n_frames > 1 and target != "gif":
                im.seek(0)
        except (AttributeError, EOFError):
            pass

        # handler EXIF orientation
        try:
            from PIL import ImageOps
            im = ImageOps.exif_transpose(im)
        except Exception:
            pass

        # resize
        rw, rh = options.get("resize_w"), options.get("resize_h")
        pct = options.get("resize_pct")
        if rw or rh:
            w, h = im.size
            if rw and rh:
                new = (int(rw), int(rh))
            elif rw:
                new = (int(rw), max(1, int(h * int(rw) / w)))
            else:
                new = (max(1, int(w * int(rh) / h)), int(rh))
            im = im.resize(new, Image.LANCZOS)
        elif pct and int(pct) != 100:
            p = int(pct) / 100.0
            im = im.resize((max(1, int(im.size[0] * p)),
                            max(1, int(im.size[1] * p))), Image.LANCZOS)
        if im.size != getattr(im, "_orig", im.size):
            on_prog(40, "resize")

        # rotate / flip
        rot = int(options.get("rotate") or 0)
        if rot:
            im = im.rotate(-rot, expand=True)
        if options.get("flip_h"):
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        if options.get("flip_v"):
            im = im.transpose(Image.FLIP_TOP_BOTTOM)
        _check_cancel(cancel_fn)
        on_prog(50, "transform")

        # watermark
        wm_text = options.get("watermark_text")
        wm_img = options.get("watermark_image")
        if wm_text or wm_img:
            im = _apply_watermark(im, wm_text, wm_img,
                                  float(options.get("watermark_opacity") or 0.5))
        on_prog(65, "watermark" if (wm_text or wm_img) else "siap simpan")

        # mode warna
        if target in _RGB_ONLY and im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        if target == "ico" and im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA")

        # simpan
        save_kwargs = {}
        if target in ("jpg", "jpeg", "webp", "avif"):
            save_kwargs["quality"] = min(quality, 95)
        if target in ("jpg", "jpeg"):
            save_kwargs["optimize"] = True
        if target == "webp":
            save_kwargs["method"] = 4
        if target == "png":
            save_kwargs["optimize"] = True
        if target == "ico":
            save_kwargs["sizes"] = [(16, 16), (32, 32), (48, 48), (64, 64),
                                    (128, 128), (256, 256)]

        _check_cancel(cancel_fn)
        on_prog(80, "menyimpan")
        if frames:  # gif dari sumber animasi
            frames[0].save(dst, format="GIF", save_all=True,
                           append_images=frames[1:], loop=0,
                           duration=im.info.get("duration", 100))
        else:
            im.save(dst, format=target.upper() if target != "jpg" else "JPEG",
                    **save_kwargs)
        on_prog(100, "selesai")


def _apply_watermark(im, text, image_path, opacity):
    from PIL import ImageDraw, ImageFont

    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if text:
        font_size = max(12, im.size[1] // 20)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pos = (im.size[0] - tw - 20, im.size[1] - th - 20)  # kanan bawah
        draw.text(pos, text, font=font,
                  fill=(255, 255, 255, int(255 * opacity)),
                  stroke_width=1, stroke_fill=(0, 0, 0, int(255 * opacity)))
    if image_path and os.path.isfile(image_path):
        try:
            wm = Image.open(image_path).convert("RGBA")
            scale = min(im.size[0] / wm.size[0], im.size[1] / wm.size[1], 1.0)
            if scale < 1.0:
                wm = wm.resize((int(wm.size[0] * scale),
                                int(wm.size[1] * scale)), Image.LANCZOS)
            alpha = wm.getchannel("A").point(lambda a: int(a * opacity))
            wm.putalpha(alpha)
            pos = (im.size[0] - wm.size[0] - 20, im.size[1] - wm.size[1] - 20)
            layer.alpha_composite(wm, pos)
        except OSError:
            pass
    out = im.convert("RGBA")
    out.alpha_composite(layer)
    return out
