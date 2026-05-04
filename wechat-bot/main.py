"""
微信机器人主程序 - AI 女友机器人
================================

工作流程:
  1. 加载配置和聊天记录
  2. 分析目标人物的语言风格
  3. 连接微信，启动消息监听
  4. 收到消息 -> AI 生成回复 -> 文本 + 语音发送

使用方法:
  python main.py          # 启动机器人
  python main.py --analyze  # 仅分析聊天记录
  python main.py --voices   # 查看可用语音列表

首次使用:
  1. 复制 .env.example 为 .env，填写配置
  2. 准备聊天记录文件 chat_history.json
  3. 确保 Windows 微信客户端已登录
  4. 运行 python main.py
"""

import sys
import signal
import argparse
from pathlib import Path
from loguru import logger

from config import settings
from bot.personality import Personality
from bot.engine import AIEngine
from wechat.handler import WeChatHandler
from tts.speaker import VoiceSpeaker
from tools.history_export import manual_format_example


# ========== 日志配置 ==========
def setup_logging():
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:7}</level> | <cyan>{message}</cyan>",
        level=settings.log_level,
        colorize=True,
    )
    logger.add(
        str(log_path),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:7} | {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
    )
    logger.info("=" * 50)
    logger.info("微信机器人启动")
    logger.info(f"目标人物: {settings.target_name}")
    logger.info(f"AI 模型: {settings.ai_model}")
    logger.info(f"语音功能: {'开启' if settings.tts_enabled else '关闭'}")
    logger.info(f"回复模式: {settings.reply_mode}")
    logger.info("=" * 50)


# ========== 核心业务逻辑 ==========
class WeChatBot:
    """微信机器人主控制器"""

    def __init__(self):
        self.personality = Personality(
            name=settings.target_name,
            history_file=settings.chat_history_file,
            max_rounds=settings.max_context_rounds,
        )
        self.engine = AIEngine(self.personality)
        self.speaker = VoiceSpeaker()
        self.wechat = WeChatHandler(on_message=self._on_message)

    def start(self):
        """启动机器人"""
        # 1. 加载风格
        self.personality.load_style_profile()

        # 2. 连接微信
        if not self.wechat.start():
            logger.error("微信连接失败！请确保:")
            logger.error("1. 微信 Windows 客户端已登录")
            logger.error("2. omni-bot-sdk 已正确安装")
            return False

        logger.info("机器人已上线！等待消息中...")
        return True

    def stop(self):
        """停止机器人"""
        logger.info("正在关闭机器人...")
        self.wechat.stop()
        logger.info("机器人已关闭")

    def _on_message(self, sender_name: str, content: str, wxid: str):
        """收到消息时的回调"""
        logger.info(f"[{sender_name}] {content}")

        # AI 生成回复
        reply = self.engine.generate_reply(content)
        if not reply:
            logger.warning("AI 生成回复失败")
            return

        logger.info(f"[机器人 -> {sender_name}] {reply}")

        # 发送文本回复
        self.wechat.reply_with_delay(reply, wxid)

        # 语音回复
        if settings.tts_enabled:
            voice_path = self.speaker.text_to_speech(reply)
            if voice_path:
                self.wechat.reply_with_voice_delay(reply, voice_path, wxid)


# ========== 命令行功能 ==========
def do_analyze():
    """分析聊天记录风格"""
    logger.info(f"开始分析 {settings.target_name} 的语言风格...")

    personality = Personality(
        name=settings.target_name,
        history_file=settings.chat_history_file,
    )

    if not personality.load_style_profile():
        logger.error(f"聊天记录文件不存在: {settings.chat_history_file}")
        logger.info("你可以:")
        logger.info("1. 使用 WeChatMsg (https://github.com/LC044/WeChatMsg) 导出聊天记录")
        logger.info("2. 手动创建 chat_history.json (格式参考 python tools/history_export.py)")
        return

    engine = AIEngine(personality)

    # 读取原始消息
    import json
    data = json.loads(Path(settings.chat_history_file).read_text(encoding="utf-8"))
    messages = data if isinstance(data, list) else data.get("messages", [])

    analysis = engine.analyze_style(messages)
    if analysis:
        print("\n" + "=" * 60)
        print("语言风格分析报告")
        print("=" * 60)
        print(analysis)
        print("=" * 60)

        # 保存分析结果
        result_path = Path(settings.chat_history_file)
        result_data = data if isinstance(data, dict) else {"messages": data}
        result_data["style_analysis"] = analysis
        result_path.write_text(
            json.dumps(result_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"分析结果已保存到 {result_path}")
    else:
        logger.error("风格分析失败，请检查 API Key 配置")


def do_list_voices():
    """列出可用中文语音"""
    speaker = VoiceSpeaker()
    voices = speaker.get_available_voices()
    if voices:
        print("\n可用中文语音:")
        print("-" * 40)
        for v in voices:
            print(f"  {v['name']} ({v['gender']})")
        print("-" * 40)
        print("在 .env 中设置 TTS_VOICE 使用")
    else:
        print("获取语音列表失败，请安装 edge-tts: pip install edge-tts")


def do_history_format():
    """打印聊天记录格式示例"""
    manual_format_example()


# ========== 入口 ==========
def main():
    parser = argparse.ArgumentParser(description="微信机器人 - AI 女友陪伴")
    parser.add_argument("--analyze", action="store_true", help="仅分析聊天记录风格")
    parser.add_argument("--voices", action="store_true", help="查看可用语音列表")
    parser.add_argument("--history-format", action="store_true", help="查看聊天记录格式")
    args = parser.parse_args()

    setup_logging()

    if args.analyze:
        do_analyze()
        return

    if args.voices:
        do_list_voices()
        return

    if args.history_format:
        do_history_format()
        return

    # 启动完整机器人
    bot = WeChatBot()

    def signal_handler(sig, frame):
        logger.info("收到中断信号")
        bot.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if bot.start():
        # 保持主线程运行
        signal.pause()


if __name__ == "__main__":
    main()
