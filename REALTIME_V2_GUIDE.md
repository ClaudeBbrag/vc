# Seed-VC V2 Real-Time Conversion Guide

## Overview

`app_realtime_v2.py` provides a web-based interface for voice conversion using V2 models. It supports both batch processing (recommended) and experimental real-time conversion.

---

## Features

[OK] **Batch Conversion** - High-quality offline voice conversion
[OK] **Style Transfer** - Convert accent, emotion, and speaking style
[OK] **Speaker Anonymization** - Convert to neutral "average" voice
[OK] **Advanced Controls** - Full control over all V2 parameters
[OK] **Web Interface** - Easy-to-use Gradio interface
[WARNING] **Real-Time Mode** - Experimental low-latency conversion

---

## Quick Start

### Launch the Interface

```bash
python app_realtime_v2.py
```

Then open your browser to: **http://localhost:7860**

### With Custom Models

```bash
python app_realtime_v2.py \
  --cfm-checkpoint-path ./checkpoints/cfm_model.pth \
  --ar-checkpoint-path ./checkpoints/ar_model.pth \
  --compile
```

### With Public Access

```bash
python app_realtime_v2.py --share
```

This creates a public URL you can share.

---

## Usage Modes

###  Batch Conversion (Recommended)

**Best for:**
- High-quality voice conversion
- Longer audio files
- Style/accent transfer
- Production use

**Steps:**
1. Go to **Batch Conversion** tab
2. Upload **Source Audio** (the voice to convert)
3. Upload **Reference Audio** (target voice style)
4. Adjust settings (optional)
5. Click **Convert Audio**
6. Download the result

**Expected Processing Time:**
- RTX 3060: ~2-5 seconds per second of audio
- RTX 4090: ~1-2 seconds per second of audio
- With compilation: ~50% faster after first run

###  Real-Time Mode (Experimental)

**Best for:**
- Testing and experimentation
- Short audio clips
- Low-latency applications (with powerful GPU)

**Limitations:**
- High latency (1-2+ seconds)
- Requires powerful GPU
- Lower quality than batch mode
- Browser-dependent

**Steps:**
1. Go to **Real-Time** tab
2. Upload **Reference Audio**
3. Click **Prepare Reference**
4. Use microphone or audio input
5. Process audio in chunks

---

## Parameters Guide

### Basic Parameters

| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| **Diffusion Steps** | 10-100 | 30 | Quality vs speed (higher = better quality) |
| **Length Adjust** | 0.5-2.0 | 1.0 | Speech rate (<1.0 = faster, >1.0 = slower) |
| **Intelligibility CFG** | 0.0-1.0 | 0.5 | Pronunciation clarity |
| **Similarity CFG** | 0.0-1.0 | 0.5 | Similarity to reference voice |

### Advanced Parameters (Style Transfer)

| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| **Top-p** | 0.1-1.0 | 0.9 | Sampling diversity (lower = conservative) |
| **Temperature** | 0.1-2.0 | 1.0 | Randomness (lower = deterministic) |
| **Repetition Penalty** | 1.0-3.0 | 1.0 | Reduce repetitive patterns |
| **Convert Style** | Checkbox | Off | Enable AR model for style transfer |
| **Anonymization Only** | Checkbox | Off | Convert to neutral voice |

---

## Performance Guide

### Recommended Settings by Use Case

#### **High Quality (Slow)**
```
Diffusion Steps: 50-100
Convert Style: [OK] Enabled
Reference Audio: 10-20 seconds
Expected Time: 3-10s per second of audio
```

#### **Balanced (Default)**
```
Diffusion Steps: 30
Convert Style: [X] Disabled
Reference Audio: 5-10 seconds
Expected Time: 2-5s per second of audio
```

#### **Fast (Lower Quality)**
```
Diffusion Steps: 10-20
Convert Style: [X] Disabled
Reference Audio: 3-5 seconds
Expected Time: 1-2s per second of audio
```

#### **Real-Time (Experimental)**
```
Diffusion Steps: 5-10
Chunk Duration: 0.5-1.0 seconds
GPU: RTX 3060 or better required
Expected Latency: 1-2+ seconds
```

### Hardware Requirements

| Mode | GPU | Processing Speed | Latency |
|------|-----|------------------|---------|
| Batch (High Quality) | RTX 3060 | 0.3-0.5x realtime | N/A |
| Batch (Fast) | RTX 3060 | 0.5-1.0x realtime | N/A |
| Real-Time | RTX 3060 | ~1.0x realtime | 1-2s |
| Real-Time | RTX 4090 | ~1.5x realtime | 0.5-1s |
| CPU (Not recommended) | Any | 0.01-0.1x realtime | 10-30+s |

---

## Features Comparison

### Batch vs Real-Time

| Feature | Batch Mode | Real-Time Mode |
|---------|------------|----------------|
| **Quality** | ***** | *** |
| **Speed** | Medium | Fast (with good GPU) |
| **Latency** | N/A | 1-2+ seconds |
| **Style Transfer** | [OK] Full support | [WARNING] Limited |
| **Long Audio** | [OK] Yes (chunks) | [X] Short clips only |
| **Browser Support** | [OK] All browsers | [WARNING] Some browsers |
| **GPU Required** | Recommended | **Required** |

### V1 vs V2 Real-Time

| Feature | V1 (`real-time-gui.py`) | V2 (`app_realtime_v2.py`) |
|---------|-------------------------|----------------------------|
| **Interface** | Desktop GUI | Web browser |
| **Latency** | ~430ms | ~1-2 seconds |
| **Style Transfer** | [X] No | [OK] Yes |
| **Quality** | **** | ***** |
| **Setup** | Complex | Easy |
| **Remote Access** | [X] No | [OK] Yes |
| **Optimized Buffering** | [OK] Yes | [WARNING] Basic |

**Recommendation**: For production real-time use, V1 desktop GUI is better optimized. V2 is better for batch processing with style transfer.

---

## Command-Line Options

### Basic Launch

```bash
python app_realtime_v2.py
```

### With Custom Checkpoints

```bash
python app_realtime_v2.py \
  --cfm-checkpoint-path /path/to/cfm.pth \
  --ar-checkpoint-path /path/to/ar.pth
```

### With Compilation (Faster)

```bash
python app_realtime_v2.py --compile
```

This compiles the AR model for ~6x speedup (first run slower).

### With Public Access

```bash
python app_realtime_v2.py --share
```

Creates a temporary public URL.

### All Options

```bash
python app_realtime_v2.py \
  --cfm-checkpoint-path ./checkpoints/cfm.pth \
  --ar-checkpoint-path ./checkpoints/ar.pth \
  --compile \
  --share
```

---

## Examples

### Example 1: Simple Voice Conversion

1. Launch: `python app_realtime_v2.py`
2. Go to **Batch Conversion** tab
3. Upload `my_voice.wav` as source
4. Upload `celebrity_voice.wav` as reference
5. Click **Convert Audio**
6. Download result

**Use Case**: Change voice timbre only (no style transfer)

### Example 2: Accent/Style Transfer

1. Set **Diffusion Steps** to 50
2. Enable **Convert Style** checkbox
3. Set **Top-p** to 0.9
4. Set **Temperature** to 1.0
5. Upload source and reference
6. Click **Convert Audio**

**Use Case**: Transfer accent, emotion, prosody

### Example 3: Speaker Anonymization

1. Enable **Anonymization Only** checkbox
2. Set **Diffusion Steps** to 30
3. Upload source audio (reference not needed)
4. Click **Convert Audio**

**Use Case**: Privacy applications, convert to "average" voice

### Example 4: Fast Conversion

1. Set **Diffusion Steps** to 10
2. Disable **Convert Style**
3. Upload short reference (3-5 seconds)
4. Click **Convert Audio**

**Use Case**: Quick tests, previews

---

## Troubleshooting

### Problem: Out of Memory

**Symptoms:**
- CUDA out of memory error
- App crashes during conversion

**Solutions:**
1. Reduce diffusion steps to 10-20
2. Disable style conversion
3. Use shorter audio clips (< 30 seconds)
4. Restart the application
5. Close other applications using GPU

### Problem: Slow Processing

**Symptoms:**
- Taking minutes per second of audio
- Progress very slow

**Solutions:**
1. Check GPU is being used (should see CUDA device in logs)
2. Reduce diffusion steps
3. Disable style conversion
4. Use `--compile` flag for first-time compilation speedup
5. Upgrade GPU if on CPU

### Problem: Poor Quality Output

**Symptoms:**
- Distorted audio
- Unclear speech
- Artifacts

**Solutions:**
1. Increase diffusion steps to 50+
2. Use cleaner reference audio
3. Enable style conversion
4. Check input audio levels (not too loud/quiet)
5. Use longer reference audio (10-20 seconds)

### Problem: Model Loading Fails

**Symptoms:**
- Error loading checkpoints
- Missing model files

**Solutions:**
1. Check internet connection (downloads from HuggingFace)
2. Wait for models to download (can take 2-5 minutes)
3. Check `./checkpoints/hf_cache` directory
4. Try deleting cache and redownloading
5. Specify custom checkpoint paths

### Problem: High Latency in Real-Time Mode

**Symptoms:**
- 3+ seconds delay
- Choppy audio

**Solutions:**
1. Reduce diffusion steps to 5-10
2. Reduce chunk duration to 0.5 seconds
3. Disable style conversion
4. Use more powerful GPU
5. **Consider using V1 real-time GUI instead**

### Problem: Browser Compatibility Issues

**Symptoms:**
- Microphone not working
- Audio not playing

**Solutions:**
1. Try different browser (Chrome recommended)
2. Check browser permissions for microphone
3. Use batch mode instead
4. Try HTTPS connection
5. Use desktop GUI version

---

## Technical Details

### Architecture

```
User Input (Audio)
    ->
Content Extractor (Whisper + ASTRAL)
    ->
Length Regulator
    ->
[Optional: AR Model for style transfer]
    ->
CFM Model (Diffusion)
    ->
Vocoder (BigVGAN)
    ->
Output Audio
```

### Processing Pipeline

1. **Load Reference Audio**
   - Extract style features (CAMPPlus)
   - Extract content features (ASTRAL)
   - Compute prompt condition

2. **Process Source Audio**
   - Extract content features
   - Length regulation
   - Optional: AR style transfer

3. **Generate Output**
   - CFM diffusion inference
   - BigVGAN vocoder
   - Output audio

### Model Components

- **Content Extractor**: ASTRAL quantization (Whisper + HuBERT)
- **Style Encoder**: CAMPPlus speaker embedding
- **AR Model**: Transformer-based sequence modeling
- **CFM Model**: Conditional flow matching with DiT
- **Vocoder**: BigVGAN v2 (22kHz, 80 bands)

---

## API Usage (Advanced)

You can use the models programmatically:

```python
from hydra.utils import instantiate
from omegaconf import DictConfig
import yaml
import torch

# Load models
cfg = DictConfig(yaml.safe_load(open("configs/v2/vc_wrapper.yaml")))
vc_wrapper = instantiate(cfg)
vc_wrapper.load_checkpoints()
vc_wrapper.to("cuda")
vc_wrapper.eval()

# Convert voice
result = vc_wrapper.convert_voice(
    source_audio_path="source.wav",
    target_audio_path="reference.wav",
    diffusion_steps=30,
    length_adjust=1.0,
    inference_cfg_rate=0.5,
    device=torch.device("cuda"),
    dtype=torch.float16
)

# Save result
import soundfile as sf
sf.write("output.wav", result[0], 22050)
```

---

## Performance Optimization

### For Faster Processing

1. **Use Compilation**
   ```bash
   python app_realtime_v2.py --compile
   ```
   First run slower (compilation), then ~6x faster

2. **Reduce Steps**
   - Use 10-20 diffusion steps instead of 50
   - Disable style conversion

3. **Shorter Reference**
   - Use 3-5 second reference instead of 20

4. **GPU Selection**
   - Ensure using CUDA, not CPU
   - Use newer GPU (Ampere or Ada architecture)

### For Better Quality

1. **More Diffusion Steps**
   - Use 50-100 steps
   - Be patient

2. **Enable Style Transfer**
   - Enables AR model
   - Better accent/prosody transfer

3. **Longer Reference**
   - 10-20 seconds of clean reference audio
   - Multiple sentences

4. **Clean Audio**
   - Remove background noise
   - Normalize audio levels
   - Use high-quality recordings

---

## Comparison with Other Tools

### vs `app_vc_v2.py`

| Feature | `app_realtime_v2.py` | `app_vc_v2.py` |
|---------|----------------------|----------------|
| **Purpose** | Real-time + Batch | Batch only |
| **Real-Time** | [OK] Experimental | [X] No |
| **Streaming** | [OK] Yes | [OK] Yes |
| **Interface** | Modern tabs | Single page |
| **Batch Quality** | ***** | ***** |

**Use app_realtime_v2.py for**: Real-time experiments, modern UI
**Use app_vc_v2.py for**: Stable batch processing, simpler interface

### vs `real-time-gui.py` (V1)

| Feature | `app_realtime_v2.py` | `real-time-gui.py` |
|---------|----------------------|--------------------|
| **Models** | V2 (CFM+AR) | V1 (DiT) |
| **Interface** | Web browser | Desktop GUI |
| **Latency** | 1-2s | ~430ms |
| **Style Transfer** | [OK] Yes | [X] No |
| **Setup** | Easy | Medium |
| **Optimization** | Basic | Advanced (SOLA, VAD) |

**Use app_realtime_v2.py for**: Better quality, style transfer, easy setup
**Use real-time-gui.py for**: Lower latency, production real-time use

---

## FAQ

**Q: Can I use this for live streaming?**
A: Not recommended. The latency (1-2+ seconds) is too high for most live streaming applications. Use `real-time-gui.py` with V1 models for lower latency (~430ms).

**Q: Why is real-time mode slower than batch mode?**
A: Real-time mode is actually using similar processing. The "real-time" refers to the ability to process audio as it comes in, but each chunk still takes time to process. True real-time requires optimizations like those in `real-time-gui.py`.

**Q: Can I run this without a GPU?**
A: Yes, but it will be very slow (10-100x slower). Not recommended for real-time use.

**Q: How do I improve audio quality?**
A: Increase diffusion steps to 50-100, enable style conversion, use longer/cleaner reference audio.

**Q: What's the difference between intelligibility and similarity CFG?**
A: Intelligibility controls pronunciation clarity, similarity controls how closely the output matches the reference voice timbre.

**Q: Can I use my own trained models?**
A: Yes! Use `--cfm-checkpoint-path` and `--ar-checkpoint-path` flags to specify your custom checkpoints.

**Q: Why does the first conversion take longer?**
A: Models are being downloaded and loaded. Subsequent conversions are faster. With `--compile`, first run includes compilation time.

**Q: Is this suitable for production?**
A: Batch mode yes (with good GPU). Real-time mode is experimental - use V1 real-time GUI for production real-time applications.

---

## Resources

- **GitHub**: https://github.com/Plachtaa/seed-vc
- **Paper**: https://arxiv.org/abs/2406.02402
- **Demo**: https://plachtaa.github.io/
- **HuggingFace Models**: https://huggingface.co/Plachta/Seed-VC

---

## Credits

This interface wraps the Seed-VC V2 models with a user-friendly web interface using Gradio.

**Original Seed-VC**: https://github.com/Plachtaa/seed-vc
**Paper**: "Seed-VC: High Quality Versatile Voice Conversion"
