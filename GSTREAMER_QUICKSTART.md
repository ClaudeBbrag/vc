# GStreamer Integration Quick Start Guide
## Real-Time Cloud Voice Conversion with Seed-VC

This guide will help you get started with GStreamer integration for cloud-based real-time voice conversion.

---

## Overview

The GStreamer integration enables Seed-VC to:
- ✅ Stream audio over networks (RTP, WebRTC, UDP)
- ✅ Deploy to cloud servers for scalable voice conversion
- ✅ Support real-time voice conversion with low latency
- ✅ Use efficient codecs (Opus at 64kbps vs MP3 at 320kbps)

**For full technical details, see:**
- [`GSTREAMER_EXECUTIVE_SUMMARY.md`](GSTREAMER_EXECUTIVE_SUMMARY.md) - Business case and overview
- [`GSTREAMER_INTEGRATION_ANALYSIS.md`](GSTREAMER_INTEGRATION_ANALYSIS.md) - Technical deep dive
- [`GSTREAMER_IMPLEMENTATION_GUIDE.md`](GSTREAMER_IMPLEMENTATION_GUIDE.md) - Detailed implementation steps

---

## Installation

### 1. Install GStreamer (System Packages)

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-nice \
    python3-gi \
    gir1.2-gstreamer-1.0
```

**macOS (with Homebrew):**
```bash
brew install gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly pygobject3
```

**Verify installation:**
```bash
gst-launch-1.0 --version
# Should show GStreamer 1.20 or newer
```

### 2. Install Python Dependencies

```bash
pip install -r requirements-gstreamer.txt
```

This installs:
- `PyGObject` - Python bindings for GStreamer
- `aiohttp` - For WebRTC signaling (optional)
- Other utilities

---

## Quick Start

### Test 1: GStreamer Bridge (Passthrough)

Test that GStreamer is working correctly with a simple passthrough:

```bash
python test_gstreamer.py --mode bridge
```

You should hear a 440Hz tone for 5 seconds. If you hear it, GStreamer is working!

### Test 2: File-to-File Voice Conversion

Convert a voice from one file to another using GStreamer:

```bash
python test_gstreamer.py --mode file \
    --source examples/source.wav \
    --reference examples/reference.wav \
    --output output_converted.wav \
    --diffusion-steps 10
```

### Test 3: Real-Time Voice Conversion (Local)

Test real-time voice conversion with a test tone:

```bash
python test_gstreamer.py --mode realtime \
    --reference examples/reference.wav \
    --diffusion-steps 10
```

You should hear a 440Hz tone converted to the reference voice.

### Test 4: Network Streaming (RTP)

This test requires two terminals.

**Terminal 1 (Send audio via RTP):**
```bash
gst-launch-1.0 filesrc location=examples/source.wav ! \
    decodebin ! audioconvert ! audioresample ! \
    audio/x-raw,rate=48000 ! opusenc ! rtpopuspay ! \
    udpsink host=127.0.0.1 port=5004
```

**Terminal 2 (Run Seed-VC with GStreamer):**
```bash
python test_gstreamer.py --mode network \
    --reference examples/reference.wav \
    --input-port 5004 \
    --output-port 5005
```

**Terminal 3 (Receive converted audio):**
```bash
gst-launch-1.0 udpsrc port=5005 caps='application/x-rtp' ! \
    rtpjitterbuffer ! rtpopusdepay ! opusdec ! \
    audioconvert ! autoaudiosink
```

---

## Usage in Your Code

### Basic Example

```python
from seed_vc_wrapper import SeedVCWrapper

# Initialize wrapper
vc = SeedVCWrapper()

# Run voice conversion with GStreamer
vc.convert_voice_gstreamer(
    reference_wav_path='examples/reference.wav',
    diffusion_steps=10,
    input_type='file',
    output_type='file',
    input_file='examples/source.wav',
    output_file='output.wav'
)
```

### Network Streaming Example

```python
from seed_vc_wrapper import SeedVCWrapper

# Initialize wrapper
vc = SeedVCWrapper()

# Real-time streaming conversion
# Receives RTP on port 5004, sends on port 5005
vc.convert_voice_gstreamer(
    reference_wav_path='examples/reference.wav',
    diffusion_steps=10,
    input_type='rtp',
    output_type='rtp',
    port=5004,              # Input port
    host='127.0.0.1',       # Output host
    output_port=5005,       # Output port
    chunk_duration_ms=180.0 # 180ms chunks
)
```

### Microphone to Speaker (Real-Time)

```python
from seed_vc_wrapper import SeedVCWrapper

# Initialize wrapper
vc = SeedVCWrapper()

# Capture from microphone, play through speakers
vc.convert_voice_gstreamer(
    reference_wav_path='examples/reference.wav',
    diffusion_steps=10,
    input_type='autoaudiosrc',    # Default microphone
    output_type='autoaudiosink',  # Default speakers
    chunk_duration_ms=180.0
)
```

---

## Configuration Options

### `convert_voice_gstreamer()` Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `reference_wav_path` | str | *required* | Path to reference voice |
| `diffusion_steps` | int | 10 | Number of diffusion steps (4-10 for real-time) |
| `inference_cfg_rate` | float | 0.7 | Classifier-free guidance rate |
| `input_type` | str | 'file' | Input source: 'file', 'rtp', 'udp', 'test', 'autoaudiosrc' |
| `output_type` | str | 'file' | Output sink: 'file', 'rtp', 'udp', 'autoaudiosink' |
| `f0_condition` | bool | False | Use F0 conditioning (for singing) |
| `auto_f0_adjust` | bool | True | Automatically adjust F0 |
| `pitch_shift` | int | 0 | Pitch shift in semitones |
| `chunk_duration_ms` | float | 180.0 | Chunk duration in milliseconds |
| `**io_kwargs` | dict | {} | Additional GStreamer options |

### Common `io_kwargs` Options

**For 'file' input:**
- `input_file`: Path to input file

**For 'file' output:**
- `output_file`: Path to output file

**For 'rtp' input:**
- `port`: Port to receive RTP stream (default: 5004)
- `latency`: Jitter buffer latency in ms (default: 50)

**For 'rtp' output:**
- `host`: Destination host (default: '127.0.0.1')
- `output_port` or `port`: Destination port (default: 5005)
- `bitrate`: Opus bitrate in bps (default: 64000)
- `output_sr`: Output sample rate (default: 48000)

**For 'test' input:**
- `frequency`: Test tone frequency in Hz (default: 440)

---

## Performance Tips

### For Real-Time Conversion

1. **Reduce diffusion steps**: Use 4-10 steps instead of 25-50
   ```python
   diffusion_steps=10  # Real-time (~150ms inference)
   # vs
   diffusion_steps=25  # High quality (~350ms inference)
   ```

2. **Use GPU**: Ensure CUDA is available
   ```python
   import torch
   print(f"CUDA available: {torch.cuda.is_available()}")
   ```

3. **Adjust chunk size**: Smaller chunks = lower latency but more overhead
   ```python
   chunk_duration_ms=180.0  # Default, good balance
   # vs
   chunk_duration_ms=100.0  # Lower latency, more CPU
   ```

4. **Optimize network settings**: For RTP streaming
   ```python
   vc.convert_voice_gstreamer(
       ...,
       input_type='rtp',
       port=5004,
       latency=30,  # Lower jitter buffer for lower latency
       bitrate=64000  # Opus bitrate (higher = better quality)
   )
   ```

### Expected Latency

| Configuration | Algorithm | I/O | Network | Total |
|---------------|-----------|-----|---------|-------|
| Local (sounddevice) | 300ms | 130ms | - | **430ms** |
| GStreamer (local) | 300ms | 50ms | - | **350ms** |
| GStreamer (same region) | 300ms | 50ms | 60ms | **410ms** |
| GStreamer (cross-continent) | 300ms | 50ms | 300ms | **650ms** |

**Target**: <600ms for acceptable real-time experience

---

## Troubleshooting

### "No module named 'gi'"

**Solution:**
```bash
pip install PyGObject

# If that fails, install system dependencies:
sudo apt-get install libgirepository1.0-dev gcc libcairo2-dev pkg-config python3-dev gir1.2-gtk-3.0
pip install PyGObject
```

### "Could not find element 'opusenc'"

**Solution:**
```bash
sudo apt-get install gstreamer1.0-plugins-bad
gst-inspect-1.0 opusenc  # Verify it's installed
```

### High latency or audio dropouts

**Solutions:**
1. Reduce jitter buffer: `latency=20` (in ms)
2. Increase GStreamer buffer: `max-buffers=20` (edit bridge code)
3. Use faster GPU
4. Reduce diffusion steps: `diffusion_steps=4`

### "Pipeline errors: Could not link elements"

**Solution:**
Add `audioconvert ! audioresample !` between incompatible elements. This is already done in the bridge code, but if you modify pipelines manually, ensure format compatibility.

### Audio quality issues

**Solutions:**
1. Increase Opus bitrate: `bitrate=128000` (default is 64000)
2. Increase diffusion steps: `diffusion_steps=15` (default is 10)
3. Use 44.1kHz model with F0: `f0_condition=True`

---

## Next Steps

### Cloud Deployment

For production cloud deployment:

1. **Read the deployment guide**: [`GSTREAMER_INTEGRATION_ANALYSIS.md`](GSTREAMER_INTEGRATION_ANALYSIS.md#phase-3-production-deployment-week-5-6)

2. **Build Docker container**: Use `Dockerfile.gstreamer` template in the analysis docs

3. **Deploy to Kubernetes**: Use the provided k8s manifests

4. **Set up WebRTC signaling**: For browser-based clients

5. **Configure TURN server**: For NAT traversal (see `coturn` setup)

### WebRTC Integration

For browser-to-cloud voice conversion:

1. **Implement WebRTC signaling server**: See `GSTREAMER_INTEGRATION_ANALYSIS.md` Phase 2

2. **Create browser client**: HTML/JavaScript code provided in docs

3. **Test end-to-end**: Browser → Cloud → Browser

---

## Examples

### Example 1: Local File Conversion

```bash
# Quick test
python test_gstreamer.py --mode file \
    --source examples/source.wav \
    --reference examples/reference.wav
```

### Example 2: Live Microphone Conversion

```python
from seed_vc_wrapper import SeedVCWrapper

vc = SeedVCWrapper()
vc.convert_voice_gstreamer(
    reference_wav_path='my_voice.wav',
    input_type='autoaudiosrc',
    output_type='autoaudiosink',
    diffusion_steps=8  # Fast for real-time
)
```

### Example 3: Network Streaming Server

```python
from seed_vc_wrapper import SeedVCWrapper

vc = SeedVCWrapper()

# Run as a streaming server
# Clients send RTP to port 5004, receive from port 5005
vc.convert_voice_gstreamer(
    reference_wav_path='target_voice.wav',
    input_type='rtp',
    output_type='rtp',
    port=5004,
    output_port=5005,
    diffusion_steps=10,
    bitrate=64000
)
```

### Example 4: Singing Voice Conversion (44.1kHz)

```python
from seed_vc_wrapper import SeedVCWrapper

vc = SeedVCWrapper()

vc.convert_voice_gstreamer(
    reference_wav_path='singer_reference.wav',
    input_type='file',
    output_type='file',
    input_file='singing_source.wav',
    output_file='converted_singing.wav',
    f0_condition=True,      # Enable F0 for singing
    diffusion_steps=15,     # More steps for quality
    auto_f0_adjust=True,
    pitch_shift=0           # Or adjust pitch
)
```

---

## Resources

- **Executive Summary**: [GSTREAMER_EXECUTIVE_SUMMARY.md](GSTREAMER_EXECUTIVE_SUMMARY.md)
- **Technical Analysis**: [GSTREAMER_INTEGRATION_ANALYSIS.md](GSTREAMER_INTEGRATION_ANALYSIS.md)
- **Implementation Guide**: [GSTREAMER_IMPLEMENTATION_GUIDE.md](GSTREAMER_IMPLEMENTATION_GUIDE.md)
- **Architecture Comparison**: [ARCHITECTURE_COMPARISON.md](ARCHITECTURE_COMPARISON.md)

- **GStreamer Documentation**: https://gstreamer.freedesktop.org/documentation/
- **WebRTC Samples**: https://webrtc.github.io/samples/
- **Opus Codec**: https://opus-codec.org/

---

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the detailed documentation files
3. Test with the provided test scripts
4. Check GStreamer installation: `gst-inspect-1.0`

---

**Happy streaming!** 🎙️🔊
