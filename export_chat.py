"""
导出微信聊天记录供 WeClone 微调使用。
打开指定联系人的聊天窗口，滚动加载历史消息，导出为 CSV。
"""

import sys
import os
import time
import csv
import re
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loguru import logger
import win32gui
import win32con
import win32api

import wx4py
from wx4py.core import uiautomation as uia

try:
    import UIAutomationClient as _uia_client
except ImportError:
    _uia_client = None


_MESSAGE_CLASSES = {
    "mmui::ChatTextItemView",
    "mmui::ChatBubbleItemView",
}
_TIME_CLASS = "mmui::ChatItemView"


def _safe_text(ctrl, attr):
    try:
        return str(getattr(ctrl, attr, "") or "")
    except Exception:
        return ""


def _safe_children(ctrl):
    try:
        return list(ctrl.GetChildren())
    except Exception:
        return []


def find_message_list(root):
    try:
        ml = root.ListControl(AutomationId="chat_message_list")
        if ml.Exists(maxSearchSeconds=0.5):
            return ml
    except Exception:
        pass
    try:
        for ctrl, _depth in uia.WalkControl(root, includeTop=True, maxDepth=8):
            if _safe_text(ctrl, "ControlTypeName") != "ListControl":
                continue
            for child in _safe_children(ctrl)[-12:]:
                cls = _safe_text(child, "ClassName")
                if cls in _MESSAGE_CLASSES:
                    return ctrl
    except Exception:
        pass
    return None


def _safe_bounding(ctrl):
    """Get bounding rectangle center X of a control."""
    try:
        bb = ctrl.BoundingRectangle
        return (bb.left + bb.right) // 2
    except Exception:
        return None


def read_all_items(msg_list):
    """Read all visible items (messages + timestamps) from the message list.

    Determines sender by bubble position: left side = 周文慧(self/is_sender=1),
    right side = 星夜(other/is_sender=0).
    """
    # Find the center X of the message list to differentiate left/right
    list_center = _safe_bounding(msg_list)

    items = []
    for child in _safe_children(msg_list):
        cls = _safe_text(child, "ClassName")
        name = _safe_text(child, "Name").strip()
        if not name:
            continue
        if cls in _MESSAGE_CLASSES:
            msg_x = _safe_bounding(child)
            is_left = msg_x is not None and list_center is not None and msg_x < list_center
            items.append({
                "type": "message",
                "text": name,
                "is_left": is_left,
            })
        elif cls == _TIME_CLASS:
            items.append({"type": "time", "text": name})
    return items


def _get_msg_list_center(msg_list):
    """Get the screen-center coordinates of the message list control."""
    try:
        bb = msg_list.BoundingRectangle
        cx = (bb.left + bb.right) // 2
        cy = (bb.top + bb.bottom) // 2
        return cx, cy
    except Exception:
        return None, None


def scroll_up(msg_list, count=5):
    """Scroll up by sending mouse wheel events over the message list."""
    cx, cy = _get_msg_list_center(msg_list)
    if cx is None:
        return
    try:
        win32api.SetCursorPos((cx, cy))
    except Exception:
        pass
    for _ in range(count):
        try:
            win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, 120, 0)
            time.sleep(0.15)
        except Exception:
            time.sleep(0.1)


def export_chat_history(contact_name: str, max_scrolls: int = 500, known_texts: set = None) -> list:
    """
    Open a contact's chat, scroll up repeatedly, collect all unique messages.

    Args:
        contact_name: Name of the contact to export
        max_scrolls: Maximum number of scroll rounds
        known_texts: Set of message texts already seen (for append mode),
                     these will be pre-populated into seen_texts to avoid duplicates

    Returns:
        List of (text, is_sender_other) tuples, in chronological order.
    """
    wx = wx4py.WeChatClient()
    if not wx.connect():
        logger.error("Failed to connect to WeChat")
        return []

    hwnd = wx.window.hwnd

    # Open the contact's chat
    wx.chat_window.open_chat(contact_name, target_type='contact')
    time.sleep(2)

    # Maximize so we can see more messages
    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    time.sleep(1)

    # Main loop: scroll up, collect new messages
    all_items = []  # ordered list of (text, type)
    seen_texts = set(known_texts) if known_texts else set()
    no_new_count = 0

    for scroll_round in range(max_scrolls):
        msg_list = find_message_list(wx.window.uia.root)
        if not msg_list:
            logger.warning("No message list found")
            break

        items = read_all_items(msg_list)

        new_in_round = 0
        for item in items:
            if item["type"] == "message" and item["text"] not in seen_texts:
                seen_texts.add(item["text"])
                all_items.append(item)
                new_in_round += 1

        if new_in_round > 0:
            logger.info(
                f"Scroll {scroll_round + 1}: +{new_in_round} new messages "
                f"(total: {len(seen_texts)})"
            )
            no_new_count = 0
        else:
            no_new_count += 1
            logger.info(f"Scroll {scroll_round + 1}: no new messages")

        # Stop if 5 consecutive scrolls yield nothing
        if no_new_count >= 5:
            logger.info("No more messages to load, stopping")
            break

        # Scroll up to load older messages
        scroll_up(msg_list, count=5)
        time.sleep(0.5)

    wx.disconnect()
    return all_items


def _parse_wechat_time(text: str, today: datetime) -> datetime:
    """Parse WeChat time text into a datetime object."""
    import re

    text = text.strip()
    # Remove time ranges like "14:15-14:16" -> keep start time
    text = re.sub(r'(\d+:\d+)\s*-\s*\d+:\d+', r'\1', text)

    t = today

    # Full date: "2025年3月15日 下午 3:45"
    m = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日\s*(上午|下午|凌晨|傍晚|晚上)?\s*(\d{1,2}):(\d{2})', text)
    if m:
        year, month, day, _, hour, minute = m.groups()
        hour = int(hour) + 12 if _ in ("下午", "晚上") and int(hour) != 12 else int(hour)
        hour = int(hour) - 12 if _ == "凌晨" and int(hour) == 12 else int(hour)
        return t.replace(year=int(year), month=int(month), day=int(day), hour=hour, minute=int(minute), second=0)

    # This year: "3月15日 上午 10:30"
    m = re.match(r'(\d{1,2})月(\d{1,2})日\s*(上午|下午|凌晨|傍晚|晚上)?\s*(\d{1,2}):(\d{2})', text)
    if m:
        month, day, _, hour, minute = m.groups()
        hour = int(hour) + 12 if _ in ("下午", "晚上") and int(hour) != 12 else int(hour)
        hour = int(hour) - 12 if _ == "凌晨" and int(hour) == 12 else int(hour)
        return t.replace(month=int(month), day=int(day), hour=hour, minute=int(minute), second=0)

    # Yesterday: "昨天 上午 10:30"
    m = re.match(r'昨天\s*(上午|下午|凌晨|傍晚|晚上)?\s*(\d{1,2}):(\d{2})', text)
    if m:
        _, hour, minute = m.groups()
        hour = int(hour) + 12 if _ in ("下午", "晚上") and int(hour) != 12 else int(hour)
        hour = int(hour) - 12 if _ == "凌晨" and int(hour) == 12 else int(hour)
        yesterday = t - __import__("datetime").timedelta(days=1)
        return yesterday.replace(hour=hour, minute=int(minute), second=0)

    # Today: "上午 10:30" or "下午 2:30"
    m = re.match(r'(上午|下午|凌晨|傍晚|晚上)?\s*(\d{1,2}):(\d{2})', text)
    if m:
        _, hour, minute = m.groups()
        hour = int(hour) + 12 if _ in ("下午", "晚上") and int(hour) != 12 else int(hour)
        hour = int(hour) - 12 if _ == "凌晨" and int(hour) == 12 else int(hour)
        return t.replace(hour=hour, minute=int(minute), second=0)

    # Fallback
    return t


def _apply_timestamps(all_items: list) -> list:
    """Parse time items and attach timestamps to message items."""
    now = datetime.now()
    current_time = now

    for item in all_items:
        if item["type"] == "time":
            parsed = _parse_wechat_time(item["text"], now)
            # If the parsed time is in the future relative to current_time,
            # it might be from a previous day (e.g. "上午 1:30" scrolling from yesterday)
            if parsed > current_time and (parsed - current_time).total_seconds() > 3600:
                parsed = parsed.replace(day=parsed.day - 1)
            current_time = parsed
        elif item["type"] == "message":
            item["time"] = current_time

    return [it for it in all_items if it["type"] == "message"]


def save_to_weclone_csv(all_items: list, contact_name: str, append_to: str = None):
    """
    Save messages to WeClone format: ./WeClone/dataset/csv/<name>/<name>_*.csv

    If append_to is provided, appends new messages to an existing CSV file.
    Otherwise, creates a new timestamped CSV file.

    Required columns: id, MsgSVRID, type_name, is_sender, talker, msg, src, CreateTime
    """
    output_dir = Path(__file__).resolve().parent.parent / "WeClone" / "dataset" / "csv" / contact_name
    output_dir.mkdir(parents=True, exist_ok=True)

    messages = _apply_timestamps(all_items)
    if not messages:
        logger.warning("No messages to save")
        return ""

    if append_to:
        filepath = Path(append_to)
        # Count existing rows to continue IDs
        existing_count = 0
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                existing_count = sum(1 for _ in f) - 1  # subtract header
        except Exception:
            pass
        start_id = existing_count + 1

        with open(filepath, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for i, item in enumerate(messages):
                sender = 1 if item.get("is_left", True) else 0
                writer.writerow([
                    start_id + i,
                    str(start_id + i),
                    "文本",
                    sender,
                    contact_name if sender else "星夜",
                    item["text"],
                    "",
                    item.get("time", datetime.now()).strftime("%Y-%m-%d %H:%M:%S"),
                ])

        logger.success(f"Appended {len(messages)} new messages to {filepath} (total: {existing_count + len(messages)})")
    else:
        export_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = output_dir / f"{contact_name}_{export_ts}_001.csv"

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "MsgSvrID", "type_name", "is_sender",
                "talker", "msg", "src", "CreateTime"
            ])

            for i, item in enumerate(messages):
                sender = 1 if item.get("is_left", True) else 0
                writer.writerow([
                    i + 1,
                    str(i + 1),
                    "文本",
                    sender,
                    contact_name if sender else "星夜",
                    item["text"],
                    "",
                    item.get("time", datetime.now()).strftime("%Y-%m-%d %H:%M:%S"),
                ])

        logger.success(f"Exported {len(messages)} messages to {filepath}")

    return str(filepath)


if __name__ == "__main__":
    args = sys.argv[1:]
    contact = "周文慧"
    append_mode = False

    if "--append" in args:
        append_mode = True
        args.remove("--append")
    if args:
        contact = args[0]

    logger.info(f"Starting export for contact: {contact}")
    logger.info("Make sure WeChat is logged in and the contact exists.")

    known_texts = set()
    existing_csv = None

    if append_mode:
        # Find the latest existing CSV
        output_dir = Path(__file__).resolve().parent.parent / "WeClone" / "dataset" / "csv" / contact
        csv_files = sorted(output_dir.glob(f"{contact}_*.csv")) if output_dir.exists() else []
        if csv_files:
            existing_csv = str(csv_files[-1])
            with open(existing_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    known_texts.add(row["msg"])
            logger.info(f"Append mode: loaded {len(known_texts)} known texts from {existing_csv}")
        else:
            logger.info("No existing CSV found, will create new file")

    messages = export_chat_history(contact, known_texts=known_texts)

    if messages:
        path = save_to_weclone_csv(messages, contact, append_to=existing_csv)
        logger.info(f"Done! {len(messages)} new messages added to:")
        logger.info(f"  {path}")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. cd WeClone")
        logger.info("  2. weclone-cli make-dataset")
        logger.info("  3. weclone-cli train-sft")
    else:
        logger.warning("No new messages found")
