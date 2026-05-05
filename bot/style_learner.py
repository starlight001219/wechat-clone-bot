"""
Style Learner — learns chat style from exported CSV conversation history.

Uses real chat messages as few-shot examples for the LLM prompt,
so DeepSeek / other LLM can mimic the conversation style without fine-tuning.
"""

import csv
import os
import random
from pathlib import Path
from typing import List, Optional
from loguru import logger


# 周文慧的人设描述
PERSONA_DESCRIPTION = """你是周文慧，19岁，大一女生。

## 性格特征
- 恬静温柔，说话轻声细语，很少发脾气
- 有时也会活泼撒娇，会用[呲牙][耶][强]等微信表情
- 善良体贴，会关心朋友，说话让人感觉舒服
- 学妹类型，带一点可爱的学生气
- 偶尔会抱怨学业（线代、英语等），但并不消极
- 说话自然真实，不正式，不说大道理

## 回复原则
1. 模仿周文慧的语气和用词，不要以AI口吻说话
2. 回复自然简短，像普通朋友聊天
3. 根据对方说的内容来回应，不要答非所问
4. 适当使用语气词（啊、啦、呀、呢、哦、嘛）
5. 偶尔可以用颜文字或微信表情，但不要过量
6. 不要说"作为AI"、"作为语言模型"之类的话"""


class StyleLearner:
    """Reads exported CSV chat logs and provides style examples for LLM prompting."""

    def __init__(self, csv_dir: str = None):
        self._examples: List[str] = []
        self._csv_dir = csv_dir or self._default_csv_dir()
        self._load_examples()

    def _default_csv_dir(self) -> str:
        """Default path to WeClone CSV exports."""
        return str(
            Path(__file__).resolve().parent.parent.parent
            / "WeClone" / "dataset" / "csv" / "周文慧"
        )

    def _load_examples(self):
        """Load all messages from CSV files in the directory."""
        csv_dir = Path(self._csv_dir)
        if not csv_dir.exists():
            logger.warning(f"CSV dir not found: {csv_dir}")
            return

        messages = []
        for fpath in sorted(csv_dir.glob("*.csv")):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        msg = row.get("msg", "").strip()
                        if msg and len(msg) >= 2:
                            messages.append(msg)
            except Exception as e:
                logger.warning(f"Failed to read {fpath}: {e}")

        self._examples = messages
        logger.info(f"Loaded {len(self._examples)} style examples from {csv_dir}")

    @property
    def count(self) -> int:
        return len(self._examples)

    @property
    def available(self) -> bool:
        return len(self._examples) > 0

    def get_examples(self, count: int = 15) -> List[str]:
        """Get a random diverse sample of messages as style references."""
        if not self._examples:
            return []

        if len(self._examples) <= count:
            return self._examples.copy()

        # Pick some from beginning, middle, and end for diversity
        n = len(self._examples)
        third = n // 3
        indices = (
            random.sample(range(0, third), min(count // 3, third))
            + random.sample(range(third, 2 * third), min(count // 3, third))
            + random.sample(range(2 * third, n), min(count // 3, n - 2 * third))
        )
        # If we still need more, fill randomly
        if len(indices) < count:
            remaining = [i for i in range(n) if i not in indices]
            indices += random.sample(remaining, min(count - len(indices), len(remaining)))

        random.shuffle(indices)
        return [self._examples[i] for i in indices[:count]]

    def build_system_prompt(self, name: str = "周文慧", example_count: int = 15) -> str:
        """Build the complete system prompt with persona + style examples."""
        prompt = PERSONA_DESCRIPTION

        examples = self.get_examples(example_count)
        if examples:
            prompt += "\n\n## 聊天风格参考\n以下是该聊天中的真实对话摘录，请模仿其中的语气、用词和节奏：\n\n"
            for i, msg in enumerate(examples, 1):
                prompt += f"{i}. {msg}\n"

        prompt += f"""

## 当前对话
{{context}}

## 对方最新消息
{{message}}

## 请以{name}的身份回复："""

        return prompt
