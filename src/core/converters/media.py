"""Converter audio/video via binary ffmpeg (eksternal, auto-detect di PATH).

Progress di-parse dari output -progress pipe:1 (out_time_ms, satuan
mikrodetik) dibanding durasi dari ffprobe.
"""
import os
import shutil
import subprocess

from core.errors import TaskCancelled

_VIDEO_TARGETS = {"mp4", "mkv", "webm", "mov", "avi", "gif"}
_VIDEO_CODEC = {
    "mp4": "libx264", "mkv": "libx264", "mov": "libx264",
    "webm": "libvpx-vp9", "avi": "mpeg4", "gif": "gif",
}
_AUDIO_CODEC = {
    "mp3": "libmp3lame", "m4a": "aac", "aac": "aac", "opus": "libopus",
    "ogg": "libvorbis", "wav": "pcm_s16le", "flac": "flac",
}


def ffmpeg_available():
    return shutil.which("ffmpeg") is not None


def _flags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _duration(src):
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", src],
            capture_output=True, text=True, timeout=30, creationflags=_flags())
        return float(out.stdout.strip())
    except (ValueError, subprocess.SubprocessError, OSError):
        return None


def convert(src, dst, target, options, on_prog, cancel_fn=None):
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg tidak ditemukan — pasang lewat panel "
                           "Dependencies (perintah winget tersedia di sana)")

    total = _duration(src)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]

    trim_start = options.get("trim_start")
    if trim_start:
        cmd += ["-ss", str(trim_start)]
    cmd += ["-i", src]
    trim_end = options.get("trim_end")
    if trim_end:
        if trim_start and float(trim_end) <= float(trim_start):
            raise RuntimeError("trim_end harus lebih besar dari trim_start")
        if trim_start:
            # -ss input-seeking menggeser timeline output ke 0:
            # -to 1.5 berarti "sampai 1.5 dtk output", bukan 1.5 dtk sumber.
            # Pakai durasi (-t) supaya trim_end = posisi di SUMBER.
            cmd += ["-t", str(float(trim_end) - float(trim_start))]
        else:
            cmd += ["-t", str(trim_end)]

    is_video_target = target in _VIDEO_TARGETS
    src_is_video = os.path.splitext(src)[1].lower() in (
        ".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".wmv", ".m4v",
        ".ts", ".3gp", ".ogv")

    if target == "gif":
        cmd += ["-vf", "fps=12,scale=480:-1:flags=lanczos"]
    elif is_video_target:
        scale_w = options.get("scale_w")
        if scale_w:
            cmd += ["-vf", "scale=%d:-2" % int(scale_w)]
        cmd += ["-c:v", _VIDEO_CODEC[target]]
        crf = options.get("crf")
        if crf and target not in ("avi", "gif"):
            cmd += ["-crf", str(int(crf))]
    elif src_is_video or options.get("extract_audio"):
        cmd += ["-vn"]  # extract audio dari video / audio-only target

    if not is_video_target and target in _AUDIO_CODEC:
        cmd += ["-c:a", _AUDIO_CODEC[target]]

    if target != "gif":
        ab = options.get("audio_bitrate")
        if ab:
            cmd += ["-b:a", str(ab)]

    on_prog(5, "menyiapkan")
    cmd += ["-progress", "pipe:1", "-nostats", dst]


    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace",
                            creationflags=_flags())
    try:
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("out_time_ms=") and total:
                micros = line.split("=", 1)[1]
                try:
                    pct = min(99, int(int(micros) / 1_000_000 / total * 100))
                    if pct >= 0:
                        on_prog(max(pct, 6))
                except ValueError:
                    pass
            if cancel_fn and cancel_fn():
                proc.terminate()
                raise TaskCancelled()
        code = proc.wait()
    except TaskCancelled:
        proc.wait()
        try:
            os.remove(dst)  # jangan tinggalkan output setengah jadi
        except OSError:
            pass
        raise
    if code != 0:
        stderr_tail = ""
        if proc.stderr:
            stderr_tail = proc.stderr.read()[-500:]
        raise RuntimeError("ffmpeg gagal (exit %d): %s" % (code, stderr_tail))
    on_prog(100)
