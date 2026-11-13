# Arsitektur Convertly

Gambaran teknis bagaimana Convertly bekerja. Untuk alasan di balik setiap
keputusan besar, lihat [`docs/adr/`](adr/) (Architecture Decision Records).

## Gambaran Umum

Convertly adalah aplikasi desktop Windows: satu proses Python yang membuka
jendela native via **pywebview** (renderer WebView2 bawaan Windows) dan
menampilkan frontend HTML/CSS/JS dari folder `ui/`. Tidak ada server, tidak
ada browser — semua konversi berjalan lokal.

```
┌────────────────────────────────────────────────────────────┐
│  Jendela native (WebView2)                                 │
│                                                            │
│  src/ui/index.html + app.js     src/api.py (js_api)           │
│  ┌──────────────────┐   promise  ┌───────────────────┐     │
│  │ dropzone, kartu  │ ─────────► │ select_files      │     │
│  │ file, opsi,      │            │ add_tasks         │     │
│  │ preset, antrian  │ ◄───────── │ get_deps/...      │     │
│  └──────────────────┘  evaluate  └─────────┬─────────┘     │
│        ▲             js (push_js)          │               │
└────────┼───────────────────────────────────┼───────────────┘
         │ window.__onEvent(...)             │
         │                                   ▼
┌────────┴───────────────────────────────────────────────────┐
│  src/core/engine.py — antrian + ThreadPoolExecutor        │
│      status: queued → running → done/error/cancelled       │
│      progress dikirim ke UI via _emit_task                 │
│                    │                                       │
│     ┌──────────────┼──────────────────┐                    │
│     ▼              ▼                  ▼                    │
│ src/core/      src/core/         src/core/               │
│ images.py      documents.py      media.py                  │
│ (Pillow)       (PyMuPDF,         (ffmpeg subprocess,       │
│                 docx, openpyxl,   -progress pipe:1)        │
│                 pptx, markdown)                            │
└────────────────────────────────────────────────────────────┘
         │                                  │
         ▼                                  ▼
  src/core/settings.py               src/core/deps.py
  config.json (atomic)                find_spec / shutil.which
  output convert/ (auto-create)       pip install (thread + log live)
```

## Alur Konversi

1. **Entri** — JS mengirim `[{src, target, options}]` → `api.add_tasks`.
2. **Validasi** — `core/registry.py`: kategori dari ekstensi, target valid
   (whitelist op PDF), dependensi tersedia (atau task ditolak dengan alasan).
3. **Eksekusi** — `engine.add_tasks` menyimpan task lalu submit ke thread pool.
4. **Progress** — converter memanggil callback persen → `push_js("task", ...)`
   → `window.__onEvent` → bar antrian.
5. **Output** — nama dari pola penamaan, folder dari `settings.resolve_output_dir`
   (default `output convert/`, auto-create), tabrakan nama diberi suffix
   `_converted`.
6. **Riwayat** — hasil dicatat ke `config.json` (maks 200, atomic).

## Threading Model

- UI thread: pywebview GUI loop (WinForms + WebView2).
- Worker: `ThreadPoolExecutor` (jumlah bisa diatur, rebuild tanpa restart).
- `api.push_js` dilindungi lock — `evaluate_js` dipanggil dari worker dengan aman.
- Cancel: `engine.is_cancelled(id)` di-polling converter; ffmpeg diterminate,
  file parsial dihapus.
- `settings` memakai `RLock` — `add_history` dari worker paralel tetap atomik.

## Sistem Dependensi

`core/deps.py` memetakan paket → fitur (`FEATURE_DEPS`). Frontend menonaktifkan
format yang dependensinya hilang; install lewat `pip` di background thread
dengan output live ke panel log. ffmpeg bukan paket pip — dideteksi via
`shutil.which` dengan panduan winget.

## Keputusan Arsitektur

Lihat [docs/adr/](adr/) — setiap keputusan besar didokumentasikan dengan
format Nygard (context, decision, consequences).
