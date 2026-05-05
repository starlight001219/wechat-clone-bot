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
    voice_only: bool = os.getenv("VOICE_ONLY", "false").lower() == "true"  # 仅语音回复，不发送文字

    # ASR (Automatic Speech Recognition) — receive voice messages
    asr_enabled: bool = os.getenv("ASR_ENABLED", "true").lower() == "true"
    asr_language: str = os.getenv("ASR_LANGUAGE", "zh-CN")
    asr_record_seconds: float = float(os.getenv("ASR_RECORD_SECONDS", "10"))

    # Voice Call Mode (real-time phone call)
    voice_call_enabled: bool = os.getenv("VOICE_CALL_ENABLED", "false").lower() == "true"
    voice_call_target: str = os.getenv("VOICE_CALL_TARGET", "星夜")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


config = Config()
