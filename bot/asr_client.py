"""
ASR (Automatic Speech Recognition) client.
Records system audio via WASAPI loopback and converts speech to text using Google Web Speech API.
"""

import os
import time
import tempfile
import threading
from typing import Optional, Callable
from loguru import logger

# speech_recognition for transcription
try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False
    logger.warning("speech_recognition not installed. Run: pip install SpeechRecognition")

# pyaudiowpatch for WASAPI loopback recording
try:
    import pyaudiowpatch as pw
    import numpy as np
    import wave
    PW_AVAILABLE = True
except ImportError:
    PW_AVAILABLE = False
    logger.warning("pyaudiowpatch not installed. Run: pip install pyaudiowpatch")

# sounddevice as fallback for Stereo Mix / WDM-KS
try:
    import sounddevice as sd
    SD_AVAILABLE = True
except ImportError:
    SD_AVAILABLE = False


class ASRClient:
    """Records system audio via WASAPI loopback and transcribes speech to text."""

    def __init__(self, language: str = "zh-CN", sample_rate: int = 16000):
        self.language = language
        self.sample_rate = sample_rate
        self._recognizer = sr.Recognizer() if SR_AVAILABLE else None

    @property
    def available(self) -> bool:
        return SR_AVAILABLE

    # ------------------------------------------------------------------
    # Loopback device detection
    # ------------------------------------------------------------------

    def find_loopback_device(self) -> Optional[dict]:
        """Find a device that can capture system audio output (Stereo Mix / loopback).

        Uses sounddevice Stereo Mix (preferred), with fallback to WASAPI loopback
        via pyaudiowpatch if sounddevice is unavailable.

        Returns a dict with keys: index, name, channels, sample_rate, _fallback_sd.
        ``_fallback_sd: True`` means the device is a sounddevice index.
        Returns None if nothing works.
        """
        # 1. Sounddevice Stereo Mix (most reliable on this system)
        dev = self._find_fallback()
        if dev:
            return dev

        # 2. Pyaudiowpatch WASAPI loopback as last resort
        if PW_AVAILABLE:
            try:
                p = pw.PyAudio()
                # Try default loopback
                try:
                    d = p.get_default_wasapi_loopback()
                    logger.info(f"WASAPI loopback (fallback): [{d['index']}] {d['name']}")
                    return {
                        "index": d["index"],
                        "name": d["name"],
                        "channels": int(d["maxInputChannels"]),
                        "sample_rate": int(d["defaultSampleRate"]),
                        "pa": p,
                    }
                except Exception:
                    pass
                # Any loopback
                for d in p.get_loopback_device_info_generator():
                    logger.info(f"WASAPI loopback (any): [{d['index']}] {d['name']}")
                    return {
                        "index": d["index"],
                        "name": d["name"],
                        "channels": int(d["maxInputChannels"]),
                        "sample_rate": int(d["defaultSampleRate"]),
                        "pa": p,
                    }
                p.terminate()
            except Exception as e:
                logger.warning(f"pyaudiowpatch failed: {e}")

        return None

    def _find_fallback(self) -> Optional[dict]:
        """Find Stereo Mix or default system audio capture via sounddevice."""
        if not SD_AVAILABLE:
            return None
        try:
            devices = sd.query_devices()
            # Prefer Stereo Mix / stereo input devices
            for i, d in enumerate(devices):
                name = str(d["name"]).lower()
                if d["max_input_channels"] > 0 and any(
                    kw in name for kw in ["立体声混音", "stereo mix", "stereo", "mix"]
                ):
                    sr = int(d.get("default_samplerate", 48000))
                    channels = int(d["max_input_channels"])
                    logger.info(f"Stereo Mix: [{i}] {d['name']} ({channels}ch, {sr}Hz)")
                    return {
                        "index": i,
                        "name": d["name"],
                        "channels": channels,
                        "sample_rate": sr,
                        "pa": None,
                        "_fallback_sd": True,
                    }
            # Last resort: default input
            default = sd.default.device[0]
            if default is not None:
                d = sd.query_devices(default)
                sr = int(d.get("default_samplerate", self.sample_rate))
                logger.info(f"Default input: [{default}] {d['name']}")
                return {
                    "index": default,
                    "name": d["name"],
                    "channels": int(d["max_input_channels"]),
                    "sample_rate": sr,
                    "pa": None,
                    "_fallback_sd": True,
                }
        except Exception as e:
            logger.warning(f"sounddevice device search failed: {e}")
        return None

    def list_devices(self) -> str:
        """List all audio devices for debugging."""
        lines = ["Available audio devices:"]
        try:
            if PW_AVAILABLE:
                p = pw.PyAudio()
                lines.append("  --- WASAPI Loopback ---")
                for dev in p.get_loopback_device_info_generator():
                    lines.append(
                        f"  [{dev['index']}] {dev['name']} "
                        f"(ch={dev['maxInputChannels']}, sr={dev['defaultSampleRate']:.0f})"
                    )
                p.terminate()
        except Exception:
            pass
        try:
            if SD_AVAILABLE:
                lines.append("  --- All devices (sounddevice) ---")
                for i, dev in enumerate(sd.query_devices()):
                    inp = "IN" if dev["max_input_channels"] > 0 else "  "
                    out = "OUT" if dev["max_output_channels"] > 0 else "   "
                    lines.append(f"  [{i}] {dev['name']:50s} {inp} {out}")
        except Exception:
            pass
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_audio(self, duration: float = 10.0, device: Optional[dict] = None,
                     on_start: Optional[Callable] = None) -> Optional[str]:
        """Record system audio via WASAPI loopback.

        Args:
            duration: Recording length in seconds.
            device: Device dict from ``find_loopback_device()``.
            on_start: Called right after recording starts (e.g. to click play).

        Returns:
            Path to a WAV file, or None on failure.
        """
        if not SR_AVAILABLE:
            logger.error("ASR unavailable: speech_recognition not installed")
            return None

        if device is None:
            device = self.find_loopback_device()

        if device is None:
            logger.error("No loopback recording device found")
            logger.info("Try installing VB-CABLE Virtual Audio Cable for loopback recording")
            return None

        # Use pyaudiowpatch (preferred)
        if device.get("pa") and not device.get("_fallback_sd"):
            try:
                return self._record_pw(duration, device, on_start)
            finally:
                try:
                    device["pa"].terminate()
                except Exception:
                    pass

        # Fallback: sounddevice
        return self._record_sd(duration, device, on_start)

    def _record_pw(self, duration: float, device: dict,
                   on_start: Optional[Callable] = None) -> Optional[str]:
        """Record via pyaudiowpatch WASAPI loopback (blocking read)."""
        pa = device["pa"]
        dev_idx = device["index"]
        channels = device["channels"]
        rate = device["sample_rate"]

        logger.info(f"Recording {duration}s via WASAPI loopback [{dev_idx}] {device['name']} "
                    f"({channels}ch, {rate}Hz)...")
        try:
            stream = pa.open(
                format=pw.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=dev_idx,
                frames_per_buffer=1024,
            )

            stream.start_stream()
            time.sleep(0.2)

            # Trigger on_start (e.g. click play on voice message)
            if on_start:
                on_start()

            frames = []
            chunk_frames = int(rate * 0.1)  # 100ms per read
            total_chunks = int(duration * 10)  # 10 reads per second

            for i in range(total_chunks):
                try:
                    data, flag = stream.read(chunk_frames)
                    if data:
                        frames.append(data)
                except Exception as e:
                    logger.debug(f"Blocking read chunk {i} failed: {e}")

            stream.stop_stream()
            stream.close()

            logger.info(f"Recording done: {len(frames)} chunks captured")

            if not frames:
                logger.error("No audio frames captured via pyaudiowpatch, "
                             "check that the voice message plays through this device")
                return None

            # Mix down to mono and save
            return self._save_wav(b"".join(frames), channels, rate)

        except Exception as e:
            logger.error(f"WASAPI loopback recording failed: {e}")
            return None

    def _record_sd(self, duration: float, device: dict,
                   on_start: Optional[Callable] = None) -> Optional[str]:
        """Fallback recording via sounddevice (Stereo Mix / WDM-KS) blocking read."""
        dev_idx = device["index"]
        rate = device["sample_rate"]
        channels = device.get("channels", 1)

        logger.info(f"Recording {duration}s via sounddevice [{dev_idx}] {device['name']} "
                    f"at {rate}Hz ({channels}ch)...")
        try:
            frames = []
            chunk_frames = int(rate * 0.1)  # 100ms

            def cb(indata, frames_read, time_info, status):
                if status:
                    logger.debug(f"sd status: {status}")
                if indata is not None and len(indata) > 0:
                    frames.append(indata.copy())

            stream = sd.InputStream(
                samplerate=rate,
                device=dev_idx,
                channels=channels,
                dtype="int16",
                callback=cb,
                blocksize=chunk_frames,
            )

            with stream:
                if on_start:
                    on_start()
                time.sleep(duration)

            logger.info(f"Recording done: {len(frames)} chunks captured")

            if not frames:
                logger.error("No audio frames captured via sounddevice")
                return None

            # Concatenate all chunks into one mono array
            full = np.concatenate(frames, axis=0)
            if full.ndim > 1 and full.shape[1] > 1:
                full = full.mean(axis=1).astype(np.int16)
            else:
                full = full.ravel()

            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_path = tmp.name
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(rate)
                wf.writeframes(full.tobytes())

            size = os.path.getsize(tmp_path)
            logger.info(f"Audio saved: {tmp_path} ({size} bytes, {len(full)} samples)")
            return tmp_path
        except Exception as e:
            logger.error(f"sounddevice recording failed: {e}")
            return None

    @staticmethod
    def _save_wav(raw_bytes: bytes, channels: int, rate: int) -> Optional[str]:
        """Convert raw PCM int16 bytes to mono WAV file. Returns path."""
        try:
            arr = np.frombuffer(raw_bytes, dtype=np.int16).reshape(-1, channels)
            # Mix down to mono (average all channels)
            mono = arr.mean(axis=1).astype(np.int16)
        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            return None

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        try:
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(rate)
                wf.writeframes(mono.tobytes())
            size = os.path.getsize(tmp_path)
            logger.info(f"Audio saved: {tmp_path} ({size} bytes, {len(mono)} samples)")
            return tmp_path
        except Exception as e:
            logger.error(f"Save WAV failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Transcription
    # ------------------------------------------------------------------

    def transcribe(self, audio_path: str) -> Optional[str]:
        """Convert audio file to text using Google Web Speech API."""
        if not SR_AVAILABLE:
            logger.error("ASR unavailable: speech_recognition not installed")
            return None

        try:
            with sr.AudioFile(audio_path) as source:
                audio = self._recognizer.record(source)

            logger.info(f"Sending to Google Web Speech API ({self.language})...")
            text = self._recognizer.recognize_google(audio, language=self.language)
            logger.info(f"ASR result: {text}")
            return text
        except sr.UnknownValueError:
            logger.warning("Google Speech Recognition could not understand audio")
            return None
        except sr.RequestError as e:
            logger.error(f"Google Speech Recognition error: {e}")
            return None
        except Exception as e:
            logger.error(f"ASR transcribe failed: {e}")
            return None

    def record_and_transcribe(self, duration: float = 10.0) -> Optional[str]:
        """Record and transcribe in one call."""
        audio_path = self.record_audio(duration=duration)
        if not audio_path:
            return None
        text = self.transcribe(audio_path)
        try:
            os.unlink(audio_path)
        except Exception:
            pass
        return text
