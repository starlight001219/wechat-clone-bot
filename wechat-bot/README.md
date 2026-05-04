# 微信机器人 - AI 女友陪伴

基于 WeChatFerry + Claude AI 的微信机器人，能模仿指定好友的语言风格进行自动聊天。

## 功能

- 🤖 **AI 自动回复** — 收到微信消息后 AI 自动生成回复
- 🎭 **语气模仿** — 分析聊天记录，模仿目标人物的说话风格
- 🎤 **语音功能** — 支持文字转语音回复（edge-tts）
- 🧠 **上下文记忆** — 记住对话历史，连贯聊天
- ⏱ **真人延迟** — 模拟真人回复速度

## 环境要求

- **Windows 系统**（需要 WeChatFerry 驱动）
- **Python 3.9+**
- **微信 Windows 客户端已登录**
- **Claude API Key**（或 OpenAI 兼容 API）

## 快速开始

### 1. 安装依赖

```bash
cd wechat-bot
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
复制 .env.example 为 .env
编辑 .env 填写你的 API Key 和目标人物名称
```

### 3. 准备聊天记录

方式一：使用 [WeChatMsg](https://github.com/LC044/WeChatMsg) 导出聊天记录为 JSON
方式二：手动创建 `chat_history.json`（格式参考下方）

```json
{
  "target_name": "她的名字",
  "total_messages": 100,
  "messages": [
    {"sender": "她", "content": "今天好开心呀～", "time": "2024-01-01 12:00:00"},
    {"sender": "我", "content": "怎么啦这么开心", "time": "2024-01-01 12:01:00"},
    {"sender": "她", "content": "你猜猜看嘛>_<", "time": "2024-01-01 12:02:00"}
  ]
}
```

### 4. 分析聊天记录（可选）

```bash
python main.py --analyze
```

会自动用 AI 分析目标人物的语言风格。

### 5. 启动机器人

```bash
python main.py
```

确保微信 Windows 客户端已登录，机器人会自动连接。

## 常用命令

```bash
python main.py              # 启动机器人
python main.py --analyze     # 分析聊天记录风格
python main.py --voices      # 查看可用语音列表
python main.py --history-format  # 查看聊天记录格式
```

## 配置说明

编辑 `.env` 文件：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| ANTHROPIC_API_KEY | Claude API Key | - |
| TARGET_NAME | 要模仿的好友昵称 | - |
| AI_TEMPERATURE | AI 创造力 (0-1) | 0.9 |
| TTS_VOICE | 语音角色 | zh-CN-XiaoxiaoNeural |
| REPLY_MODE | 回复模式 (all/keyword/whitelist) | all |
| WHITELIST_FRIENDS | 白名单好友列表 | - |

## 原理

```
微信消息 → WeChatFerry 接收 → AI 引擎生成回复
    ↓                              ↓
回复发送 ← 文本+语音 ← edge-tts 语音合成
```

## 技术栈

- [WeChatFerry](https://github.com/lich0821/WeChatFerry) — 微信驱动
- [Claude API](https://anthropic.com) — AI 对话引擎
- [edge-tts](https://github.com/rany2/edge-tts) — 语音合成
- [Loguru](https://github.com/Delgan/loguru) — 日志

## 免责声明

本工具仅供学习和研究使用。请遵守微信使用条款和相关法律法规。
