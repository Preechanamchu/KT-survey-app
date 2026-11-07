@echo off
chcp 65001 >nul
title KT Survey Pro - GitHub APK Uploader
echo ============================================================
echo   KT Survey Pro — ระบบอัปโหลด APK ขึ้น GitHub Releases
echo ============================================================
echo.
echo กำลังเริ่มต้นเซิร์ฟเวอร์และเปิดเบราว์เซอร์อัตโนมัติ...
echo.

python server.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo เกิดข้อผิดพลาดในการรัน python กรุณาตรวจสอบว่าติดตั้ง Python ไว้ในเครื่องแล้ว
    pause
)
