"""AI 对话引擎 - 负责调用 AI API 生成回复"""

import time
import random
from typing import Optional
from loguru import logger

from config import settings
from bot.personality import Personality


class AIEngine:
    """AI 对话引擎，支持 Claude 和 OpenAI 兼容 API"""

    def __init__(self, personality: Personality):
        self.personality = personality
        self.client = None
        self._init_client()

    def _init_client(self):
        """初始化 AI 客户端"""
        # 优先使用 OpenAI 兼容 API
        if settings.openai_api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url,
                )
                self.provider = "openai"
                logger.info(f"已初始化 OpenAI 客户端 (model: {settings.openai_model})")
                return
            except Exception as e:
                logger.warning(f"OpenAI 客户端初始化失败: {e}")

        # 使用 Claude API
        if settings.anthropic_api_key:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                self.provider = "claude"
                logger.info(f"已初始化 Claude 客户端 (model: {settings.ai_model})")
                return
            except Exception as e:
                logger.warning(f"Claude 客户端初始化失败: {e}")

        logger.error("未配置任何 AI API Key (ANTHROPIC_API_KEY 或 OPENAI_API_KEY)")
        self.client = None

    @property
    def is_ready(self) -> bool:
        return self.client is not None

    def _preprocess_message(self, msg: str) -> str:
        """预处理消息，去除无关内容"""
        # 如果消息包含引用回复，只保留新内容
        if "\n" in msg:
            lines = msg.strip().split("\n")
            msg = lines[-1]
        return msg.strip()

    def _call_claude(self, messages: list[dict]) -> Optional[str]:
        """调用 Claude API"""
        try:
            # 分离 system prompt
            system_content = ""
            api_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_content = msg["content"]
                else:
                    api_messages.append(msg)

            response = self.client.messages.create(
                model=settings.ai_model,
                system=system_content,
                messages=api_messages,
                max_tokens=settings.ai_max_tokens,
                temperature=settings.ai_temperature,
            )
            return response.content[0].text

        except Exception as e:
            logger.error(f"Claude API 调用失败: {e}")
            return None

    def _call_openai(self, messages: list[dict]) -> Optional[str]:
        """调用 OpenAI 兼容 API"""
        try:
            response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_tokens=settings.ai_max_tokens,
                temperature=settings.ai_temperature,
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI API 调用失败: {e}")
            return None

    def generate_reply(self, user_message: str) -> Optional[str]:
        """生成回复"""
        if not self.is_ready:
            logger.warning("AI 引擎未就绪")
            return None

        msg = self._preprocess_message(user_message)
        if not msg:
            return None

        # 添加到对话历史
        self.personality.add_message("user", msg)

        # 获取完整上下文
        messages = self.personality.get_conversation_context()

        # 调用对应 API
        if self.provider == "claude":
            reply = self._call_claude(messages)
        else:
            reply = self._call_openai(messages)

        if reply:
            reply = reply.strip()
            self.personality.add_message("assistant", reply)

        return reply

    def analyze_style(self, chat_records: list[dict]) -> Optional[str]:
        """分析聊天记录中的语言风格"""
        if not self.is_ready:
            logger.warning("AI 引擎未就绪，无法分析风格")
            return None

        # 抽样最近的聊天记录用于分析
        samples = chat_records[-200:] if len(chat_records) > 200 else chat_records

        # 构建分析消息
        messages_text = []
        for msg in samples:
            speaker = msg.get("sender", msg.get("user", "对方"))
            content = msg.get("content", msg.get("message", ""))
            messages_text.append(f"{speaker}: {content}")

        sample_text = "\n".join(messages_text)

        analysis_prompt = f"""请分析以下 {settings.target_name} 的聊天记录，提取她的语言风格特征。

请从以下维度分析：
1. 常用语气词（哈哈、呀、呢、嘛、哦、嗯等）
2. 句式特点（爱用问句、感叹句、省略号等）
3. 用词习惯（爱用哪些词、不喜欢用什么词）
4. 表情符号使用习惯
5. 聊天节奏（回复长度、分段习惯）
6. 语气特点（温柔、活泼、傲娇、高冷等）
7. 常用话题和兴趣点

聊天记录：
```
{sample_text}
```

请给出详细的语言风格分析报告，要求：
- 具体、可操作（不要笼统描述）
- 指出她最独特的表达方式
- 给出模仿她的具体建议
- 用中文回复"""

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            response = client.messages.create(
                model=settings.ai_model,
                system="你是一个专业的语言风格分析专家。请仔细分析聊天记录中的语言特征。",
                messages=[{"role": "user", "content": analysis_prompt}],
                max_tokens=2000,
                temperature=0.3,
            )
            analysis = response.content[0].text
            self.personality.set_style_profile(analysis)
            return analysis

        except Exception as e:
            logger.error(f"风格分析失败: {e}")
            return None

    def get_emotion_response(self, message: str) -> Optional[str]:
        """生成情感回复（带更多亲密感）"""
        return self.generate_reply(message)
