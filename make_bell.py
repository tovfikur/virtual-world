import wave
import numpy as np
from pathlib import Path
# Use the latest bell sound shared by the user for connection alerts
source = 'audiomass-output(1).wav'
path = Path('frontend/src/assets/connectBellSample.js')
path.parent.mkdir(parents=True, exist_ok=True)
with wave.open(source,'rb') as w:
    rate = w.getframerate()
    n = w.getnframes()
    channels = w.getnchannels()
    data = w.readframes(n)
samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
if channels > 1:
    samples = samples.reshape(-1, channels).mean(axis=1)
length = min(int(rate * 0.8), len(samples))
segment = samples[:length]
segment = segment / (np.max(np.abs(segment)) or 1.0)
chunk = 16
with path.open('w', encoding='utf-8') as f:
    f.write(f'export const BELL_SAMPLE_RATE = {rate};\n')
    f.write('export const BELL_SAMPLE = [\n')
    for i in range(0, len(segment), chunk):
        slice_vals = ', '.join(f"{v:.6f}" for v in segment[i:i+chunk])
        f.write(f'  {slice_vals}')
        if i + chunk < len(segment):
            f.write(',')
        f.write('\n')
    f.write('];\n')
print('wrote bell sample', len(segment)/rate)
