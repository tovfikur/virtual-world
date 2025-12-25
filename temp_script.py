import wave
import numpy as np
from pathlib import Path
path = Path('frontend/src/assets/rockStepSample.js')
path.parent.mkdir(parents=True, exist_ok=True)
with wave.open('audiomass-output.wav','rb') as w:
    rate = w.getframerate()
    n = w.getnframes()
    channels = w.getnchannels()
    data = w.readframes(n)
samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
if channels > 1:
    samples = samples.reshape(-1, channels).mean(axis=1)
max_val = np.max(np.abs(samples)) or 1.0
samples = samples / max_val
with path.open('w', encoding='utf-8') as f:
    f.write('export const ROCK_SAMPLE_RATE = %d;\n' % rate)
    f.write('export const ROCK_SAMPLE = [\n')
    chunk = 16
    for i in range(0, len(samples), chunk):
        vals = ', '.join(f"{v:.6f}" for v in samples[i:i+chunk])
        f.write(f'  {vals}')
        if i + chunk < len(samples):
            f.write(',')
        f.write('\n')
    f.write('];\n')
print('wrote', path)
