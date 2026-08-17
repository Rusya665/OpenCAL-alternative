"""
Generate authentic retro Doom-style UI sound effects for OpenCAL menu navigation.
Formats strictly as 48kHz 16-bit Stereo PCM for instantaneous HDMI DAC playback.
"""
import numpy as np
import wave
from pathlib import Path

SOUNDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"
SOUNDS_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_RATE = 48000  # Standard HDMI Audio rate (48kHz)


def write_stereo_wav(filename: str, samples: np.ndarray):
    """Write normalized 48kHz stereo 16-bit PCM WAV."""
    samples = np.clip(samples, -1.0, 1.0)
    pcm = (samples * 32767).astype(np.int16)
    stereo_pcm = np.column_stack((pcm, pcm)).flatten()
    out_path = SOUNDS_DIR / filename
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(2)  # Stereo for HDMI
        wf.setsampwidth(2)   # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(stereo_pcm.tobytes())
    print(f"[OK] Generated {out_path} ({len(pcm)} samples, {len(pcm)/SAMPLE_RATE:.3f}s, Stereo 48kHz)")


def generate_scroll_sound():
    """Crisp, punchy Doom-style UI cursor tick (180ms, 48kHz stereo)."""
    duration = 0.18
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    
    # Fast pitch slide from 1600Hz -> 380Hz
    freq = 1500.0 * np.exp(-t * 28.0) + 380.0
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    
    # Square/sine crunch mix
    tone = np.sin(phase) * 0.7 + np.sign(np.sin(phase)) * 0.3
    # Exponential decay
    env = np.exp(-t * 22.0)
    # Attack noise burst for mechanical bite
    noise = (np.random.rand(len(t)) * 2.0 - 1.0) * np.exp(-t * 60.0) * 0.35
    
    sound = (tone * env + noise) * 0.95
    write_stereo_wav("doom_scroll.wav", sound)


def generate_click_sound():
    """Doom-style menu switch / button press (280ms, 48kHz stereo)."""
    duration = 0.28
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    
    # Click 1: Sharp high crack
    freq1 = 2600.0 * np.exp(-t * 35.0) + 600.0
    phase1 = 2 * np.pi * np.cumsum(freq1) / SAMPLE_RATE
    click = np.sin(phase1) * np.exp(-t * 40.0)
    
    # Click 2: Heavy resonant thump (Doom DSPSTART style)
    freq2 = 420.0 * np.exp(-t * 12.0) + 120.0
    phase2 = 2 * np.pi * np.cumsum(freq2) / SAMPLE_RATE
    thump = np.sin(phase2) * np.exp(-t * 14.0) * 0.9
    
    # Texture noise
    noise = (np.random.rand(len(t)) * 2.0 - 1.0) * np.exp(-t * 45.0) * 0.3
    
    sound = (click * 0.65 + thump * 0.75 + noise) * 0.95
    write_stereo_wav("doom_click.wav", sound)


if __name__ == "__main__":
    generate_scroll_sound()
    generate_click_sound()
