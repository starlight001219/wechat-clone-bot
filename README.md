# 微信智能机器人

基于微信 PC 4.x + wx4py + DeepSeek API / 本地模型的智能回复机器人，可模仿指定人的语气风格自动回复。

## 功能特性

- **AI 自动回复** — 基于 LLM 生成上下文相关的回复，模仿指定人的语气
- **对话记忆** — 自动记录最近聊天上下文，回复更有连贯性
- **语音合成 (TTS)** — 集成 Edge-TTS，支持将文字回复转为语音（免费，无需 API Key）
- **本地模型支持** — 可接入 LoRA 微调的 Qwen2.5 模型（需 GPU 训练）

## 环境要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| Windows | 10/11 | 必需 |
| 微信 PC 客户端 | **4.x** | 支持最新版 |
| Python | 3.10+ | 运行时 |

## 快速启动

### 1. 安装依赖

```bash
cd D:\新建文件夹\misc\wechat-bot
pip install -r requirements.txt
```

### 2. 配置

编辑 `.env` 文件：

```
TARGET_NAME=要模仿的人名       # ← 改成你要模仿的人
TTS_ENABLED=true               # 可选：启用语音合成
```

### 3. 登录微信

打开微信 PC 客户端，用**小号**登录。**保持窗口可见**（不要最小化到托盘）。

### 4. 启动机器人

```bash
py -3.10 bot\main.py
```

## 项目结构

```
wechat-bot/
├─ bot/
│  ├─ main.py             # 主程序入口（整合记忆 + TTS）
│  ├─ wechat_client.py    # wx4py 微信自动化（支持微信 4.x）
│  ├─ llm_client.py       # LLM API 调用 + Persona 提示词
│  ├─ memory_manager.py   # 对话记忆管理（上下文保持）
│  ├─ tts_client.py       # Edge-TTS 语音合成
│  └─ chat_log.py         # 聊天记录导出
├─ config.py              # 配置读取
├─ start.bat              # 一键启动
├─ .env                   # API Key 等敏感配置
└─ logs/                  # 运行日志
```

## 语音合成（TTS）

启用后，每次回复会自动生成语音文件到 `data/audio/` 目录。

- 基于 Microsoft Edge-TTS，**完全免费**，无需注册
- 支持多种中文发音人：`xiaoxiao`(女声)、`yunyang`(男声)、`xiaoyi`(活泼)、`yunxi`(阳光)
- 可在 `.env` 中设置 `TTS_VOICE` 切换发音人

## 两种 LLM 模式

### 本地模型模式
- 需先完成 LoRA 微调，启动推理服务
- 配置: `USE_LOCAL_MODEL=true`

### 远程 API 模式（默认）
- 无需 GPU，配置 API Key 即可使用
- 支持 DeepSeek、OpenAI、Claude 等

## 注意事项

1. **微信窗口必须可见** — 基于 UIAutomation，窗口不可见时无法工作
2. **不要最小化到托盘** — 可以最小化到任务栏，但不能完全隐藏
3. **封号风险** — 个人微信自动化有被封风险，**建议用小号**
4. **首次 TTS** — 第一次使用语音合成时会自动下载语音模型，需要联网
