import wave
import numpy as np
from pathlib import Path
source = 'splash-6213.wav'
path = Path('frontend/src/assets/waterStepSample.js')
path.parent.mkdir(parents=True, exist_ok=True)
with wave.open(source,'rb') as w:
    rate = w.getframerate()
    n = w.getnframes()
    channels = w.getnchannels()
    data = w.readframes(n)
print('rate', rate, 'frames', n, 'channels', channels)
samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
if channels > 1:
    samples = samples.reshape(-1, channels).mean(axis=1)
max_val = np.max(np.abs(samples)) or 1.0
samples = samples / max_val
chunk = 16
with path.open('w', encoding='utf-8') as f:
    f.write(f'export const WATER_SAMPLE_RATE = {rate};\n')
    f.write('export const WATER_SAMPLE = [\n')
    for i in range(0, len(samples), chunk):
        slice_vals = ', '.join(f"{v:.6f}" for v in samples[i:i+chunk])
        f.write(f'  {slice_vals}')
        if i + chunk < len(samples):
            f.write(',')
        f.write('\n')
    f.write('];\n')
