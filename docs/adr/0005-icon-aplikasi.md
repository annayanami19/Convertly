# ADR-0005 — Icon Aplikasi: WM_SETICON + AppUserModelID

- **Status:** Accepted
- **Tanggal:** 2026-11-14

## Context

Aplikasi jalan dari `pythonw.exe` sehingga title bar dan taskbar menampilkan
icon Python bawaan. `webview.start(icon=...)` (pywebview 6) menyetel
`Form.Icon`, tetapi taskbar Windows kadang tetap menampilkan icon proses.

## Decision

Tiga lapis: (1) `webview.start(icon=...)` sebagai jalur resmi, (2) setelah
event `loaded`, `WM_SETICON` (ICON_BIG + ICON_SMALL) dikirim langsung ke
handle Form via ctypes — handle dari `window.native.Handle` dikonversi dengan
`IntPtr.ToInt64()`, (3) `SetCurrentProcessExplicitAppUserModelID("imp.convertly.1")`
agar taskbar mengelompokkan aplikasi secara independen dari pythonw.exe.
Icon-nya sendiri digenerate programatik oleh `tools/gen_icon.py` ke
`ui/assets/icon.ico` (multi-size).

## Consequences

- (+) Title bar dan taskbar konsisten memakai icon aplikasi.
- (-) Bergantung detail pythonnet (`IntPtr` tidak mendukung `int()` langsung)
  — dikunci ke mekanisme konversi eksplisit dan dilindungi try/except ber-log.
- (-) Windows kadang men-cache icon taskbar; perlu restart instance agar
  icon baru terlihat.
