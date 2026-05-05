@echo off
chcp 65001 >nul
cd /d "D:\新建文件夹\starlight\wechat-bot"

echo ====================================
echo   微信 AI 女友机器人
echo ====================================
echo.

:: 进入虚拟环境
call .venv\Scripts\activate.bat

:: 启动机器人
python main.py

pause
