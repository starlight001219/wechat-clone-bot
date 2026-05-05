# 🤖 微信智能机器人 (WeChat AI Bot)

基于 **微信 PC 4.x** + **wx4py** + **DeepSeek API** 的智能回复机器人。

可**从真实聊天记录中学习**指定联系人的语气风格，实现**自动化聊天 + 语音合成**。

---

## 📋 项目概述

本项目通过微信 PC 客户端的 UI 自动化接口，实时监听指定联系人的消息，调用 **DeepSeek API**（学习真实聊天记录中的语气风格）生成符合目标人物风格的回复，并通过微信窗口自动发送。同时集成 **Edge-TTS 语音合成**，可将文字回复转为语音。

### 核心特色：从聊天记录学习风格

不需要昂贵的 GPU 微调训练！通过 **StyleLearner** 模块：

1. 读取导出的微信聊天记录 CSV
2. 提取 2582+ 条真实对话消息作为风格参考
3. 构建带角色描述 + 真实示例的提示词
4. 发送给 DeepSeek API，生成自然逼真的回复

核心流程：

```
接收消息 → 查询对话历史 → StyleLearner 选取风格示例 → DeepSeek 生成回复 → 存入记忆 → 发送文字 → (可选) 生成语音
```

---

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| **风格学习** | 从真实聊天记录中学习语气风格，无需 GPU 训练 |
| **AI 自动回复** | 基于 DeepSeek API + 真实聊天示例生成自然回复 |
| **对话记忆管理** | 自动记录最近 20 轮对话，持久化到本地文件，回复更连贯 |
| **语音合成 (TTS)** | 集成 Edge-TTS，免费无 API Key 要求，自动生成 MP3 语音文件 |
| **多发音人** | 支持 4 种中文发音人：女声、男声、活泼女声、阳光男声 |
| **聊天记录导出** | 支持导出微信聊天记录为 CSV |
| **日志审计** | 完整的运行日志记录，方便调试和监控 |

---

## 🛠️ 技术栈

| 技术 | 用途 | 版本 |
|------|------|------|
| **Windows 10/11** | 运行平台（必需，依赖 UI Automation） | — |
| **微信 PC 客户端 4.x** | 聊天界面自动化操作 | 4.1.8+ |
| **Python** | 主开发语言 | 3.10+ |
| **wx4py** | 微信 PC 4.x UI 自动化库 | ≥0.2.1 |
| **pywin32** | Windows API 接口（窗口操作、UI 控制） | ≥300 |
| **OpenAI Python SDK** | 远程 LLM API 调用 | ≥1.0.0 |
| **Edge-TTS** | 微软 Edge 浏览器 TTS 引擎（免费） | ≥6.0.0 |
| **Loguru** | 结构化日志记录 | ≥0.7.0 |
| **python-dotenv** | 环境变量管理 | ≥1.0.0 |
| **Qwen2.5-1.5B (可选)** | 本地微调基座模型 | LoRA |
| **LLaMA Factory (可选)** | 微调训练框架 | — |

---

## 🏗️ 项目架构

```
wechat-bot/
├── bot/                          # 核心业务逻辑
│   ├── main.py                   # 主入口：初始化、消息循环、整合各模块
│   ├── wechat_client.py          # 微信客户端：连接、发送、监听消息轮询
│   ├── llm_client.py             # LLM 客户端：调用本地或远程 API 生成回复
│   ├── memory_manager.py         # 对话记忆：上下文管理 + JSON 持久化
│   ├── tts_client.py             # 语音合成：Edge-TTS 文字转语音
│   ├── chat_log.py               # 聊天记录导出工具（供 WeClone 训练用）
│   └── __init__.py
├── config.py                     # 配置读取（从 .env 加载）
├── .env                          # 敏感配置（API Key、开关等）【不上传】
├── .env.example                  # 配置模板
├── .gitignore                    # Git 忽略规则
├── requirements.txt              # Python 依赖清单
├── start.bat                     # Windows 一键启动脚本
├── export_chat.py                # 独立聊天记录导出脚本
├── data/                         # 运行时数据（记忆、音频）【不上传】
│   ├── conversation_memory.json  # 对话记忆持久化文件
│   └── audio/                    # TTS 生成的 MP3 文件
└── logs/                         # 运行日志【不上传】
```

### 核心模块说明

| 模块 | 文件 | 职责 |
|------|------|------|
| **入口** | `bot/main.py` | 初始化 WeChatBot 类，注册消息回调，启动事件循环 |
| **消息监听** | `bot/wechat_client.py` | 通过 wx4py 连接微信，轮询聊天窗口消息列表，检测新消息 |
| **AI 回复** | `bot/llm_client.py` | 调用 DeepSeek / OpenAI API，整合风格示例生成回复 |
| **风格学习** | `bot/style_learner.py` | 从 CSV 聊天记录提取 2582+ 条消息作为风格参考，构建角色提示词 |
| **记忆系统** | `bot/memory_manager.py` | 环形缓冲区存储最近 N 轮对话，支持多联系人隔离和 JSON 持久化 |
| **语音合成** | `bot/tts_client.py` | Edge-TTS 异步/同步接口，支持多种中文发音人 |
| **数据导出** | `export_chat.py` | 独立脚本，滚动加载聊天记录，导出为 WeClone 格式 CSV |
| **配置管理** | `config.py` | 从 .env 文件读取配置，提供类型化配置类 |

---

## 🔧 环境要求

| 依赖项 | 要求 | 说明 |
|--------|------|------|
| **操作系统** | Windows 10 或 11 | 必须，依赖 Windows UIAutomation API |
| **微信客户端** | PC 4.x 版本 | 当前适配 4.1.8，升级后可能需要更新 wx4py |
| **Python** | 3.10 或更高 | 推荐 3.10.11 |
| **DeepSeek API Key** | 需要 | 用于调用 AI 回复 |
| **网络** | 需要联网 | DeepSeek API / Edge-TTS 需要联网 |
| **GPU** | 不需要 | 所有 AI 处理在云端完成 |

---

## 📥 安装与配置

### 1. 安装 Python 依赖

```bash
cd wechat-bot
pip install -r requirements.txt
```

### 2. 配置环境变量

复制配置模板并编辑：

```bash
copy .env.example .env
```

编辑 `.env` 文件，至少配置以下内容：

```ini
# 选择 LLM 模式（二选一）

# 模式 A：远程 API（推荐快速体验）
LLM_API_KEY=sk-your-deepseek-api-key
LLM_API_BASE=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

# 模式 B：本地模型（需先训练）
# USE_LOCAL_MODEL=true
# LOCAL_MODEL_URL=http://127.0.0.1:8000

# 被模仿人的名字
TARGET_NAME=周文慧

# 要监控的联系人（留空=监控所有会话）
TARGET_WXID=星夜

# TTS 语音合成开关
TTS_ENABLED=false
TTS_VOICE=xiaoxiao
```

### 3. 完整配置项说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `LLM_API_KEY` | `""` | DeepSeek / OpenAI 兼容 API Key |
| `LLM_API_BASE` | `https://api.deepseek.com/v1` | API 端点地址 |
| `LLM_MODEL` | `deepseek-chat` | 远程模型名称 |
| `USE_LOCAL_MODEL` | `false` | 是否使用本地模型 |
| `LOCAL_MODEL_URL` | `http://127.0.0.1:8000` | 本地推理服务地址 |
| `TARGET_NAME` | `朋友` | 系统提示词中的角色名 |
| `TARGET_WXID` | `""` | 监控的联系人（逗号分隔），留空=全部 |
| `TTS_ENABLED` | `false` | 是否启用语音合成 |
| `TTS_VOICE` | `xiaoxiao` | 发音人（见 TTS 说明） |
| `LOG_LEVEL` | `INFO` | 日志级别 |

---

## 🚀 使用方法

### 1. 登录微信

打开微信 PC 客户端，**用小号登录**。保持微信窗口**可见**（可以最小化到任务栏，但不能完全隐藏到托盘）。

### 2. 启动机器人

**方式一：双击启动（推荐）**

双击 `start.bat` 即可一键启动。

**方式二：命令行启动**

```bash
cd wechat-bot
py -3.10 bot\main.py
```

### 3. 运行时说明

- 机器人会自动打开指定联系人的聊天窗口
- 每 2 秒轮询一次新消息
- 检测到新消息后自动调用 LLM 生成回复并发送
- 按 `Ctrl+C` 安全停止

---

## 🧪 StyleLearner：从聊天记录学习风格

### 工作原理

`StyleLearner` 模块读取导出的微信聊天记录 CSV，从中提取真实对话消息作为**风格参考示例**，构建成 DeepSeek 的系统提示词。

```
CSV 聊天记录 (2582+ 条消息)
    ↓
读取 → 筛选 → 随机抽样 15 条
    ↓
构建系统提示词：
  [角色描述] + [30条真实示例] + [回复原则]
    ↓
发送给 DeepSeek API → 生成自然回复
```

### 角色配置

在 `bot/style_learner.py` 中配置人设：

```python
PERSONA_DESCRIPTION = """
你是周文慧，19岁，大一女生。
## 性格特征
- 恬静温柔，说话轻声细语
- 有时也会活泼撒娇
- 善良体贴，学妹类型
- 偶尔抱怨学业但不消极
...
"""
```

### 为什么不微调本地模型？

对比测试结果：

| 输入 | 本地 LoRA 模型 | DeepSeek + StyleLearner |
|------|---------------|----------------------|
| 在干嘛呢 | 语句碎片拼接 | "刚洗完澡躺床上呢～今天下午去图书馆写了会儿线代作业[捂脸]" |
| 明天吃饭？ | 答非所问 | "咦？突然约我吃饭呀～[呲牙] 明天下午没课，几点去呀？" |
| 线代考试好慌 | 回复不相关 | "啊？矩阵那章真的好难啊…[流泪]" |

**DeepSeek + StyleLearner 完胜！** 无需 GPU 训练，效果反而更好。

---

## 🔊 语音合成 (TTS)

### 简介

基于 **Microsoft Edge-TTS** 引擎，完全**免费**，无需任何 API Key 或注册账号。使用 Edge 浏览器内置的神经网络语音合成技术，发音自然流畅。

### 配置

```ini
# .env
TTS_ENABLED=true
TTS_VOICE=xiaoxiao       # 可选发音人
```

### 发音人列表

| 配置值 | 发音人 | 性别 | 风格 |
|--------|--------|------|------|
| `xiaoxiao` | 晓晓 | 女声 | 亲切自然（默认） |
| `yunyang` | 云扬 | 男声 | 专业沉稳 |
| `xiaoyi` | 晓伊 | 女声 | 活泼生动 |
| `yunxi` | 云希 | 男声 | 阳光明朗 |

### 工作方式

1. 每次 AI 生成文字回复后，自动调用 Edge-TTS API 生成 MP3 文件
2. 音频文件保存在 `data/audio/` 目录
3. 文件名基于回复内容 MD5 哈希，避免重复生成
4. 首次使用需要联网下载语音模型（约 1-5MB）

### 手动调用

```python
from bot.tts_client import TTSClient

tts = TTSClient(voice="xiaoxiao")
audio_path = tts.speak_sync("你好，今天天气真不错！")
print(f"音频文件：{audio_path}")
```

---

## 🧠 对话记忆系统

### 工作原理

- 使用环形缓冲区（`collections.deque`）存储每个联系人的最近 N 轮对话
- 默认保存最近 20 轮对话，可配置
- 每次回复后自动持久化到 `data/conversation_memory.json`
- 启动时自动加载上一次的记忆

### 记忆格式

```json
{
  "wxid_xxx": [
    {
      "timestamp": 1746452800.0,
      "user": "今天天气真好",
      "bot": "是啊，要出去走走吗？"
    }
  ]
}
```

---

## 📝 开发流程

### 开发背景

本项目旨在通过 AI 技术实现微信聊天的智能化回复，最初从 DeepSeek API 的简单调用开始，逐步演进为完整的机器人系统。

### 版本演进

| 阶段 | 改进内容 |
|------|----------|
| **v1.0** | 基础框架：wx4py 连接 + DeepSeek API 调用 + 人物风格提示词 |
| **v2.0** | 本地模型支持：集成 WeClone 训练的 LoRA 微调 Qwen2.5 模型 |
| **v3.0** | 对话记忆：添加上下文管理、持久化、多联系人隔离 |
| **v4.0** | 语音合成：集成 Edge-TTS，支持多种中文发音人 |
| **v5.0** | 优化完善：消息队列、错误处理、日志系统、文档 |

### 技术选型理由

| 选择 | 理由 |
|------|------|
| **wx4py**（而非 ItChat） | 支持微信 4.x 最新版，UIA 方式更稳定 |
| **Edge-TTS**（而非百度/阿里 TTS） | 完全免费，无需 API Key，中文发音质量高 |
| **Qwen2.5-1.5B**（作为本地模型） | 8GB 显存下可运行的参数最大的中文模型，效果与性价比平衡 |
| **环形缓冲区记忆**（而非数据库） | 轻量级，无需额外依赖，足够满足对话场景 |

---

## ⚠️ 注意事项

1. **微信窗口必须可见** — 基于 UIAutomation 技术，窗口最小化到托盘时将无法读取消息
2. **封号风险** — 个人微信自动化操作有被封可能，**强烈建议使用小号**
3. **不要最小化到托盘** — 可以最小化到任务栏，但不要完全隐藏到系统托盘
4. **微信版本兼容** — 当前适配 4.1.8 版本，微信升级后可能需要更新 wx4py
5. **首次 TTS 需联网** — 第一次使用语音合成时需要下载 Edge TTS 模型
6. **本地 GPU 推理** — 本地模式需要约 3GB 显存

---

## 📁 GitHub 仓库

- 项目地址：[github.com/starlight001219/wechat-clone-bot](https://github.com/starlight001219/wechat-clone-bot)

### 相关项目

- [WeClone](https://github.com/xming521/WeClone) — 微信聊天记录提取与 AI 微调框架
- [ZhouWenHui Chatbot](https://github.com/starlight001219/ai) — 周文慧 AI Web 聊天界面

---

## 📄 许可证

本项目基于上游 [WeClone](https://github.com/xming521/WeClone) 项目改造，请遵守其开源许可证。

---

## 💬 常见问题

**Q: 启动时报错 "Failed to connect"？**
A: 确保微信已打开并登录，且版本为 4.x。

**Q: 机器人不回复消息？**
A: 检查微信窗口是否可见，以及 API Key 配置是否正确。

**Q: TTS 报错 "module not found"？**
A: 运行 `pip install edge-tts` 安装依赖。

**Q: 如何切换发音人？**
A: 修改 `.env` 中的 `TTS_VOICE` 为对应的发音人名。
