# ADR-0002 — Lazy Import demi Startup Cepat

- **Status:** Accepted
- **Tanggal:** 2026-11-14

## Context

Empat kategori konversi menarik dependensi berat (Pillow, PyMuPDF, python-docx,
openpyxl, python-pptx, markdown). Mengimpor semuanya saat aplikasi start
membuat waktu buka jendela terasa lambat, padahal satu sesi biasanya hanya
memakai satu-dua konverter.

## Decision

Semua import library konversi dilakukan **lazy** — di dalam fungsi pembantu
(`_fitz()`, `_docx()`, `_openpyxl()`, `_pptx()`, `_markdown()`) — sehingga
hanya modul yang benar-benar dipakai yang dimuat. `core/deps.py` mengecek
ketersediaan via `importlib.util.find_spec` tanpa memuat modul berat.

## Consequences

- (+) Startup aplikasi cepat; memori hanya terpakai sesuai kebutuhan.
- (+) Satu paket rusak tidak otomatis meruntuhkan kategori lain.
- (-) Kesalahan import baru terasa saat konversi dijalankan — dimitigasi oleh
  panel Dependencies yang memverifikasi paket sebelum fitur diaktifkan.
