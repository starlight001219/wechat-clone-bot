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

_MESSAGE_CLASSES_TEXT = {
    "mmui::ChatTextItemView",
    "mmui::ChatBubbleItemView",
}
_MESSAGE_CLASSES_VOICE = {
    "mmui::ChatVoiceItemView",
    "mmui::ChatVoiceBubbleView",
}
_MESSAGE_CLASSES = _MESSAGE_CLASSES_TEXT | _MESSAGE_CLASSES_VOICE


@dataclass
class WeChatMessage:
    sender: str
    content: str
    wxid: str
    roomid: str = ""
    is_group: bool = False
    is_voice: bool = False


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


def _element_key(class_name: str, text: str, element) -> str:
    """Generate a dedup key for a chat element (text or voice)."""
    if class_name in _MESSAGE_CLASSES_VOICE:
        # Use element position as unique key (voice messages might share text)
        try:
            rect = str(element.BoundingRectangle)
            return f"voice:{rect}"
        except Exception:
            return f"voice:{text}"
    # Text messages: dedup by content
    return f"text:{text}"


_atomic_id_counter = 0


def _next_id() -> str:
    """Return a unique monotonic ID for fallback dedup."""
    global _atomic_id_counter
    _atomic_id_counter += 1
    return str(_atomic_id_counter)


def _read_chat_elements(msg_list) -> list:
    """Read all message elements (text + voice) from the message list, newest first.

    Returns list of (text, class_name, is_voice, element) tuples.
    """
    items = []
    for child in _safe_children(msg_list):
        cls = _safe_text(child, "ClassName")
        name = _safe_text(child, "Name").strip()
        if cls not in _MESSAGE_CLASSES:
            continue
        if not name and cls not in _MESSAGE_CLASSES_VOICE:
            continue
        is_voice = cls in _MESSAGE_CLASSES_VOICE
        items.append((name or "[语音]", cls, is_voice, child))
    return items[::-1]


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
            elements = _read_chat_elements(msg_list)
            for text, cls, is_voice, elem in elements:
                self._known.add(_element_key(cls, text, elem))
            logger.info(f"Cached {len(elements)} existing messages as seen")

    def send_audio_file(self, file_path: str, who: str) -> bool:
        """Send an audio file as a file attachment to the target contact."""
        try:
            self._wx.chat_window.send_file_to(who, file_path, target_type='contact')
            logger.info(f"Sent audio to {who}: {file_path}")
            self._mark_own_messages_as_seen()
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
            self._known.add(f"text:{message}")  # don't echo ourselves
            self._mark_own_messages_as_seen()
            logger.info(f"Sent to {who}: {message[:50]}")
            return True
        except Exception as e:
            logger.error(f"Send to {who} failed: {e}")
            return False

    def _mark_own_messages_as_seen(self, max_wait: float = 3.0):
        """After sending, wait for own message UI element to appear and mark it seen."""
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(0.5)
            try:
                root = self._wx.window.uia.root
                if not root:
                    continue
                msg_list = _find_message_list(root)
                if not msg_list:
                    continue
                new_count = 0
                for text, cls, is_voice, elem in _read_chat_elements(msg_list):
                    key = _element_key(cls, text, elem)
                    if key not in self._known:
                        self._known.add(key)
                        new_count += 1
                if new_count > 0:
                    return
            except Exception:
                pass

    def play_voice_message(self) -> bool:
        """Find and click the most recent voice message to start playback."""
        try:
            root = self._wx.window.uia.root
            if not root:
                return False
            msg_list = _find_message_list(root)
            if not msg_list:
                return False
            for text, cls, is_voice, elem in _read_chat_elements(msg_list):
                if is_voice:
                    elem.Click()
                    logger.info(f"Clicked voice message to play")
                    return True
            logger.warning("No voice message element found to click")
            return False
        except Exception as e:
            logger.error(f"Failed to click voice message: {e}")
            return False

    def discover_message_classes(self) -> list:
        """Scan message list and return ALL unique class names found (for debugging voice detection)."""
        classes = set()
        try:
            root = self._wx.window.uia.root
            if not root:
                return []
            msg_list = _find_message_list(root)
            if not msg_list:
                return []
            for child in _safe_children(msg_list):
                cls = _safe_text(child, "ClassName")
                if cls:
                    classes.add(cls)
            result = sorted(classes)
            logger.info(f"Discovered message classes: {result}")
            return result
        except Exception as e:
            logger.error(f"Class discovery failed: {e}")
            return []

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

                for text, cls, is_voice, elem in _read_chat_elements(msg_list):
                    key = _element_key(cls, text, elem)
                    if key not in self._known:
                        self._known.add(key)
                        if is_voice:
                            logger.info(f"New voice message detected")
                        else:
                            logger.info(f"New message detected: {text[:60]}")
                        if self._on_message_cb:
                            msg = WeChatMessage(
                                sender=self._target,
                                content=text,
                                wxid=self._target,
                                is_voice=is_voice,
                            )
                            self._on_message_cb(msg)
                        break  # only process the newest one per cycle
            except Exception as e:
                logger.debug(f"Poll error: {e}")
            time.sleep(2)
