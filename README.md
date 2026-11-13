# Convertly

Konverter file universal untuk Windows — gambar, dokumen/office, audio, dan video — dalam satu aplikasi desktop ringan.

![Version](https://img.shields.io/badge/version-1.0.0-blueviolet)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

## Daftar Isi

- [Fitur](#-fitur)
- [Memulai](#-memulai)
- [Penggunaan](#-penggunaan)
- [Testing](#-testing)
- [Arsitektur](#arsitektur)
- [Roadmap](#roadmap)
- [Struktur Project](#%EF%B8%8F-struktur-project)
- [Kontribusi](#-kontribusi)
- [Lisensi](#-lisensi)

<!-- TODO: tambahkan screenshot di sini, mis. docs/screenshot-main.png -->
<!-- ![Tampilan utama Convertly](docs/screenshot-main.png) -->

Convertly dibangun dengan Python + [pywebview](https://pywebview.flowrl.com/):
jendela native (WebView2 bawaan Windows) dengan frontend HTML/CSS — desain
glassmorphism + aurora, dark/light mode — dan seluruh proses konversi berjalan
lokal, tanpa server, tanpa internet.

## ✨ Fitur

- **Antrian konversi** — drag & drop banyak file, deteksi otomatis format target
  yang tersedia per file, batch, progress realtime, cancel per item.
- **Gambar** — PNG, JPG, WebP, AVIF, GIF, BMP, TIFF, ICO (+ HEIC decode):
  konversi, resize, kualitas, watermark teks/gambar, rotate, flip.
- **Dokumen** — PDF ops (merge, split per halaman, rotate, kompres, extract
  teks) dan konversi teks antara DOCX, XLSX, CSV, PPTX, TXT, MD, HTML, PDF.
- **Audio / Video** — semua format yang didukung [ffmpeg](https://ffmpeg.org):
  konversi, trim, CRF, scaling, bitrate, extract audio, video → GIF.
- **Preset rekomendasi** — pengaturan terbaik per format terisi otomatis dan
  terkunci; bisa dibuka ke mode manual kapan saja.
- **Manajer dependensi in-app** — fitur dengan paket yang belum terpasang
  otomatis disabled dan bisa di-install lewat tombol Install (log live).
- **Dark / Light mode**, folder output default `output convert` (auto-create),
  pola penamaan `{name}/{format}/{date}`, riwayat 200 entri, bersihkan log,
  reset pengaturan.

## 🚀 Memulai

### Prasyarat

- [Python 3.10+](https://python.org) (centang *Add to PATH* saat install)
- [ffmpeg](https://ffmpeg.org) di PATH — **opsional**, hanya untuk audio/video.
  Panel *Dependencies* di aplikasi memandu pemasangannya.

### Instalasi & Menjalankan

```bat
git clone <url-repo>
cd convert-pro
start.bat
```

`start.bat` membuat virtual environment + memasang dependencies secara
otomatis (sekali saja), lalu membuka jendela aplikasi.

| File | Fungsi |
|---|---|
| `start.bat` | setup venv (sekali) + jalankan aplikasi |
| `stop.bat` | matikan aplikasi (via PID) |
| `uninstall.bat` | hapus venv/cache; konfirmasi sebelum menyentuh config & folder |

## 📖 Penggunaan

1. Lepas file ke drop-zone (atau klik **pilih file**).
2. Pilih format target per file — preset rekomendasi terisi otomatis.
3. Klik **Konversi Sekarang** — hasil muncul di folder `output convert`
   (dapat diganti di *Settings*).

Kategori dengan paket yang belum terpasang tampil **disabled** dengan badge —
buka view *Dependencies* dan klik **Install** untuk mengaktifkannya.

## 🧪 Testing

```bat
venv\Scripts\python.exe tests\test_full.py
```

78 kasus uji: seluruh jalur konversi (dengan verifikasi konten hasil), engine
(antrian, validasi, cancel), settings (race thread, config korup), registry,
dan jembatan API. Exit code `0` = semua lulus.

## 🏗️ Struktur Project

```
convert-pro/
├── src/                       # seluruh kode aplikasi
│   ├── main.py                # entry point — jendela native pywebview
│   ├── api.py                 # jembatan JS ↔ Python (js_api)
│   ├── core/
│   │   ├── engine.py          # antrian konversi + thread pool + progress
│   │   ├── registry.py        # matriks format → target + dependensinya
│   │   ├── deps.py            # cek & install paket per fitur
│   │   ├── settings.py        # config.json (atomic write), reset, output dir
│   │   ├── applog.py          # app.log untuk diagnosa
│   │   └── converters/        # images.py · documents.py · media.py (ffmpeg)
│   └── ui/                    # frontend (glassmorphism + aurora, dark/light)
├── tests/                     # test suite
├── tools/gen_icon.py          # generator icon aplikasi
├── docs/                      # dokumentasi + ADR
├── start.bat · stop.bat · uninstall.bat
└── LICENSE · README.md
```

> Artefak runtime (`config.json`, `app.log`, `.pid`, `output convert/`)
> tetap berada di root repo — dibuat otomatis saat aplikasi berjalan.

## 🔧 Teknologi

| Komponen | Pilihan |
|---|---|
| UI engine | [pywebview](https://pywebview.flowrl.com/) (WebView2) |
| Gambar | Pillow + pillow-avif-plugin + pillow-heif |
| Dokumen | PyMuPDF, python-docx, openpyxl, python-pptx, markdown |
| Audio/Video | ffmpeg (binary eksternal, auto-detect) |

> Catatan: konversi dokumen bersifat **teks** (paragraf, heading, tabel
> sederhana) — layout kompleks Word/Excel adalah best-effort.

## 🐞 Troubleshooting

- Log aplikasi: `app.log` — lihat path lewat *Settings > Log aplikasi*.
- Tab audio/video disabled → pasang ffmpeg (`winget install --id Gyan.FFmpeg -e`),
  lalu restart aplikasi.
- Aplikasi tidak mau mati → `stop.bat`.

## Arsitektur

Detail komponen, alur konversi, threading model, dan sistem dependensi:
lihat [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Keputusan teknis besar terdokumentasi
sebagai ADR di [`docs/adr/`](docs/adr/) — format Nygard (context, decision,
consequences):

| ADR | Keputusan |
|---|---|
| [0001](docs/adr/0001-ui-engine-pywebview.md) | UI engine pywebview dibanding Qt/Electron |
| [0002](docs/adr/0002-lazy-import-startup.md) | Lazy import demi startup cepat |
| [0003](docs/adr/0003-dependency-manager.md) | Dependensi hilang mematikan fitur, bukan aplikasi |
| [0004](docs/adr/0004-default-output-folder.md) | Folder output default `output convert` |
| [0005](docs/adr/0005-icon-aplikasi.md) | Icon aplikasi: WM_SETICON + AppUserModelID |

## Roadmap

- [ ] Preset kustom yang bisa disimpan user
- [ ] Watermark gambar dengan posisi & opasitas bebas
- [ ] Dukungan ebook (EPUB) dan arsip (ZIP/TAR)
- [ ] Build EXE standalone (PyInstaller) + auto-update check
- [ ] Multi-bahasa (ID/EN)

## 🤝 Kontribusi

Lihat [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md). Update
[docs/CHANGELOG.md](docs/CHANGELOG.md) untuk perubahan yang menonjol.

## 📄 Lisensi

[MIT](LICENSE) — © 2026 Convertly Contributors.
