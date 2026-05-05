import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # LLM API (DeepSeek / OpenAI-compatible)
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_api_base: str = os.getenv("LLM_API_BASE", "https://api.deepseek.com/v1")
    llm_model: str = os.getenv("LLM_MODEL", "deepseek-chat")

    # Local model (LoRA fine-tuned)
    use_local_model: bool = os.getenv("USE_LOCAL_MODEL", "false").lower() == "true"
    local_model_url: str = os.getenv("LOCAL_MODEL_URL", "http://127.0.0.1:8000")

    # Claude API (alternative)
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    # Target person to mimic
    target_name: str = os.getenv("TARGET_NAME", "朋友")

    # Bot target (empty = all incoming)
    target_wxid: str = os.getenv("TARGET_WXID", "")

    # TTS (Text-to-Speech) — Edge-TTS
    tts_enabled: bool = os.getenv("TTS_ENABLED", "false").lower() == "true"
    tts_voice: str = os.getenv("TTS_VOICE", "xiaoxiao")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


config = Config()
