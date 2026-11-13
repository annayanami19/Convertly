# ADR-0003 — Dependensi Hilang Mematikan Fitur, Bukan Aplikasi

- **Status:** Accepted
- **Tanggal:** 2026-11-14

## Context

Convertly berjalan dari script Python; tidak ada jaminan semua paket
terpasang (venv rusak, user menghapus paket, ffmpeg belum ada). Dua opsi:
biarkan aplikasi crash saat import, atau mendegradasi fungsinya.

## Decision

**Fitur didegradasi, bukan aplikasi.** `core/deps.py` memetakan paket → fitur
(`FEATURE_DEPS`) dan mengecek via `importlib.util.find_spec` / `shutil.which`.
Format yang dependensinya hilang ditandai disabled di UI dengan badge, dan
hanya bisa diaktifkan setelah user mengklik **Install** (pip di background
thread, output live ke panel log). Aplikasi tidak pernah meng-install tanpa
persetujuan user.

## Consequences

- (+) Aplikasi selalu bisa dibuka walau dependensi parsial.
- (+) User memahami apa yang hilang dan kenapa (badge + alasan per paket).
- (-) Setiap jalur konversi harus mengecek dependensi (di `add_tasks` dan di
  `targets_for` UI) — kalau terlewat, task ditolak dengan pesan eksplisit.
- (-) ffmpeg tidak bisa di-install via pip — diberikan panduan `winget` +
  tombol copy command, fitur tetap disabled sampai binary terdeteksi.
