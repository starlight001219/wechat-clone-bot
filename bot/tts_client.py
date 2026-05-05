"""Text-to-Speech client using Edge-TTS (free, offline-capable, no API key).

Supports Chinese voices with natural intonation.
Outputs .mp3 files playable via Windows Media Player or sent as voice messages.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional
from loguru import logger

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    logger.warning("edge-tts not installed. Run: pip install edge-tts")


# Chinese voices with different styles:
# zh-CN-XiaoxiaoNeural - female, friendly (default)
# zh-CN-YunyangNeural  - male, professional
# zh-CN-XiaoyiNeural   - female, lively
# zh-CN-YunxiNeural    - male, lively
VOICE_MAP = {
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",
    "yunyang": "zh-CN-YunyangNeural",
    "xiaoyi": "zh-CN-XiaoyiNeural",
    "yunxi": "zh-CN-YunxiNeural",
}


class TTSClient:
    """Generates speech audio from text using Microsoft Edge TTS."""

    def __init__(self, voice: str = "xiaoxiao", output_dir: str = "data/audio"):
        self.voice = VOICE_MAP.get(voice, voice)  # allow custom voice names too
        self._available = EDGE_TTS_AVAILABLE
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def available(self) -> bool:
        return self._available

    async def speak(self, text: str, filename: Optional[str] = None) -> Optional[str]:
        """Generate TTS audio file asynchronously. Returns path to audio file."""
        if not self._available:
            logger.warning("TTS unavailable: edge-tts not installed")
            return None

        if not text.strip():
            return None

        if filename is None:
            import hashlib
            safe = hashlib.md5(text.encode()).hexdigest()[:12]
            filename = f"tts_{safe}.mp3"

        output_path = self.output_dir / filename

        try:
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(str(output_path))
            if output_path.exists():
                logger.info(f"TTS saved: {output_path} ({output_path.stat().st_size} bytes)")
                return str(output_path)
            else:
                logger.error("TTS file not created after generation")
                return None
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            return None

    def speak_sync(self, text: str, filename: Optional[str] = None) -> Optional[str]:
        """Synchronous wrapper for speak()."""
        return asyncio.run(self.speak(text, filename))
