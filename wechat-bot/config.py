"""微信机器人配置管理"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Claude API
    anthropic_api_key: Optional[str] = Field(None, alias="ANTHROPIC_API_KEY")

    # OpenAI 兼容 API (可选，优先于 Claude)
    openai_api_key: Optional[str] = Field(None, alias="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(None, alias="OPENAI_BASE_URL")
    openai_model: str = Field("gpt-4o", alias="OPENAI_MODEL")

    # AI 参数
    ai_model: str = Field("claude-sonnet-4-20250506", alias="AI_MODEL")
    ai_temperature: float = Field(0.9, alias="AI_TEMPERATURE")
    ai_max_tokens: int = Field(500, alias="AI_MAX_TOKENS")

    # 目标人设
    target_name: str = Field(..., alias="TARGET_NAME")

    # 语音
    tts_voice: str = Field("zh-CN-XiaoxiaoNeural", alias="TTS_VOICE")
    tts_enabled: bool = Field(True, alias="TTS_ENABLED")
    tts_output_dir: str = Field("./voice_cache", alias="TTS_OUTPUT_DIR")

    # 回复设置
    reply_mode: str = Field("all", alias="REPLY_MODE")
    whitelist_friends: str = Field("", alias="WHITELIST_FRIENDS")
    reply_delay_min: float = Field(1.0, alias="REPLY_DELAY_MIN")
    reply_delay_max: float = Field(5.0, alias="REPLY_DELAY_MAX")

    # 聊天记录
    chat_history_file: str = Field("./chat_history.json", alias="CHAT_HISTORY_FILE")
    max_context_rounds: int = Field(20, alias="MAX_CONTEXT_ROUNDS")

    # 日志
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_file: str = Field("./bot.log", alias="LOG_FILE")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


def get_whitelist() -> list[str]:
    """获取白名单好友列表"""
    if not settings.whitelist_friends:
        return []
    return [name.strip() for name in settings.whitelist_friends.split(",")]


def get_reply_mode() -> str:
    """获取回复模式"""
    mode = settings.reply_mode.lower()
    if mode not in ("keyword", "all", "whitelist"):
        return "all"
    return mode
