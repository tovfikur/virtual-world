import wave
import numpy as np
from pathlib import Path
source = 'walking-on-small-gravel-42533.wav'
path = Path('frontend/src/assets/rockStepSample.js')
path.parent.mkdir(parents=True, exist_ok=True)
with wave.open(source,'rb') as w:
    rate = w.getframerate()
    n = w.getnframes()
    channels = w.getnchannels()
    data = w.readframes(n)
samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
if channels > 1:
    samples = samples.reshape(-1, channels).mean(axis=1)
starts = [0.15, 0.9, 1.7, 2.5, 3.3, 4.1, 4.9, 5.7]
length = int(rate * 0.35)
segments = []
for t in starts:
    start = int(t * rate)
    if start >= len(samples):
        break
    end = min(start + length, len(samples))
    seg = samples[start:end]
    if len(seg) == 0:
        continue
    max_val = float(np.max(np.abs(seg))) or 1.0
    seg = (seg / max_val).tolist()
    segments.append(seg)
if not segments:
    segments = [samples[:length].tolist()]
with path.open('w', encoding='utf-8') as f:
    f.write(f'export const ROCK_SAMPLE_RATE = {rate};\n')
    f.write('export const ROCK_SAMPLES = [\n')
    for idx, seg in enumerate(segments):
        f.write('  [\n')
        chunk = 16
        for i in range(0, len(seg), chunk):
            slice_vals = ', '.join(f"{seg[j]:.6f}" for j in range(i, min(i + chunk, len(seg))))
            f.write(f'    {slice_vals}')
            if i + chunk < len(seg):
                f.write(',')
            f.write('\n')
        f.write('  ]')
        if idx + 1 < len(segments):
            f.write(',')
        f.write('\n')
    f.write('];\n')
print('wrote', len(segments), 'segments')
