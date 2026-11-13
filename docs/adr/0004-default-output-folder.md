# ADR-0004 — Folder Output Default "output convert" (Auto-Create)

- **Status:** Accepted
- **Tanggal:** 2026-11-14

## Context

Tanpa folder output bawaan, hasil konversi menyebar di folder sumber masing-
masing file dan sulit ditemukan user. Dibutuhkan default yang pasti, dan
harus tetap bisa diganti.

## Decision

Folder output default adalah **`output convert/`** di dalam folder aplikasi,
dibuat otomatis saat dibutuhkan (`settings.resolve_output_dir` dengan
`os.makedirs(exist_ok=True)`). Path custom di Settings boleh absolut atau
relatif (dihitung dari folder aplikasi). Pola penamaan `{name}/{format}/
{date}` disanitasi dari karakter ilegal; tabrakan sumber=output diberi
suffix `_converted`.

## Consequences

- (+) Hasil konversi selalu di satu tempat yang mudah ditemukan.
- (+) Tidak ada kegagalan penulisan karena folder belum ada.
- (-) `uninstall.bat` yang menghapus seluruh folder aplikasi ikut menghapus
  hasil konversi di dalamnya — diberi peringatan eksplisit di uninstaller.
