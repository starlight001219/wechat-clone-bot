"""聊天记录导出工具 - 从微信本地数据库提取聊天记录

使用说明:
  微信的聊天记录存储在本地 SQLite 数据库中 (Msg/msg.db)。
  数据库使用 SQLCipher 加密，需要解密后才能读取。

  本工具提供两种方式:
  1. 使用第三方工具 WeChatMsg (https://github.com/LC044/WeChatMsg) 导出为 JSON
  2. 手动转换 CSV/JSON 为工具需要的格式
"""

import json
import csv
from pathlib import Path
from typing import Optional
from loguru import logger


def find_wechat_db() -> Optional[Path]:
    """查找微信本地数据库路径 (仅用于参考)

    WeChat 数据库通常在以下位置:
    %APPDATA%\\Tencent\\WeChat\\[wxid]\\Msg\\msg.db
    """
    import os
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        logger.warning("无法获取 APPDATA 路径")
        return None

    wechat_dir = Path(appdata) / "Tencent" / "WeChat"
    if not wechat_dir.exists():
        logger.warning(f"微信目录不存在: {wechat_dir}")
        return None

    logger.info(f"微信数据目录: {wechat_dir}")
    logger.info("注意: 微信数据库是加密的 (SQLCipher)，需要解密工具")
    return wechat_dir


def convert_wechatmsg_json(input_path: str, output_path: str, target_name: str) -> bool:
    """转换 WeChatMsg 工具导出的 JSON 格式为工具需要的格式

    WeChatMsg 项目: https://github.com/LC044/WeChatMsg

    Args:
        input_path: WeChatMsg 导出的 JSON 文件路径
        output_path: 输出文件路径
        target_name: 目标联系人名称
    """
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        messages = []

        # WeChatMsg 导出格式通常为一个列表
        if isinstance(raw_data, list):
            for item in raw_data:
                sender = item.get("sender", item.get("user", item.get("name", "")))
                content = item.get("content", item.get("msg", item.get("message", "")))
                time_str = item.get("time", item.get("timestamp", ""))

                if content:
                    messages.append({
                        "sender": sender,
                        "content": content,
                        "time": time_str,
                    })

        elif isinstance(raw_data, dict):
            # 可能是嵌套格式
            records = (
                raw_data.get("messages", raw_data.get("records", raw_data.get("data", [])))
            )
            for item in records:
                sender = item.get("sender", item.get("user", item.get("name", "")))
                content = item.get("content", item.get("msg", item.get("message", "")))
                time_str = item.get("time", item.get("timestamp", ""))

                if content:
                    messages.append({
                        "sender": sender,
                        "content": content,
                        "time": time_str,
                    })

        if not messages:
            logger.warning("未找到有效消息记录")
            return False

        # 保存转换结果
        output = {
            "target_name": target_name,
            "total_messages": len(messages),
            "messages": messages,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        # 统计
        senders = {}
        for msg in messages:
            s = msg["sender"]
            senders[s] = senders.get(s, 0) + 1

        logger.info(f"成功转换 {len(messages)} 条消息到 {output_path}")
        logger.info(f"发送者统计: {senders}")
        return True

    except Exception as e:
        logger.error(f"转换失败: {e}")
        return False


def convert_csv(input_path: str, output_path: str, target_name: str) -> bool:
    """从 CSV 文件导入聊天记录

    CSV 格式要求:
    sender,content,time
    xxx,消息内容,2024-01-01 12:00:00
    """
    try:
        messages = []
        with open(input_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sender = row.get("sender", row.get("user", ""))
                content = row.get("content", row.get("message", row.get("msg", "")))
                time_str = row.get("time", row.get("timestamp", ""))

                if sender and content:
                    messages.append({
                        "sender": sender,
                        "content": content,
                        "time": time_str,
                    })

        if not messages:
            logger.warning("CSV 中未找到有效消息")
            return False

        output = {
            "target_name": target_name,
            "total_messages": len(messages),
            "messages": messages,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        logger.info(f"成功导入 {len(messages)} 条消息")
        return True

    except Exception as e:
        logger.error(f"CSV 导入失败: {e}")
        return False


def manual_format_example():
    """打印手动格式示例"""
    example = """{
  "target_name": "她的昵称",
  "total_messages": 100,
  "messages": [
    {
      "sender": "她",
      "content": "今天好开心呀～",
      "time": "2024-01-01 12:00:00"
    },
    {
      "sender": "我",
      "content": "怎么啦这么开心",
      "time": "2024-01-01 12:01:00"
    },
    {
      "sender": "她",
      "content": "你猜猜看嘛>_<",
      "time": "2024-01-01 12:02:00"
    }
  ]
}"""
    print("聊天记录 JSON 格式示例:\n")
    print(example)
    print("\n将聊天记录保存为 chat_history.json 放在项目根目录即可。")


if __name__ == "__main__":
    manual_format_example()
