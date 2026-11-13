@echo off
setlocal
cd /d "%~dp0"
title Convertly Launcher

rem ---- Cari Python di PATH ----
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python tidak ditemukan di PATH. Install Python 3.10+ dari python.org.
    pause
    exit /b 1
)

rem ---- Buat venv bila belum ada ----
if not exist "venv\Scripts\python.exe" (
    echo [SETUP] Membuat virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Gagal membuat venv.
        pause
        exit /b 1
    )
)

rem ---- Install dependencies bila belum ditandai selesai ----
if not exist "venv\.deps_installed" (
    echo [SETUP] Menginstall dependencies ^(sekali saja^)...
    "venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    "venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Gagal install dependencies. Cek koneksi internet lalu jalankan lagi.
        pause
        exit /b 1
    )
    echo ok> "venv\.deps_installed"
)

rem ---- Aplikasi menulis .pid sendiri saat start (main.py) ----
echo [START] Menjalankan Convertly...
start "" "venv\Scripts\pythonw.exe" "src\main.py"
timeout /t 2 /nobreak >nul
if exist ".pid" (
    echo [OK] Convertly berjalan. Untuk menutup: stop.bat
) else (
    echo [WARN] Window belum terdeteksi. Bila tidak muncul, jalankan:
    echo        venv\Scripts\python.exe main.py
)
exit /b 0
