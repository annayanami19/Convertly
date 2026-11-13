@echo off
setlocal
cd /d "%~dp0"

if not exist ".pid" (
    echo [INFO] File .pid tidak ada - aplikasi tidak sedang berjalan.
    exit /b 0
)

set /p PID=<".pid"
if "%PID%"=="" (
    echo [INFO] .pid kosong.
    exit /b 0
)

taskkill /PID %PID% /T /F >nul 2>nul
if errorlevel 1 (
    echo [INFO] Proses %PID% sudah tidak ada.
) else (
    echo [OK] Convertly dimatikan ^(PID %PID%^).
)
del /q ".pid" >nul 2>nul
exit /b 0
