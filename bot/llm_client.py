"""LLM API client for generating conversational responses."""

from typing import Optional
import requests
from loguru import logger
import config


# Persona prompt template — will be enriched after WeClone fine-tuning
PERSONA_PROMPT = """你是{name}。你需要根据你和对方的聊天历史记录，以{name}的身份回复消息。

## 回复原则
1. 模仿{name}的语气、用词习惯和聊天风格，不要以AI的口吻说话
2. 回复要自然，像是真人之间的对话，不要过于正式
3. 根据上下文判断回复内容，不要答非所问
4. 保持对话的连贯性
5. 回复不要太长，像普通人聊天一样自然
6. 适当使用语气词、表情符号（如果有这个习惯）

## 当前对话
{context}

## 对方最新消息
{message}

## 请以{name}的身份回复："""


class LLMClient:
    """Client for LLM API (OpenAI-compatible or local model)."""

    def __init__(self):
        self._client = None
        self._local_url = None
        self._setup_client()

    def _setup_client(self):
        """Initialize the LLM client."""
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
            logger.info(f"LLM client initialized: {self._model}")
        else:
            logger.warning("No LLM configured (no API key and local model disabled)")

    def _build_prompt(self, message: str, context: str = "") -> str:
        """Build the persona prompt."""
        name = config.config.target_name
        return PERSONA_PROMPT.format(
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
        """Call remote OpenAI-compatible API with context."""
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
