# Contributing to Convertly

Terima kasih ingin berkontribusi! Panduan singkat ini menjaga kontribusi tetap
mudah direview dan konsisten dengan arah project.

## Cara mulai

1. Fork / clone repo, lalu jalankan `start.bat` — venv + dependencies terpasang otomatis.
2. Jalankan test suite dari ROOT repo sebelum dan sesudah perubahan:

   ```bat
   venv\Scripts\python.exe tests\test_full.py
   ```

   Semua test harus PASS (exit code 0).

## Aturan kode

Seluruh kode Python berada di folder `src/` — `src/main.py` (entry),
`src/api.py` (bridge), `src/core/` (logika), `src/ui/` (frontend).

- Python 3.10+, gaya mengikuti kode yang sudah ada (docstring bahasa Indonesia,
  penamaan jelas, tanpa dependensi baru tanpa diskusi).
- Semua import library berat dilakukan **lazy** (di dalam fungsi) agar startup cepat.
- Converter baru wajib: terdaftar di `core/registry.py` (kategori + matriks target),
  punya entri dependensi di `core/deps.py`, dan melempar `RuntimeError` dengan pesan
  jelas saat gagal.
- Jangan pernah menimpa file user di luar folder output yang dipilih.
- Error jangan dibiarkan senyap — log via `core/applog.py` atau lempar exception
  dengan pesan yang bisa dipahami user.

## Pelaporan bug

Sertakan: langkah reproduksi, format file sumber/target, output di `app.log`
(bisa dilihat lewat Settings > Bersihkan Log atau langsung buka filenya), dan
versi Windows + Python.

## Pull request

- Satu PR = satu topik perubahan.
- Sertakan update `CHANGELOG.md` (format [Keep a Changelog](https://keepachangelog.com/en/2.0.0/)).
- Test harus lulus; tambah test untuk perbaikan bug / fitur baru.
