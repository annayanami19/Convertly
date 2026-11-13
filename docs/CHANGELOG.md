# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-14

Initial public release.

### Added

- Universal file converter for Windows: images, documents/office, and audio/video.
- Drag & drop queue with per-file target selection, batch conversion, progress, and cancel.
- Image conversion: PNG, JPG, WebP, AVIF, GIF, BMP, TIFF, ICO + HEIC decode; resize, quality, text/image watermark, rotate, flip.
- Document conversion: PDF ops (merge, split per page, rotate, compress, extract text) and text-level conversion between DOCX, XLSX, CSV, PPTX, TXT, MD, HTML, PDF.
- Media conversion via ffmpeg: any ffmpeg-supported format, trim, CRF, scaling, audio bitrate, extract audio, video-to-GIF.
- Recommended presets per target format, auto-filled and locked; manual override with two-click confirmation.
- In-app dependency manager: features with missing packages are disabled until installed via the Install button; ffmpeg detected via PATH with a winget guide.
- Dark and light glassmorphism UI with animated aurora background.
- Default output folder `output convert` (auto-created), custom output folder, naming pattern `{name}/{format}/{date}`, overwrite or skip.
- Session history (last 200 entries) with clear-history, log viewer with clear-logs, reset-to-default settings.
- Custom application icon in title bar and taskbar.
- `start.bat` (one-time venv + dependency setup), `stop.bat`, and `uninstall.bat` with confirmation prompts.
- Test suite: 78 unit/end-to-end cases (`tests/test_full.py`) covering all converters, engine, settings, registry, and API bridge.

[Unreleased]: https://example.com/convertly/compare/v1.0.0...HEAD
[1.0.0]: https://example.com/convertly/releases/tag/v1.0.0
