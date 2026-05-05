"""LLM API client for generating conversational responses.

Two modes:
1. Remote API (DeepSeek/OpenAI) — uses StyleLearner for persona + chat examples
2. Local model (fine-tuned Qwen2.5) — direct HTTP call to inference server
"""

from typing import Optional
import requests
from loguru import logger
import config
from bot.style_learner import StyleLearner


class LLMClient:
    """Client for LLM API (OpenAI-compatible or local model)."""

    def __init__(self):
        self._client = None
        self._local_url = None
        self._style = None
        self._prompt_template = None
        self._setup_client()

    def _setup_client(self):
        """Initialize the LLM client and style learner."""
        cfg = config.config
        if cfg.use_local_model:
            self._local_url = cfg.local_model_url.rstrip("/")
            logger.info(f"Using local model: {self._local_url}")
        elif cfg.llm_api_key:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=cfg.llm_api_key,
                base_url=cfg.llm_api_base,
            )
            self._model = cfg.llm_model
            # Initialize style learner from exported chat CSVs
            self._style = StyleLearner()
            if self._style.available:
                self._prompt_template = self._style.build_system_prompt(
                    name=cfg.target_name, example_count=15
                )
                logger.info(f"Style learner ready: {self._style.count} examples loaded")
            else:
                self._prompt_template = self._fallback_prompt()
                logger.info("Style learner unavailable, using fallback prompt")
            logger.info(f"LLM client initialized: {self._model}")
        else:
            logger.warning("No LLM configured (no API key and local model disabled)")

    def _fallback_prompt(self) -> str:
        """Fallback prompt when no CSV data is available."""
        return """你是{name}。你需要根据你和对方的聊天历史记录，以{name}的身份回复消息。

## 性格特征
- 恬静温柔，说话轻声细语
- 有时也会活泼撒娇
- 善良体贴，会关心朋友
- 学妹类型，带一点可爱的学生气
- 说话自然真实

## 回复原则
1. 模仿{name}的语气、用词习惯和聊天风格，不要以AI的口吻说话
2. 回复要自然，像是真人之间的对话
3. 根据上下文判断回复内容
4. 回复不要太长
5. 适当使用语气词（啊、啦、呀、呢）

## 当前对话
{context}

## 对方最新消息
{message}

## 请以{name}的身份回复："""

    def _build_prompt(self, message: str, context: str = "") -> str:
        """Build the persona prompt with style examples."""
        name = config.config.target_name
        if self._prompt_template:
            return self._prompt_template.format(
                name=name, context=context or "(暂无历史记录)", message=message
            )
        return self._fallback_prompt().format(
            name=name, context=context or "(暂无历史记录)", message=message
        )

    def chat(self, message: str, context: str = "") -> Optional[str]:
        """Send a message and get a persona-driven reply."""
        cfg = config.config
        if cfg.use_local_model:
            return self._chat_local(message, context)
        if not self._client:
            logger.error("LLM client not initialized")
            return None
        return self._chat_api(message, context)

    def chat_with_history(self, message: str, history: list = None) -> Optional[str]:
        """Send message with full chat history (list of [user, assistant] pairs)."""
        if not self._client:
            logger.error("LLM client not initialized")
            return None

        cfg = config.config
        messages = []
        if self._prompt_template:
            system_content = self._prompt_template.split("{{context}}")[0].strip()
            messages.append({"role": "system", "content": system_content})
        else:
            messages.append({
                "role": "system",
                "content": f"你是{cfg.target_name}，19岁的大一女生，恬静温柔，请用自然的语气和朋友聊天。"
            })

        if history:
            for user_msg, assistant_msg in history[-10:]:
                messages.append({"role": "user", "content": user_msg})
                messages.append({"role": "assistant", "content": assistant_msg})

        messages.append({"role": "user", "content": message})

        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.8,
                max_tokens=500,
            )
            reply = resp.choices[0].message.content.strip()
            logger.info(f"LLM reply: {reply[:80]}...")
            return reply
        except Exception as e:
            logger.error(f"LLM chat_with_history error: {e}")
            return None

    def _chat_local(self, message: str, context: str = "") -> Optional[str]:
        """Call local inference server."""
        try:
            resp = requests.post(
                f"{self._local_url}/chat",
                json={"message": message, "history": []},
                timeout=60,
            )
            resp.raise_for_status()
            reply = resp.json()["reply"]
            logger.info(f"Local model reply: {reply[:80]}...")
            return reply
        except Exception as e:
            logger.error(f"Local model error: {e}")
            return None

    def _chat_api(self, message: str, context: str = "") -> Optional[str]:
        """Call remote OpenAI-compatible API with persona + style examples."""
        try:
            prompt = self._build_prompt(message, context)
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=500,
            )
            reply = resp.choices[0].message.content.strip()
            logger.info(f"LLM reply: {reply[:80]}...")
            return reply
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            return None
