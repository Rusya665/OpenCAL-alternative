"""
Generate authentic retro Doom-style UI sound effects for OpenCAL menu navigation.
"""
import numpy as np
import wave
from pathlib import Path

SOUNDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"
SOUNDS_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_RATE = 22050  # Classic Doom audio sample rate

def write_wav(filename: str, samples: np.ndarray):
    # Normalize and convert to 16-bit PCM
    samples = np.clip(samples, -1.0, 1.0)
    pcm = (samples * 32767).astype(np.int16)
    out_path = SOUNDS_DIR / filename
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())
    print(f"[OK] Generated {out_path} ({len(pcm)} samples, {len(pcm)/SAMPLE_RATE:.3f}s)")

def generate_scroll_sound():
    # Crisp, punchy Doom-style UI cursor tick (DSPSTOP / D_STNMOV style)
    # ~0.045s duration, fast pitch drop 1400Hz -> 500Hz with exponential decay
    duration = 0.045
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    freq = 1400.0 * np.exp(-t * 35.0) + 400.0
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    
    # Square/saw wave blend with overdrive for 90s crunch
    tone = np.sign(np.sin(phase)) * 0.4 + np.sin(phase) * 0.6
    # Fast attack, exponential decay envelope
    env = np.exp(-t * 80.0)
    # Add subtle noise burst for punch
    noise = (np.random.rand(len(t)) * 2.0 - 1.0) * np.exp(-t * 160.0) * 0.3
    
    sound = (tone * env + noise) * 0.8
    write_wav("doom_scroll.wav", sound)

def generate_click_sound():
    # Doom-style menu activation / switch press (D_PSTART / DSSWTCH style)
    # ~0.12s duration, two-stage thump + metallic click
    duration = 0.12
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    
    # Stage 1: Initial high click (2200Hz -> 800Hz)
    freq1 = 2200.0 * np.exp(-t * 40.0) + 700.0
    phase1 = 2 * np.pi * np.cumsum(freq1) / SAMPLE_RATE
    click = np.sin(phase1) * np.exp(-t * 60.0)
    
    # Stage 2: Low-mid mechanical resonant crunch (350Hz)
    freq2 = 350.0 * np.exp(-t * 15.0)
    phase2 = 2 * np.pi * np.cumsum(freq2) / SAMPLE_RATE
    thump = np.sin(phase2) * np.exp(-t * 25.0) * 0.8
    
    # Stage 3: Crunch noise
    noise = (np.random.rand(len(t)) * 2.0 - 1.0) * np.exp(-t * 80.0) * 0.4
    
    sound = (click * 0.6 + thump * 0.6 + noise) * 0.85
    write_wav("doom_click.wav", sound)

if __name__ == "__main__":
    generate_scroll_sound()
    generate_click_sound()
