"""
WeChat AI Bot - Main Entry
Mimics a person's chat style using LLM API + WeChat 4.x automation.
Integrates conversation memory and optional TTS voice output.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from bot.wechat_client import WeChatClient, WeChatMessage
from bot.llm_client import LLMClient
from bot.memory_manager import ConversationMemory
from bot.asr_client import ASRClient
from bot.voice_call_client import VoiceCallSession, find_cable_devices, set_cable_as_default_mic
import config


class WeChatBot:
    def __init__(self):
        self.cfg = config.config
        self.wx = WeChatClient()
        self.llm = LLMClient()
        self.memory = ConversationMemory(max_turns=20, storage_dir="data")
        self.tts = None  # lazy init
        self.asr = ASRClient(language=self.cfg.asr_language) if self.cfg.asr_enabled else None
        self._voice_in_progress = False

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
        logger.info(f"Loaded conversation memory. TTS={self.cfg.tts_enabled}, VoiceOnly={self.cfg.voice_only}, ASR={self.cfg.asr_enabled}")

        self.wx.on_message(self.handle_message)

    def start_voice_call(self):
        """Start a voice call with 星夜 and run the conversation loop."""
        logger.info("=" * 40)
        logger.info("Starting voice call mode")
        logger.info("=" * 40)

        if not self.wx.connect():
            logger.error("Failed to connect to WeChat")
            return

        self.wx.set_target(self.cfg.voice_call_target)
        self.wx.open_chat_window()

        # Init TTS
        self._init_tts()
        if not self.tts or not self.tts.available:
            logger.error("TTS not available, voice call cannot work")
            self.wx.stop()
            return

        # Run voice call
        session = VoiceCallSession(
            llm_client=self.llm,
            tts_client=self.tts,
            asr_client=self.asr,
        )
        try:
            session.run()
        except KeyboardInterrupt:
            logger.info("Voice call interrupted by user")
        finally:
            self.wx.stop()
            logger.info("Voice call session ended")

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
        if msg.is_group:
            return

        # Voice message → ASR pipeline
        if msg.is_voice:
            self._handle_voice_message(msg)
            return

        logger.info(f"New message: {msg.sender}: {msg.content[:80]}")

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
                    tts_path = self.tts.speak_sync(reply)
                except Exception as e:
                    logger.warning(f"TTS generation error: {e}")
                    tts_path = None
            else:
                tts_path = None
        else:
            tts_path = None

        time.sleep(1)

        if self.cfg.voice_only and tts_path:
            # Voice-only mode: send audio file, skip text
            self.wx.send_audio_file(tts_path, msg.wxid)
            logger.info(f"Voice-only reply sent (text skipped)")
        else:
            # Normal mode: send text reply
            self.wx.send_message(reply, msg.wxid)

        # In non-voice-only mode, still log the audio if generated
        if tts_path and not self.cfg.voice_only:
            logger.info(f"Voice reply generated: {tts_path}")

    def _handle_voice_message(self, msg: WeChatMessage):
        """Play voice → record → ASR transcribe → LLM reply → TTS → send audio."""
        logger.info(f"Processing voice message from {msg.sender}")

        if self._voice_in_progress:
            logger.warning("Voice message already being processed, skipping")
            return

        if not self.asr or not self.asr.available:
            logger.warning("ASR not available, skipping voice message")
            return

        self._voice_in_progress = True
        try:
            # Record system audio while clicking play on the voice message
            duration = self.cfg.asr_record_seconds
            wav_path = self.asr.record_audio(
                duration=duration,
                on_start=lambda: self.wx.play_voice_message(),
            )
            if not wav_path:
                logger.error("Failed to record voice message audio")
                return

            # Transcribe recorded audio to text
            text = self.asr.transcribe(wav_path)
            try:
                os.unlink(wav_path)
            except Exception:
                pass

            if not text:
                logger.warning("ASR could not transcribe voice message")
                return

            logger.info(f"ASR transcribed: {text}")

            # Generate LLM reply (same as text message)
            context = self.memory.get_context(msg.wxid, max_turns=5)
            reply = self.llm.chat(text, context=context)
            if not reply:
                return

            # Store conversation
            self.memory.add_turn(msg.wxid, text, reply)
            self.memory.save_to_disk()

            # Generate TTS audio and send
            tts_path = None
            if self.cfg.tts_enabled:
                if self.tts is None:
                    self._init_tts()
                if self.tts and self.tts.available:
                    try:
                        tts_path = self.tts.speak_sync(reply)
                    except Exception as e:
                        logger.warning(f"TTS generation error: {e}")

            time.sleep(1)

            if self.cfg.voice_only and tts_path:
                self.wx.send_audio_file(tts_path, msg.wxid)
                logger.info("Voice-only reply sent (text skipped)")
            else:
                self.wx.send_message(reply, msg.wxid)

            if tts_path and not self.cfg.voice_only:
                logger.info(f"Voice reply generated: {tts_path}")

        finally:
            self._voice_in_progress = False

    def run(self):
        """Start the bot."""
        logger.info("=" * 40)
        logger.info("WeChat AI Bot starting...")
        logger.info(f"Persona: {self.cfg.target_name}")

        target = self.cfg.voice_call_target
        logger.info(f"Contact: {target}")

        # Voice call mode
        if self.cfg.voice_call_enabled:
            logger.info("Mode: VOICE CALL")
            logger.info("=" * 40)
            self.start_voice_call()
            return

        logger.info("Mode: TEXT CHAT")
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
