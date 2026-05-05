"""
WeChat client using wx4py for WeChat 4.x.
Simple approach: open chat once, poll message list on main window.
"""

import time
import threading
from dataclasses import dataclass
from typing import Optional, Callable, Set
from loguru import logger

import wx4py
from wx4py.core import uiautomation as uia
import win32gui
import win32con

_MESSAGE_CLASSES = {
    "mmui::ChatTextItemView",
    "mmui::ChatBubbleItemView",
}


@dataclass
class WeChatMessage:
    sender: str
    content: str
    wxid: str
    roomid: str = ""
    is_group: bool = False


# ---------------------------------------------------------------------------
# UIA helpers
# ---------------------------------------------------------------------------

def _safe_text(ctrl, attr: str) -> str:
    try:
        return str(getattr(ctrl, attr, "") or "")
    except Exception:
        return ""


def _safe_children(ctrl) -> list:
    try:
        return list(ctrl.GetChildren())
    except Exception:
        return []


def _find_contact_by_name(root, name: str) -> Optional[object]:
    """Find a session list item by contact name in the main window."""
    try:
        sl = root.ListControl(AutomationId="session_list")
        if sl.Exists(maxSearchSeconds=0.5):
            for item in _safe_children(sl):
                if name in _safe_text(item, "Name"):
                    return item
    except Exception:
        pass
    try:
        for ctrl, _depth in uia.WalkControl(root, includeTop=True, maxDepth=6):
            if _safe_text(ctrl, "ControlTypeName") != "ListControl":
                continue
            if _safe_text(ctrl, "AutomationId") == "session_list" or \
               _safe_text(ctrl, "Name") == "会话":
                for item in _safe_children(ctrl):
                    if name in _safe_text(item, "Name"):
                        return item
    except Exception:
        pass
    return None


def _find_message_list(root):
    """Find the chat_message_list from a window root."""
    try:
        msg_list = root.ListControl(AutomationId="chat_message_list")
        if msg_list.Exists(maxSearchSeconds=0.5):
            return msg_list
    except Exception:
        pass
    try:
        for control, _depth in uia.WalkControl(root, includeTop=True, maxDepth=8):
            if _safe_text(control, "ControlTypeName") != "ListControl":
                continue
            score = 0
            for child in _safe_children(control)[-12:]:
                cls = _safe_text(child, "ClassName")
                if cls in _MESSAGE_CLASSES:
                    score += 10
            if score >= 10:
                return control
    except Exception:
        pass
    return None


def _read_message_texts(msg_list) -> list:
    """Read message texts from the message list, newest first."""
    texts = []
    for child in _safe_children(msg_list):
        cls = _safe_text(child, "ClassName")
        name = _safe_text(child, "Name").strip()
        if not name:
            continue
        if cls in _MESSAGE_CLASSES:
            texts.append(name)
    return texts[::-1]  # newest first


# ---------------------------------------------------------------------------
# WeChatClient
# ---------------------------------------------------------------------------

class WeChatClient:
    """
    Monitors a specific contact's chat by:
    1. Opening the chat once at startup
    2. Polling the message list control for new messages
    3. Sending replies via wx4py
    """

    def __init__(self):
        self._wx = wx4py.WeChatClient()
        self._running = False
        self._on_message_cb: Optional[Callable] = None
        self._thread: Optional[threading.Thread] = None
        self._known: Set[str] = set()  # message texts we've already seen
        self._target: str = ""

    def connect(self) -> bool:
        try:
            result = self._wx.connect()
            if result:
                logger.info("Connected to WeChat via wx4py")
            return result
        except Exception as e:
            logger.error(f"Connect failed: {e}")
            return False

    def set_target(self, name: str):
        """Set the contact to monitor."""
        self._target = name

    def open_chat_window(self) -> bool:
        """Open the target chat once and maximize the window."""
        if not self._target:
            logger.error("No target set")
            return False
        try:
            self._wx.chat_window.open_chat(self._target, target_type='contact')
            time.sleep(1.0)
            # Maximize window so it's visible and UIA can read it
            hwnd = self._wx.window.hwnd
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            time.sleep(1.0)
            # Load initial messages so we don't reply to old ones
            self._load_initial_messages()
            logger.info(f"Chat window opened and maximized for {self._target}")
            return True
        except Exception as e:
            logger.error(f"Failed to open chat for {self._target}: {e}")
            return False

    def _load_initial_messages(self):
        """Read and cache all current messages as 'already seen'."""
        msg_list = _find_message_list(self._wx.window.uia.root)
        if msg_list:
            texts = _read_message_texts(msg_list)
            for t in texts:
                self._known.add(t)
            logger.info(f"Cached {len(texts)} existing messages as seen")

    def send_audio_file(self, file_path: str, who: str) -> bool:
        """Send an audio file as a file attachment to the target contact."""
        try:
            self._wx.chat_window.send_file_to(who, file_path, target_type='contact')
            logger.info(f"Sent audio to {who}: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Send audio to {who} failed: {e}")
            return False

    def send_message(self, message: str, who: str) -> bool:
        """Send a reply to the target contact."""
        if not message.strip():
            return False
        try:
            # Ensure window is active before sending
            hwnd = self._wx.window.hwnd
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass
            time.sleep(0.3)

            self._wx.chat_window.send_to(who, message, target_type='contact')
            self._known.add(message)  # don't echo ourselves
            logger.info(f"Sent to {who}: {message[:50]}")
            return True
        except Exception as e:
            logger.error(f"Send to {who} failed: {e}")
            return False

    def on_message(self, callback: Callable):
        self._on_message_cb = callback

    def start_listening(self):
        """Start polling the message list for new messages."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Message polling started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self._wx.disconnect()

    def _poll_loop(self):
        """Poll the message list for new unseen messages."""
        while self._running:
            try:
                root = self._wx.window.uia.root
                if not root:
                    time.sleep(2)
                    continue

                msg_list = _find_message_list(root)
                if not msg_list:
                    time.sleep(2)
                    continue

                texts = _read_message_texts(msg_list)
                for t in texts:
                    if t not in self._known:
                        self._known.add(t)
                        logger.info(f"New message detected: {t[:60]}")
                        if self._on_message_cb:
                            msg = WeChatMessage(
                                sender=self._target,
                                content=t,
                                wxid=self._target,
                            )
                            self._on_message_cb(msg)
                        break  # only process the newest one per cycle
            except Exception as e:
                logger.debug(f"Poll error: {e}")
            time.sleep(2)
