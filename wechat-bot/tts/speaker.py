"""语音合成模块 - 使用 edge-tts 将文本转为语音"""

import os
import uuid
import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger

from config import settings


class VoiceSpeaker:
    """语音合成器"""

    def __init__(self):
        self.voice = settings.tts_voice
        self.output_dir = Path(settings.tts_output_dir)
        self.enabled = settings.tts_enabled
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def text_to_speech(self, text: str, filename: Optional[str] = None) -> Optional[str]:
        """将文本转换为语音文件"""
        if not self.enabled:
            logger.debug("语音功能已禁用")
            return None

        try:
            import edge_tts

            if filename is None:
                filename = f"voice_{uuid.uuid4().hex[:8]}.mp3"

            output_path = self.output_dir / filename

            async def _tts():
                communicate = edge_tts.Communicate(text, self.voice)
                await communicate.save(str(output_path))

            asyncio.run(_tts())

            if output_path.exists():
                logger.info(f"语音已生成: {output_path}")
                return str(output_path)
            else:
                logger.warning("语音文件生成失败")
                return None

        except ImportError:
            logger.warning("未安装 edge-tts，语音功能不可用")
            return None
        except Exception as e:
            logger.error(f"语音合成失败: {e}")
            return None

    def get_available_voices(self) -> list[dict]:
        """获取可用中文语音列表"""
        try:
            import edge_tts

            async def _list():
                voices = await edge_tts.list_voices()
                cn_voices = [
                    {
                        "name": v["ShortName"],
                        "gender": v.get("Gender", ""),
                        "locale": v.get("Locale", ""),
                    }
                    for v in voices
                    if "CN" in v.get("Locale", "")
                ]
                return cn_voices

            return asyncio.run(_list())
        except Exception as e:
            logger.error(f"获取语音列表失败: {e}")
            return []

    def cleanup_old_files(self, max_files: int = 50):
        """清理旧的语音缓存文件"""
        files = sorted(self.output_dir.glob("*.mp3"), key=os.path.getmtime)
        if len(files) > max_files:
            for f in files[:-max_files]:
                f.unlink(missing_ok=True)
                logger.debug(f"已清理旧语音文件: {f}")
