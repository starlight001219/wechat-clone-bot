"""微信消息处理器 - 使用 omni-bot-sdk 驱动"""

import sys
import time
import random
import threading
import os.path
from pathlib import Path
from typing import Callable, Optional
from loguru import logger


class WeChatHandler:
    """基于 omni-bot-sdk 的微信消息处理器"""

    def __init__(self, on_message: Optional[Callable] = None):
        """
        Args:
            on_message: 消息回调，签名 on_message(sender_name, content, sender_id)
        """
        self.on_message = on_message
        self._bot = None
        self._msg_service = None
        self._window_mgr = None
        self._running = False
        self._known_senders: dict[str, str] = {}  # name -> display name

    def start(self, config_path: str = "") -> bool:
        """启动微信连接"""
        try:
            sdk_path = os.path.join(
                os.path.dirname(__file__), '..', '..', 'omni-bot-sdk-oss', 'src'
            )
            sys.path.insert(0, os.path.abspath(sdk_path))
            from omni_bot_sdk.bot import Bot

            if not config_path:
                config_path = os.path.join(
                    os.path.dirname(__file__), '..', 'omni_config.yaml'
                )

            self._bot = Bot(config_path=config_path)
            logger.info(f"微信用户: {self._bot.user_info.nickname}")
            logger.info(f"版本: {self._bot.user_info.version}")

            self._window_mgr = self._bot.window_manager

            # 校准 UI 位置（非必需，发送功能可能受限）
            try:
                self._window_mgr.init_chat_window()
            except Exception as e:
                logger.warning(f"窗口校准不完整: {e}")

            # 启动消息监听
            from omni_bot_sdk.services.core.message_service import MessageService
            self._msg_service = MessageService(
                self._bot.message_queue, self._bot.db
            )
            self._msg_service.set_callback(self._on_new_messages)
            self._msg_service.start()

            self._running = True
            logger.info("消息监听已启动")
            return True

        except ImportError as e:
            logger.error(f"导入失败: {e}")
            return False
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False

    def stop(self):
        """停止"""
        self._running = False
        if self._msg_service:
            try:
                self._msg_service.stop()
            except Exception:
                pass
        logger.info("微信处理器已关闭")

    def _on_new_messages(self, messages: list):
        """omni-bot-sdk 消息回调 - 处理数据库轮询消息"""
        if not self.on_message or not self._running:
            return

        for msg in messages:
            try:
                # 消息格式: (table_name, db_row_tuple)
                # db_row_tuple: [local_id, server_id, type, seq, sender_id, time,
                #                 status, ... , source(11), content(12), ..., db_path(17)]
                if not isinstance(msg, (list, tuple)) or len(msg) < 2:
                    continue

                db_row = msg[1]
                if not isinstance(db_row, (list, tuple)) or len(db_row) < 13:
                    continue

                # 只处理文本消息 (type=1)
                msg_type = db_row[2]
                if msg_type != 1:
                    continue

                # 消息内容 (index 12)
                content = str(db_row[12]) if db_row[12] else ""
                if not content:
                    continue

                # 发送者标识 (index 11=source, 或 index 4=sender_id)
                sender_raw = db_row[11]
                if isinstance(sender_raw, str) and sender_raw:
                    sender = sender_raw
                else:
                    sender = str(db_row[4])

                logger.info(f"[{sender}] {content[:80]}")
                self.on_message(sender, content, sender)

            except Exception as e:
                logger.error(f"处理消息出错: {e}")

    def send_text(self, text: str, receiver: str = "") -> bool:
        """发送文本消息"""
        try:
            if not self._window_mgr:
                return False

            if receiver and not self._window_mgr.switch_session(receiver):
                logger.warning(f"切换到 [{receiver}] 失败")
                return False

            from omni_bot_sdk.rpa.message_sender import MessageSender
            sender = MessageSender(self._window_mgr)
            result = sender.send_message(text)
            if result:
                logger.info(f"已发送 -> {receiver}: {text[:40]}")
            return result

        except Exception as e:
            logger.error(f"发送失败: {e}")
            return False

    def send_voice(self, voice_path: str, receiver: str = "") -> bool:
        """发送语音文件"""
        try:
            if not os.path.exists(voice_path):
                return False
            if not self._window_mgr:
                return False

            if receiver and not self._window_mgr.switch_session(receiver):
                return False

            import pyautogui
            from omni_bot_sdk.utils.helpers import copy_file_to_clipboard

            if not self._window_mgr.activate_input_box():
                return False
            if not copy_file_to_clipboard(voice_path):
                return False

            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.5)
            pyautogui.press("enter")
            logger.info(f"已发送语音: {voice_path}")
            return True

        except Exception as e:
            logger.error(f"发送语音失败: {e}")
            return False

    def reply_with_delay(self, text: str, receiver: str = "",
                         delay_range: tuple[float, float] = None):
        """带随机延迟回复"""
        if delay_range is None:
            delay_range = (1.0, 5.0)

        def _do():
            time.sleep(random.uniform(*delay_range))
            self.send_text(text, receiver)

        threading.Thread(target=_do, daemon=True).start()

    def reply_with_voice_delay(self, text: str, voice_path: str,
                                receiver: str = "",
                                delay_range: tuple[float, float] = None):
        """带延迟回复文字+语音"""
        if delay_range is None:
            delay_range = (1.0, 5.0)

        def _do():
            time.sleep(random.uniform(*delay_range))
            self.send_text(text, receiver)
            time.sleep(0.3)
            self.send_voice(voice_path, receiver)

        threading.Thread(target=_do, daemon=True).start()
