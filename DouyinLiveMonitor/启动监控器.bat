@echo off
chcp 65001 >nul 2>&1
title 鎶栭煶鐩存挱闂寸洃鎺у櫒
echo ========================================
echo   鎶栭煶鐩存挱闂寸洃鎺у櫒 - 鍚姩绋嬪簭
echo ========================================
echo.

:: 妫€鏌?Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [閿欒] 鏈壘鍒?Python锛岃鍏堝畨瑁?Python 3.8+
    echo 涓嬭浇鍦板潃: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 妫€鏌ュ苟瀹夎渚濊禆
echo [1/2] 妫€鏌ヤ緷璧?..
python -c "import PyQt5" >nul 2>&1
if %errorlevel% neq 0 (
    echo [瀹夎] 姝ｅ湪瀹夎 PyQt5锛堥娆¤繍琛岄渶瑕侊級...
    pip install PyQt5 requests -q
)

echo [2/2] 鍚姩鐩戞帶鍣?..
echo.
python "%~dp0main.py"

if %errorlevel% neq 0 (
    echo.
    echo [閿欒] 鍚姩澶辫触锛岄敊璇唬鐮? %errorlevel%
    pause
)
