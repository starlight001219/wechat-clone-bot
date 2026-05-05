@echo off
chcp 65001 >nul
title WeChat AI Bot

echo ========================================
echo  微信智能机器人启动脚本
echo ========================================
echo.
echo 请确保：
echo  1. 微信PC客户端已打开并登录
echo  2. 微信窗口未最小化到托盘
echo  3. 已配置 .env 文件（API Key等信息）
echo.

:: Check if .env exists
if not exist .env (
    echo [警告] 未找到 .env 配置文件！
    echo 请复制 .env.example 为 .env 并填写 API Key
    echo.
copy .env.example .env
    echo 已创建 .env 模板，请编辑后重新运行
    pause
    exit /b
)

:: Run the bot
echo [信息] 启动机器人...
py -3.10 bot\main.py

pause
