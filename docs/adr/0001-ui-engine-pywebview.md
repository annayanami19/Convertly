# ADR-0001 — UI Engine: pywebview dibanding Qt/Electron

- **Status:** Accepted
- **Tanggal:** 2026-11-14

## Context

Convertly butuh UI desktop yang jauh di atas tampilan bawaan toolkit Python
(dark/light mode, glassmorphism, animasi aurora, drag & drop modern). Kandidat:
PySide6/PyQt + QSS atau library widget (qt-material, qfluentwidgets),
Electron-like bundling, dan pywebview.

## Decision

Memakai **pywebview**: frontend HTML/CSS/JS murni di folder `ui/`, backend
Python diekspos via `js_api` (promise-based), renderer memakai WebView2 yang
sudah ada di Windows 10/11.

## Consequences

- (+) Kebebasan desain penuh (glassmorphism, aurora animasi) tanpa bundel
  browser — ukuran aplikasi tetap kecil.
- (+) Frontend dan backend terpisah bersih (bridge API eksplisit).
- (-) Path file hasil drag & drop hanya tersedia di sisi Python
  (`pywebviewFullPath` via `DOMEventHandler`) — perlu event bridge custom
  (`api.on_drop_event` → `push_js("files_dropped")`).
- (-) Konstanta API berubah antar mayor versi pywebview (mis. `OPEN_DIALOG` →
  `FileDialog.OPEN`) — versi dikunci `pywebview>=6.0`.
