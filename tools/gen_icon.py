"""Generator icon aplikasi Convertly — jalankan:
venv/Scripts/python.exe tools/gen_icon.py
Hasil: ui/assets/icon.ico (multi-size) + icon.png (preview).
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "ui", "assets")
os.makedirs(OUT, exist_ok=True)

S = 512
im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
grad = Image.new("RGBA", (S, S))
d = ImageDraw.Draw(grad)

# gradient diagonal teal (#5eead4) -> violet (#a78bfa)
c1, c2 = (94, 234, 212), (167, 139, 250)
for y in range(S):
    for seg in range(0, S, 4):
        t = (y + seg) / (2 * S)
        col = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)) + (255,)
        d.rectangle([seg, y, seg + 4, y + 4], fill=col)

mask = Image.new("L", (S, S), 0)
md = ImageDraw.Draw(mask)
md.rounded_rectangle([16, 16, S - 16, S - 16], radius=110, fill=255)
im.paste(grad, (0, 0), mask)

# dua panah blok putih (simbol konversi <->)
arrows = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ad = ImageDraw.Draw(arrows)
WHITE = (255, 255, 255, 235)
# panah atas: kanan
ad.rounded_rectangle([120, 176, 330, 236], radius=26, fill=WHITE)
ad.polygon([(330, 146), (330, 266), (412, 206)], fill=WHITE)
# panah bawah: kiri
ad.rounded_rectangle([182, 276, 392, 336], radius=26, fill=WHITE)
ad.polygon([(182, 246), (182, 366), (100, 306)], fill=WHITE)
im.alpha_composite(arrows)

im.save(os.path.join(OUT, "icon.ico"),
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
               (128, 128), (256, 256)])
im.save(os.path.join(OUT, "icon.png"))
print("icon dibuat:", os.path.join(OUT, "icon.ico"))
