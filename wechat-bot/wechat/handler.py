"""微信消息处理器 - 使用 WeChatFerry 与微信客户端交互"""

import time
import random
import threading
from typing import Callable, Optional
from loguru import logger

from config import settings, get_whitelist, get_reply_mode


class WeChatHandler:
    """微信消息收发处理器"""

    def __init__(self, on_message: Optional[Callable] = None):
        self.wcf = None
        self.running = False
        self.on_message = on_message  # 回调: on_message(sender_name, content, wxid)
        self._bot_wxid: Optional[str] = None
        self._bot_name: Optional[str] = None
        self._contacts: dict[str, str] = {}  # wxid -> name

    def start(self):
        """启动微信连接"""
        try:
            import wcf
            self.wcf = wcf.Wcf()
            logger.info("WeChatFerry 连接成功")

            # 获取机器人自身信息
            self._bot_wxid = self.wcf.get_self_wxid()
            logger.info(f"机器人微信ID: {self._bot_wxid}")

            # 获取通讯录
            self._refresh_contacts()

            # 启动消息监听
            self.running = True
            self._listen_thread = threading.Thread(target=self._message_loop, daemon=True)
            self._listen_thread.start()
            logger.info("消息监听已启动")

            return True

        except ImportError:
            logger.error("未安装 wcf 库，请运行: pip install wcf")
            return False
        except Exception as e:
            logger.error(f"微信连接失败: {e}")
            return False

    def stop(self):
        """停止微信连接"""
        self.running = False
        if self.wcf:
            try:
                self.wcf.cleanup()
            except Exception:
                pass
        logger.info("微信连接已关闭")

    def _refresh_contacts(self):
        """刷新通讯录"""
        try:
            contacts = self.wcf.get_contacts()
            self._contacts = {}
            for c in contacts:
                wxid = c.get("wxid", "")
                name = c.get("name", "") or c.get("remark", "") or c.get("nickname", "")
                if wxid and name:
                    self._contacts[wxid] = name
            logger.info(f"已加载 {len(self._contacts)} 个联系人")
        except Exception as e:
            logger.error(f"获取通讯录失败: {e}")

    def get_contact_name(self, wxid: str) -> str:
        """获取联系人名称"""
        return self._contacts.get(wxid, wxid)

    def _message_loop(self):
        """消息监听循环"""
        while self.running:
            try:
                msgs = self.wcf.get_msg()
                for msg in msgs:
                    self._process_message(msg)
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"消息监听异常: {e}")
                time.sleep(1)

    def _process_message(self, msg: dict):
        """处理单条消息"""
        try:
            msg_type = msg.get("type", 0)
            content = msg.get("content", "").strip()
            sender = msg.get("sender", "")
            roomid = msg.get("roomid", "")

            # 只处理文本消息 (type=1)
            if msg_type != 1 or not content:
                return

            # 跳过自己的消息
            if sender == self._bot_wxid:
                return

            # 获取发送者名称
            sender_name = self.get_contact_name(sender)

            # 判断是否应该回复
            if not self._should_reply(sender_name, sender, content):
                return

            logger.info(f"收到消息 from {sender_name}({sender}): {content}")

            # 调用回调
            if self.on_message:
                self.on_message(sender_name, content, sender)

        except Exception as e:
            logger.error(f"消息处理异常: {e}")

    def _should_reply(self, name: str, wxid: str, content: str) -> bool:
        """判断是否应该回复"""
        mode = get_reply_mode()

        if mode == "whitelist":
            whitelist = get_whitelist()
            return name in whitelist or wxid in whitelist

        if mode == "keyword":
            keywords = get_whitelist()
            if not keywords:
                return True  # 无关键词时默认回复全部
            return any(kw in content for kw in keywords)

        # mode == "all"
        return True

    def send_text(self, text: str, receiver: str):
        """发送文本消息"""
        if not self.wcf:
            logger.warning("微信未连接")
            return False

        try:
            self.wcf.send_text(text, receiver)
            logger.info(f"已发送消息给 {receiver}: {text[:50]}...")
            return True
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False

    def send_voice(self, voice_path: str, receiver: str):
        """发送语音消息"""
        if not self.wcf:
            logger.warning("微信未连接")
            return False

        try:
            self.wcf.send_file(voice_path, receiver)
            logger.info(f"已发送语音给 {receiver}")
            return True
        except Exception as e:
            logger.error(f"发送语音失败: {e}")
            return False

    def reply_with_delay(self, text: str, receiver: str, delay_range: tuple[float, float] = None):
        """带延迟回复，模拟真人"""
        if delay_range is None:
            delay_range = (settings.reply_delay_min, settings.reply_delay_max)

        def _do_reply():
            delay = random.uniform(*delay_range)
            logger.info(f"回复延迟 {delay:.1f} 秒")
            time.sleep(delay)
            self.send_text(text, receiver)

        threading.Thread(target=_do_reply, daemon=True).start()

    def reply_with_voice_delay(self, text: str, voice_path: str, receiver: str, delay_range: tuple[float, float] = None):
        """带延迟回复语音"""
        if delay_range is None:
            delay_range = (settings.reply_delay_min, settings.reply_delay_max)

        def _do_reply():
            delay = random.uniform(*delay_range)
            logger.info(f"语音回复延迟 {delay:.1f} 秒")
            time.sleep(delay)
            self.send_text(text, receiver)
            time.sleep(0.5)
            self.send_voice(voice_path, receiver)

        threading.Thread(target=_do_reply, daemon=True).start()
