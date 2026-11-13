@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Convertly Uninstaller
echo ============================================
echo   CONVERTLY - UNINSTALLER
echo ============================================
echo.
echo Ini akan menghapus: venv, cache, file .pid, dan log aplikasi.
echo File hasil konversi di LUAR folder aplikasi TIDAK disentuh.
echo PERHATIAN: folder "output convert" (hasil konversi) ada di dalam
echo folder aplikasi - ikut terhapus bila memilih hapus seluruh folder.
echo.

rem ---- 1. Matikan aplikasi bila jalan ----
if exist ".pid" (
    set /p PID=<".pid"
    if not "!PID!"=="" taskkill /PID !PID! /T /F >nul 2>nul
    del /q ".pid" >nul 2>nul
    echo [OK] Aplikasi dimatikan.
)

rem ---- 2. Hapus venv + cache ----
echo [..] Menghapus venv dan cache...
if exist "venv" rmdir /s /q "venv"
for /d /r %%D in (__pycache__) do @if exist "%%D" rmdir /s /q "%%D"
del /q "*.pyc" >nul 2>nul
echo [OK] Selesai.

rem ---- 3. Tanya config.json ----
choice /c YN /n /m "Hapus juga config.json (setting + riwayat)? [Y/T, default T]: " /t 15 /d N
if errorlevel 2 goto :skipconfig
if exist "config.json" del /q "config.json"
echo [OK] config.json dihapus.
:skipconfig

rem ---- 4. Tanya hapus seluruh folder ----
echo.
choice /c YN /n /m "Hapus SELURUH folder convertly (tidak bisa dibatalkan)? [Y/T, default T]: " /t 15 /d N
if errorlevel 2 goto :done
echo [..] Menghapus seluruh folder dalam 3 detik... (tutup window ini untuk batal)
timeout /t 3 /nobreak >nul
start "" cmd /c "timeout /t 2 /nobreak >nul & rd /s /q "%~dp0""
exit /b 0

:done
echo.
echo [SELESAI] Uninstall selesai. Folder aplikasi tetap ada (source code).
pause
exit /b 0
