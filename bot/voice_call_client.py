"""
Voice Call Client for WeChat AI Bot.
Manages voice call lifecycle: initiate call, listen, reply, hang up.

Audio flow:
  Incoming (星夜's voice):
    WeChat plays through headset → Stereo Mix captures → ASR → LLM → TTS
  Outgoing (bot's reply):
    TTS audio → VB-CABLE Output → VB-CABLE Input → WeChat mic → network → 星夜
"""

import os
import subprocess
import time
import tempfile
import threading
import wave
from typing import Optional, Callable
from loguru import logger
import numpy as np

import win32api
import win32con
import win32gui
import sounddevice as sd

# Lazy imports for heavy modules
_whisper_available = None
_whisper_model = None


# ---------------------------------------------------------------------------
# Constants: known button coordinates (relative to screen, maximized WeChat)
# ---------------------------------------------------------------------------
# Voice call button (phone icon) in the chat header
CALL_BUTTON_X = 1980
CALL_BUTTON_Y = 57

# Hang-up button in the call window (when call is active)
# This will need calibration
HANGUP_BUTTON_X = 1200
HANGUP_BUTTON_Y = 400

# Stereo Mix device — auto-detected by name at runtime
STEREO_MIX_DEVICE = None
STEREO_MIX_SR = 48000
STEREO_MIX_CHANNELS = 2

# VB-CABLE device indices (populated after detection)
CABLE_PLAYBACK_DEVICE = None  # Play TTS INTO this (CABLE Input [23])
CABLE_CAPTURE_DEVICE = None  # WeChat mic FROM this (CABLE Output [27])


def _ensure_whisper():
    """Lazy-load whisper model."""
    global _whisper_available, _whisper_model
    if _whisper_available is not None:
        return _whisper_available
    # Use HuggingFace mirror for users in China
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    try:
        # Try faster-whisper first
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
        _whisper_available = True
        logger.info("Whisper (faster-whisper) model loaded: small")
    except ImportError:
        try:
            import whisper
            _whisper_model = whisper.load_model("small", device="cpu")
            _whisper_available = True
            logger.info("Whisper (openai-whisper) model loaded: small")
        except ImportError:
            _whisper_available = False
            logger.warning("Whisper not installed. Run: pip install faster-whisper")
    return _whisper_available


# ---------------------------------------------------------------------------
# Device detection helpers
# ---------------------------------------------------------------------------

def find_cable_devices():
    """Find VB-CABLE audio devices. Returns True if both IN/OUT exist."""
    global CABLE_PLAYBACK_DEVICE, CABLE_CAPTURE_DEVICE
    try:
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            name = str(d["name"]).lower()
            if "cable input" in name or "vb-audio virtual cable" in name:
                if d["max_output_channels"] > 0 and CABLE_PLAYBACK_DEVICE is None:
                    CABLE_PLAYBACK_DEVICE = i
                    logger.info(f"CABLE Playback (TTS→call): [{i}] {d['name']} OUT={d['max_output_channels']} SR={d.get('default_samplerate','?')}")
            if "cable output" in name:
                if d["max_input_channels"] > 0 and CABLE_CAPTURE_DEVICE is None:
                    CABLE_CAPTURE_DEVICE = i
                    logger.info(f"CABLE Capture (WeChat mic): [{i}] {d['name']} IN={d['max_input_channels']} SR={d.get('default_samplerate','?')}")

        ok = CABLE_PLAYBACK_DEVICE is not None and CABLE_CAPTURE_DEVICE is not None
        if not ok:
            logger.warning(f"VB-CABLE devices incomplete: playback={CABLE_PLAYBACK_DEVICE}, capture={CABLE_CAPTURE_DEVICE}")
        return ok
    except Exception as e:
        logger.warning(f"VB-CABLE detection failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Call control
# ---------------------------------------------------------------------------

def bring_wechat_to_foreground():
    """Bring the main WeChat window to the foreground."""
    hwnd = win32gui.FindWindow(None, "微信")
    if not hwnd:
        logger.warning("Could not find WeChat window by title '微信'")
        return False

    # Force window to foreground using multiple methods
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    win32gui.BringWindowToTop(hwnd)
    win32gui.SetForegroundWindow(hwnd)
    win32gui.SetActiveWindow(hwnd)
    time.sleep(0.5)
    logger.info(f"WeChat window activated: HWND={hwnd}")
    return True


def click_call_button():
    """Click the voice call button to initiate/answer a call."""
    bring_wechat_to_foreground()
    logger.info(f"Clicking voice call button at ({CALL_BUTTON_X}, {CALL_BUTTON_Y})")
    # Click multiple times in case first doesn't register
    for attempt in range(3):
        win32api.SetCursorPos((CALL_BUTTON_X, CALL_BUTTON_Y))
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
        time.sleep(0.3)
    time.sleep(1)
    logger.info("Call button clicked (3 attempts)")


def click_hangup_button():
    """Click the hang-up button to end the call."""
    logger.info(f"Clicking hang-up button at ({HANGUP_BUTTON_X}, {HANGUP_BUTTON_Y})")
    win32api.SetCursorPos((HANGUP_BUTTON_X, HANGUP_BUTTON_Y))
    time.sleep(0.2)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
    time.sleep(0.05)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
    time.sleep(1)
    logger.info("Hang-up button clicked")


def set_cable_as_default_mic():
    """Set CABLE Output as the Windows default communication recording device.

    This makes WeChat use VB-CABLE as its microphone during calls.
    Requires a one-time manual setup or PowerShell execution.
    """
    try:
        # Use PowerShell to set default recording device to CABLE Output
        ps_cmd = r'''
$devices = @(Get-ChildItem -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture" -Recurse -ErrorAction SilentlyContinue)
$cable = $devices | Where-Object { $_ -match "CABLE Output" }
if (-not $cable) {
    Write-Host "CABLE Output not found in registry"
    exit 1
}
Write-Host "CABLE Output found"
'''
        result = subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10
        )
        logger.info(f"Set default mic result: {result.stdout.strip()}")
        return True
    except Exception as e:
        logger.warning(f"Could not set CABLE as default mic automatically: {e}")
        logger.info("Please set 'CABLE Output' as default recording device manually:")
        logger.info("  1. Right-click speaker icon → Sound → Recording tab")
        logger.info("  2. Right-click 'CABLE Output' → 'Set as Default Device'")
        logger.info("  3. Right-click 'CABLE Output' → 'Set as Default Communication Device'")
        return False


def restore_default_mic():
    """Restore the original default recording device (headset mic)."""
    logger.info("To restore: set headset microphone as default recording device in Sound settings")


# ---------------------------------------------------------------------------
# Audio recording (Stereo Mix - captures incoming call audio)
# ---------------------------------------------------------------------------

def find_stereo_mix_device():
    """Find Stereo Mix / loopback recording device by name."""
    global STEREO_MIX_DEVICE
    if STEREO_MIX_DEVICE is not None:
        return STEREO_MIX_DEVICE
    try:
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            name = str(d["name"]).lower()
            if d["max_input_channels"] > 0 and ("立体声混音" in name or "stereo mix" in name or "loopback" in name):
                STEREO_MIX_DEVICE = i
                logger.info(f"Stereo Mix device found: [{i}] {d['name']} IN={d['max_input_channels']} SR={d.get('default_samplerate','?')}")
                return i
        logger.warning("No Stereo Mix device found, using default input")
        STEREO_MIX_DEVICE = sd.default.device[0]  # fallback to default
        return STEREO_MIX_DEVICE
    except Exception as e:
        logger.warning(f"Stereo Mix detection failed: {e}")
        return None


class StereoMixRecorder:
    """Record from Stereo Mix device in chunks, triggered by an on_data callback."""

    def __init__(self, sr=STEREO_MIX_SR, channels=STEREO_MIX_CHANNELS):
        self.device = find_stereo_mix_device()
        self.sr = sr
        self.channels = channels
        self._frames = []
        self._stream = None

    def start(self):
        """Open sounddevice InputStream and begin capturing."""
        self._frames = []

        def callback(indata, frames_read, time_info, status):
            if status:
                logger.debug(f"Stereo Mix status: {status}")
            if indata is not None and len(indata) > 0:
                self._frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.sr,
            device=self.device,
            channels=self.channels,
            dtype="int16",
            callback=callback,
            blocksize=int(self.sr * 0.1),  # 100ms chunks
        )
        self._stream.start()
        logger.debug("Stereo Mix recording started")

    def stop(self):
        """Stop and close the stream."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.debug("Stereo Mix recording stopped")

    def read(self, duration: float = 5.0) -> Optional[np.ndarray]:
        """Record for a fixed duration and return mono int16 array."""
        old_len = len(self._frames)
        time.sleep(duration)
        new_frames = self._frames[old_len:]
        if not new_frames:
            return None
        full = np.concatenate(new_frames, axis=0)
        if full.ndim > 1 and full.shape[1] > 1:
            full = full.mean(axis=1).astype(np.int16)
        return full.ravel()

    def is_silent(self, audio: np.ndarray, threshold: int = 500) -> bool:
        """Check if audio is mostly silence."""
        if audio is None or len(audio) == 0:
            return True
        return np.max(np.abs(audio)) < threshold


# ---------------------------------------------------------------------------
# TTS playback through VB-CABLE
# ---------------------------------------------------------------------------

def play_audio_to_cable(audio_path: str):
    """Play a WAV/MP3 audio file through CABLE Input (into the call).

    Flow: TTS → sd.play() → CABLE Input [playback] → VB-CABLE → CABLE Output [mic] → WeChat → 星夜
    """
    if CABLE_PLAYBACK_DEVICE is None:
        logger.error("VB-CABLE playback device not found")
        return False

    try:
        import soundfile as sf
        data, sr = sf.read(audio_path)
        if data.ndim > 1:
            data = data.mean(axis=1)
        data = (data * 32767).astype(np.int16) if data.dtype.kind == 'f' else data.astype(np.int16)

        sd.play(data, samplerate=sr, device=CABLE_PLAYBACK_DEVICE, blocking=True)
        logger.info(f"Played {len(data)} samples to CABLE Input [{CABLE_PLAYBACK_DEVICE}]")
        return True
    except Exception as e:
        logger.error(f"Play to VB-CABLE failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Full conversation loop
# ---------------------------------------------------------------------------

class VoiceCallSession:
    """
    Manages one voice call session: call → conversation loop → hang-up.
    """

    def __init__(self, llm_client, tts_client, asr_client,
                 on_first_audio: Optional[Callable] = None):
        self.llm = llm_client
        self.tts = tts_client
        self.asr = asr_client
        self.on_first_audio = on_first_audio  # called when we detect the first voice
        self._running = False
        self._recorder = StereoMixRecorder()

    def run(self):
        """Wait for call to be active (audio detected), then run conversation loop."""
        if not find_cable_devices():
            logger.error("VB-CABLE not installed. Cannot route TTS into call.")
            logger.info("Download from: https://vb-audio.com/Cable/")
            return

        # Bring WeChat to foreground
        bring_wechat_to_foreground()

        logger.info("=" * 40)
        logger.info("Starting audio monitoring...")
        logger.info("Please call 星夜 on WeChat now!")
        logger.info("=" * 40)

        # Start recording system audio and wait for call to connect
        self._recorder.start()
        self._running = True

        # Wait for audio activity (call is connected)
        logger.info("Listening for call audio...")
        call_active = self._wait_for_call_audio(timeout=300)
        if not call_active:
            logger.warning("No call audio detected")
            self._recorder.stop()
            return

        logger.info("Call audio detected! Starting conversation...")
        time.sleep(0.5)

        # Speak first greeting through the call
        self._speak_greeting()

        try:
            self._conversation_loop()
        except KeyboardInterrupt:
            logger.info("Conversation loop interrupted")
        finally:
            self._recorder.stop()
            self._running = False
            logger.info("Voice call ended")

    def _wait_for_call_audio(self, timeout=300):
        """Wait until Stereo Mix captures non-silence (call is active)."""
        start = time.time()
        silent_checks = 0
        while time.time() - start < timeout:
            audio = self._recorder.read(duration=1.0)
            if audio is not None and len(audio) > 0:
                peak = np.max(np.abs(audio))
                if peak > 800:  # Above silence threshold = call audio
                    logger.info(f"Call audio detected! Peak level: {peak}")
                    return True
                elif peak > 100:
                    silent_checks = 0
                else:
                    silent_checks += 1
            if silent_checks % 10 == 0 and silent_checks > 0:
                logger.debug(f"Still waiting for call... (peak: {np.max(np.abs(audio)) if audio is not None else 0})")
        return False

    def _wait_for_incoming_call(self, timeout=120):
        """Poll for incoming call window from WeChat. Returns window rect or None."""
        # Record existing windows before the call
        existing = set()
        def enum_save(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                existing.add(hwnd)
            return True
        win32gui.EnumWindows(enum_save, None)
        logger.debug(f"Recorded {len(existing)} existing windows")

        start = time.time()
        while time.time() - start < timeout:
            # Find new windows that appeared
            new_windows = []
            def enum_check(hwnd, _):
                if win32gui.IsWindowVisible(hwnd) and hwnd not in existing:
                    rect = win32gui.GetWindowRect(hwnd)
                    w = rect[2] - rect[0]
                    h = rect[3] - rect[1]
                    title = win32gui.GetWindowText(hwnd)
                    # Call popup is typically 200-500px wide, 100-400px tall
                    if 150 < w < 600 and 80 < h < 500:
                        new_windows.append((hwnd, title, rect))
                return True
            win32gui.EnumWindows(enum_check, None)

            for hwnd, title, rect in new_windows:
                logger.info(f"New window: HWND={hwnd} title='{title}' rect={rect}")
                # Check if it looks like a WeChat call window
                cls = win32gui.GetClassName(hwnd)
                if "chat" in cls.lower() or "call" in cls.lower() or "qt" in cls.lower():
                    logger.info(f"Call window detected: HWND={hwnd} class='{cls}'")
                    return rect

            time.sleep(1)
        return None

    def _speak_greeting(self):
        """Generate a greeting and play through VB-CABLE into the call."""
        greeting = self.llm.chat("你好", context=[])
        if not greeting:
            greeting = "你好，我是周文慧。"
        logger.info(f"Speaking greeting: {greeting[:60]}")
        try:
            tts_path = self.tts.speak_sync(greeting)
            if tts_path:
                play_audio_to_cable(tts_path)
        except Exception as e:
            logger.warning(f"Greeting TTS failed: {e}")

    def _conversation_loop(self):
        """Main loop: detect speech → ASR → LLM → TTS → play."""
        logger.info("Voice conversation loop started")
        turn_count = 0
        whisper_available = _whisper_available is True

        while self._running:
            turn_count += 1
            logger.info(f"--- Conversation turn {turn_count} ---")

            # Record incoming audio
            audio = self._recorder.read(duration=5.0)

            # Check if there's actual speech
            if not audio or self._recorder.is_silent(audio, threshold=500):
                logger.debug("Silence detected, listening again...")
                continue

            if not whisper_available:
                logger.info("Whisper not available - cannot transcribe speech, listening again")
                continue

            # Save to temp file for ASR
            tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_path = tmp_wav.name
            try:
                with wave.open(tmp_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(STEREO_MIX_SR)
                    wf.writeframes(audio.tobytes())
            except Exception as e:
                logger.error(f"Save audio failed: {e}")
                os.unlink(tmp_path)
                continue

            # ASR using Whisper
            try:
                text = self._transcribe_whisper(tmp_path)
            except Exception as e:
                logger.error(f"Whisper transcription failed: {e}")
                text = None
            finally:
                os.unlink(tmp_path)

            if not text:
                logger.info("No speech detected, continuing...")
                continue

            logger.info(f"ASR: {text}")

            # Call on_first_audio callback
            if self.on_first_audio:
                self.on_first_audio()
                self.on_first_audio = None

            # LLM reply
            reply = self.llm.chat(text)
            if not reply:
                continue
            logger.info(f"LLM reply: {reply[:80]}")

            # TTS
            try:
                tts_path = self.tts.speak_sync(reply)
            except Exception as e:
                logger.warning(f"TTS failed: {e}")
                continue

            if not tts_path or not os.path.exists(tts_path):
                continue

            # Play through VB-CABLE (into the call)
            play_audio_to_cable(tts_path)

            # Wait a moment for the call audio to clear
            time.sleep(1)

    def _transcribe_whisper(self, audio_path: str) -> Optional[str]:
        """Transcribe using faster-whisper or openai-whisper (lazy load)."""
        global _whisper_model, _whisper_available
        if _whisper_available is None:
            # First call: try to load Whisper lazily
            _ensure_whisper()
        if _whisper_model is None or _whisper_available is not True:
            logger.debug("Whisper not available, skipping transcription")
            return None

        try:
            model_obj = _whisper_model
            # faster-whisper
            if hasattr(model_obj, "transcribe") and hasattr(model_obj, "model"):
                segments, info = model_obj.transcribe(audio_path, language="zh")
                text = "".join(seg.text for seg in segments)
                return text.strip() or None
            # openai-whisper
            elif hasattr(model_obj, "transcribe"):
                result = model_obj.transcribe(audio_path, language="zh")
                return result.get("text", "").strip() or None
        except Exception as e:
            logger.error(f"Whisper error: {e}")
            return None

    def stop(self):
        """Stop the conversation loop."""
        self._running = False
