"""Conversation memory manager - stores context with persistence."""

import json
import time
from pathlib import Path
from typing import List, Dict, Optional
from collections import deque
from loguru import logger


class ConversationMemory:
    """Stores recent conversation turns with file persistence."""

    def __init__(self, max_turns: int = 20, storage_dir: str = "data"):
        self.max_turns = max_turns
        self._history: Dict[str, deque] = {}  # wxid -> deque of turns
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def add_turn(self, wxid: str, user_msg: str, bot_reply: str):
        """Record one conversation turn for a contact."""
        if wxid not in self._history:
            self._history[wxid] = deque(maxlen=self.max_turns)
        self._history[wxid].append({
            "timestamp": time.time(),
            "user": user_msg,
            "bot": bot_reply,
        })

    def get_context(self, wxid: str, max_turns: int = 5) -> str:
        """Build context string for the LLM prompt from recent history."""
        if wxid not in self._history or not self._history[wxid]:
            return ""

        lines = []
        for turn in list(self._history[wxid])[-max_turns:]:
            lines.append(f"对方: {turn['user']}")
            lines.append(f"你: {turn['bot']}")
        return "\n".join(lines)

    def save_to_disk(self):
        """Persist memory to JSON file."""
        path = self._storage_dir / "conversation_memory.json"
        data = {
            wxid: list(turns)
            for wxid, turns in self._history.items()
        }
        try:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save memory: {e}")

    def load_from_disk(self):
        """Restore memory from JSON file."""
        path = self._storage_dir / "conversation_memory.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for wxid, turns in data.items():
                self._history[wxid] = deque(turns[-self.max_turns:], maxlen=self.max_turns)
            logger.info(f"Loaded memory for {len(data)} contacts")
        except Exception as e:
            logger.warning(f"Failed to load memory: {e}")

    def clear(self, wxid: Optional[str] = None):
        """Clear memory for one or all contacts."""
        if wxid:
            self._history.pop(wxid, None)
        else:
            self._history.clear()
