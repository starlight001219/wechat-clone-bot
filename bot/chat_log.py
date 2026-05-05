"""Chat log exporter - exports WeChat chat history for WeClone fine-tuning."""

import csv
import os
from datetime import datetime
from pathlib import Path
from loguru import logger


class ChatLogExporter:
    """Export WeChat chat history to CSV format for WeClone."""

    def __init__(self, output_dir: str = "../WeClone/dataset/res_csv/raw"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_session(self, who: str, messages: list) -> str:
        """
        Export a chat session to CSV.

        Args:
            who: Contact name
            messages: List of wxauto message objects

        Returns:
            Path to exported CSV file
        """
        safe_name = "".join(c if c.isalnum() or c in '-_' else '_' for c in who)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.output_dir / f"{safe_name}_{timestamp}.csv"

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["sender", "content", "time"])
            for msg in messages:
                sender = getattr(msg, "sender", "unknown")
                content = getattr(msg, "content", str(msg))
                msg_time = getattr(msg, "time", datetime.now().isoformat())
                writer.writerow([sender, content, msg_time])

        logger.info(f"Exported {len(messages)} messages to {filepath}")
        return str(filepath)


def auto_export_to_weclone(wx_client, contacts: list):
    """
    Quick function: export last N messages from multiple contacts
    directly to WeClone's raw data directory.
    """
    exporter = ChatLogExporter()
    exported = []
    for contact in contacts:
        msgs = wx_client.get_chat_messages(contact, 100)
        if msgs:
            path = exporter.export_session(contact, msgs)
            exported.append(path)
    return exported
