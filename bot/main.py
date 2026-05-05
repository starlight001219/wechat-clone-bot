"""
WeChat AI Bot - Main Entry
Mimics a person's chat style using LLM API + WeChat 4.x automation.
Integrates conversation memory and optional TTS voice output.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from bot.wechat_client import WeChatClient, WeChatMessage
from bot.llm_client import LLMClient
from bot.memory_manager import ConversationMemory
import config


class WeChatBot:
    def __init__(self):
        self.cfg = config.config
        self.wx = WeChatClient()
        self.llm = LLMClient()
        self.memory = ConversationMemory(max_turns=20, storage_dir="data")
        self.tts = None  # lazy init

        logger.remove()
        logger.add(
            sys.stderr,
            level=self.cfg.log_level,
            format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}",
        )
        logger.add(
            "logs/bot_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            level="DEBUG",
        )

        # Restore conversation memory
        self.memory.load_from_disk()
        logger.info(f"Loaded conversation memory. TTS={self.cfg.tts_enabled}, VoiceOnly={self.cfg.voice_only}")

        self.wx.on_message(self.handle_message)

    def _init_tts(self):
        """Lazy init TTS client."""
        if self.tts is None and self.cfg.tts_enabled:
            from bot.tts_client import TTSClient
            try:
                self.tts = TTSClient(voice=self.cfg.tts_voice)
                if not self.tts.available:
                    logger.warning("TTS unavailable (edge-tts not installed)")
                    self.tts = None
                else:
                    logger.info(f"TTS client ready (voice: {self.cfg.tts_voice})")
            except Exception as e:
                logger.warning(f"TTS init failed: {e}")

    def handle_message(self, msg: WeChatMessage):
        """Process incoming message and generate reply."""
        logger.info(f"New message: {msg.sender}: {msg.content[:80]}")

        if msg.is_group:
            return

        # Get conversation context from memory
        context = self.memory.get_context(msg.wxid, max_turns=5)

        # Generate reply via LLM
        reply = self.llm.chat(msg.content, context=context)
        if not reply:
            logger.warning("No reply generated, skipping")
            return

        # Store in memory
        self.memory.add_turn(msg.wxid, msg.content, reply)
        self.memory.save_to_disk()

        # Generate TTS audio if enabled
        if self.cfg.tts_enabled:
            if self.tts is None:
                self._init_tts()
            if self.tts and self.tts.available:
                try:
                    audio_path = self.tts.speak_sync(reply)
                except Exception as e:
                    logger.warning(f"TTS generation error: {e}")
                    audio_path = None
            else:
                audio_path = None
        else:
            audio_path = None

        time.sleep(1)

        if self.cfg.voice_only and audio_path:
            # Voice-only mode: send audio file, skip text
            self.wx.send_audio_file(audio_path, msg.wxid)
            logger.info(f"Voice-only reply sent (text skipped)")
        else:
            # Normal mode: send text reply
            self.wx.send_message(reply, msg.wxid)

        # In non-voice-only mode, still log the audio if generated
        if audio_path and not self.cfg.voice_only:
            logger.info(f"Voice reply generated: {audio_path}")

    def run(self):
        """Start the bot."""
        logger.info("=" * 40)
        logger.info("WeChat AI Bot starting...")
        logger.info(f"Persona: {self.cfg.target_name}")

        target = "星夜"
        logger.info(f"Contact: {target}")
        logger.info("=" * 40)

        if not self.wx.connect():
            logger.error("Failed to connect. Is WeChat open and logged in?")
            return

        self.wx.set_target(target)

        if not self.wx.open_chat_window():
            logger.error(f"Failed to open chat for {target}")
            self.wx.stop()
            return

        self.wx.start_listening()

        logger.info("Bot is running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.memory.save_to_disk()
            self.wx.stop()
            logger.info("Bot stopped")


if __name__ == "__main__":
    bot = WeChatBot()
    bot.run()
