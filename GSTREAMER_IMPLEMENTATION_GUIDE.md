# GStreamer Implementation Guide
## Step-by-Step Integration for Seed-VC

This guide provides practical, actionable steps to integrate GStreamer into Seed-VC for cloud-based real-time voice conversion.

---

## Prerequisites

### System Requirements

- **OS:** Linux (Ubuntu 22.04+ recommended) or macOS
- **GPU:** NVIDIA GPU with 6GB+ VRAM (for real-time processing)
- **RAM:** 8GB minimum, 16GB recommended
- **Network:** Low-latency connection (<100ms RTT for optimal results)

### Software Dependencies

```bash
# Ubuntu/Debian
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
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-bad-1.0 \
    libgstreamer1.0-dev \
    libgirepository1.0-dev \
    pkg-config

# Python bindings
pip install PyGObject

# Optional: TURN server for NAT traversal
sudo apt-get install -y coturn
```

### Verify Installation

```bash
# Check GStreamer version (should be 1.20+)
gst-launch-1.0 --version

# Test basic pipeline
gst-launch-1.0 audiotestsrc ! autoaudiosink

# Test Opus codec
gst-launch-1.0 audiotestsrc ! opusenc ! opusdec ! autoaudiosink

# List all available plugins
gst-inspect-1.0
```

---

## Step 1: Basic GStreamer Bridge (Local Testing)

### Create the Audio Bridge Module

Create `modules/gstreamer_bridge.py`:

```python
"""
GStreamer Audio Bridge for Seed-VC
Handles audio I/O between GStreamer pipelines and Python/NumPy
"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import numpy as np
import threading
import queue
from typing import Optional, Callable

# Initialize GStreamer
Gst.init(None)


class AudioBuffer:
    """Thread-safe circular audio buffer"""

    def __init__(self, max_size_samples: int = 48000):
        self.buffer = np.zeros(max_size_samples, dtype=np.float32)
        self.write_pos = 0
        self.read_pos = 0
        self.lock = threading.Lock()

    def write(self, data: np.ndarray):
        """Write audio data to buffer"""
        with self.lock:
            data_len = len(data)
            space_available = len(self.buffer) - self.write_pos

            if data_len <= space_available:
                self.buffer[self.write_pos:self.write_pos + data_len] = data
                self.write_pos += data_len
            else:
                # Wrap around
                self.buffer[self.write_pos:] = data[:space_available]
                self.buffer[:data_len - space_available] = data[space_available:]
                self.write_pos = data_len - space_available

    def read(self, num_samples: int) -> Optional[np.ndarray]:
        """Read audio data from buffer"""
        with self.lock:
            available = self.write_pos - self.read_pos
            if available < num_samples:
                return None  # Not enough data

            data = self.buffer[self.read_pos:self.read_pos + num_samples].copy()
            self.read_pos += num_samples
            return data

    def available_samples(self) -> int:
        """Get number of available samples"""
        with self.lock:
            return self.write_pos - self.read_pos


class GStreamerAudioBridge:
    """
    Bridges GStreamer pipelines with Seed-VC processing.

    Example usage:
        bridge = GStreamerAudioBridge(sample_rate=22050)
        bridge.create_input_pipeline('file', input_file='test.wav')
        bridge.create_output_pipeline('file', output_file='output.wav')
        bridge.start()

        while True:
            chunk = bridge.read_input(4096)  # Read 4096 samples
            if chunk is not None:
                processed = your_processing_function(chunk)
                bridge.write_output(processed)
    """

    def __init__(self, sample_rate: int = 22050, channels: int = 1):
        """
        Initialize GStreamer audio bridge.

        Args:
            sample_rate: Target sample rate for processing (Hz)
            channels: Number of audio channels (1=mono, 2=stereo)
        """
        self.sample_rate = sample_rate
        self.channels = channels

        self.input_pipeline = None
        self.output_pipeline = None
        self.input_buffer = AudioBuffer()
        self.output_buffer = AudioBuffer()

        self.mainloop = None
        self.mainloop_thread = None

    def create_input_pipeline(self, source_type: str = 'file', **kwargs):
        """
        Create input pipeline based on source type.

        Args:
            source_type: 'file', 'rtp', 'udp', 'test'
            **kwargs: Additional parameters (e.g., input_file, port)
        """
        if source_type == 'file':
            input_file = kwargs.get('input_file', 'input.wav')
            pipeline_str = f"""
                filesrc location={input_file} !
                decodebin !
                audioconvert !
                audioresample !
                audio/x-raw,rate={self.sample_rate},channels={self.channels},format=F32LE !
                appsink name=sink emit-signals=true max-buffers=10 drop=false
            """

        elif source_type == 'rtp':
            port = kwargs.get('port', 5004)
            pipeline_str = f"""
                udpsrc port={port} caps="application/x-rtp,media=audio,encoding-name=OPUS,payload=96" !
                rtpjitterbuffer latency=50 !
                rtpopusdepay !
                opusdec !
                audioconvert !
                audioresample !
                audio/x-raw,rate={self.sample_rate},channels={self.channels},format=F32LE !
                appsink name=sink emit-signals=true max-buffers=10 drop=false
            """

        elif source_type == 'udp':
            port = kwargs.get('port', 5004)
            pipeline_str = f"""
                udpsrc port={port} !
                rawaudioparse use-sink-caps=false format=pcm pcm-format=f32le sample-rate={self.sample_rate} num-channels={self.channels} !
                audioconvert !
                appsink name=sink emit-signals=true max-buffers=10 drop=false
            """

        elif source_type == 'test':
            # Sine wave for testing
            freq = kwargs.get('frequency', 440)
            pipeline_str = f"""
                audiotestsrc wave=sine freq={freq} !
                audioconvert !
                audioresample !
                audio/x-raw,rate={self.sample_rate},channels={self.channels},format=F32LE !
                appsink name=sink emit-signals=true max-buffers=10 drop=false
            """

        else:
            raise ValueError(f"Unsupported source type: {source_type}")

        # Create pipeline
        self.input_pipeline = Gst.parse_launch(pipeline_str)

        # Get appsink and connect callback
        appsink = self.input_pipeline.get_by_name('sink')
        appsink.connect('new-sample', self._on_input_sample)

        # Set up bus to watch for errors
        bus = self.input_pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::error', self._on_error)
        bus.connect('message::eos', self._on_eos)

    def create_output_pipeline(self, sink_type: str = 'file', **kwargs):
        """
        Create output pipeline based on sink type.

        Args:
            sink_type: 'file', 'rtp', 'udp', 'autoaudiosink'
            **kwargs: Additional parameters
        """
        if sink_type == 'file':
            output_file = kwargs.get('output_file', 'output.wav')
            pipeline_str = f"""
                appsrc name=src format=time is-live=true block=true max-bytes=0 !
                audio/x-raw,rate={self.sample_rate},channels={self.channels},format=F32LE !
                audioconvert !
                wavenc !
                filesink location={output_file}
            """

        elif sink_type == 'rtp':
            host = kwargs.get('host', '127.0.0.1')
            port = kwargs.get('port', 5005)
            bitrate = kwargs.get('bitrate', 64000)
            pipeline_str = f"""
                appsrc name=src format=time is-live=true block=true !
                audio/x-raw,rate={self.sample_rate},channels={self.channels},format=F32LE !
                audioresample !
                audio/x-raw,rate=48000 !
                audioconvert !
                opusenc bitrate={bitrate} frame-size=20 !
                rtpopuspay !
                udpsink host={host} port={port}
            """

        elif sink_type == 'udp':
            host = kwargs.get('host', '127.0.0.1')
            port = kwargs.get('port', 5005)
            pipeline_str = f"""
                appsrc name=src format=time is-live=true block=true !
                audio/x-raw,rate={self.sample_rate},channels={self.channels},format=F32LE !
                udpsink host={host} port={port}
            """

        elif sink_type == 'autoaudiosink':
            # Play to default audio device
            pipeline_str = f"""
                appsrc name=src format=time is-live=true block=true !
                audio/x-raw,rate={self.sample_rate},channels={self.channels},format=F32LE !
                audioconvert !
                autoaudiosink
            """

        else:
            raise ValueError(f"Unsupported sink type: {sink_type}")

        # Create pipeline
        self.output_pipeline = Gst.parse_launch(pipeline_str)
        self.appsrc = self.output_pipeline.get_by_name('src')

        # Set up bus
        bus = self.output_pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::error', self._on_error)

    def _on_input_sample(self, appsink):
        """Callback when new audio sample arrives"""
        sample = appsink.emit('pull-sample')
        if sample is None:
            return Gst.FlowReturn.ERROR

        buffer = sample.get_buffer()
        success, map_info = buffer.map(Gst.MapFlags.READ)

        if success:
            # Convert to numpy array
            audio_data = np.frombuffer(map_info.data, dtype=np.float32)
            buffer.unmap(map_info)

            # Write to input buffer
            self.input_buffer.write(audio_data)

        return Gst.FlowReturn.OK

    def _on_error(self, bus, message):
        """Handle pipeline errors"""
        err, debug = message.parse_error()
        print(f"GStreamer Error: {err}")
        print(f"Debug info: {debug}")

    def _on_eos(self, bus, message):
        """Handle end-of-stream"""
        print("End of stream reached")
        if self.mainloop:
            self.mainloop.quit()

    def read_input(self, num_samples: int) -> Optional[np.ndarray]:
        """
        Read audio samples from input buffer.

        Args:
            num_samples: Number of samples to read

        Returns:
            Numpy array of shape (num_samples,) or None if not enough data
        """
        return self.input_buffer.read(num_samples)

    def write_output(self, audio_data: np.ndarray):
        """
        Write audio samples to output pipeline.

        Args:
            audio_data: Numpy array of audio samples (float32)
        """
        if self.appsrc is None:
            raise RuntimeError("Output pipeline not created")

        # Ensure correct dtype
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        # Convert to bytes
        audio_bytes = audio_data.tobytes()

        # Create GStreamer buffer
        buffer = Gst.Buffer.new_wrapped(audio_bytes)

        # Push to pipeline
        ret = self.appsrc.emit('push-buffer', buffer)

        if ret != Gst.FlowReturn.OK:
            print(f"Error pushing buffer: {ret}")

    def start(self):
        """Start both pipelines"""
        if self.input_pipeline:
            self.input_pipeline.set_state(Gst.State.PLAYING)
            print("Input pipeline started")

        if self.output_pipeline:
            self.output_pipeline.set_state(Gst.State.PLAYING)
            print("Output pipeline started")

        # Start GLib main loop in separate thread
        self.mainloop = GLib.MainLoop()
        self.mainloop_thread = threading.Thread(target=self.mainloop.run, daemon=True)
        self.mainloop_thread.start()

    def stop(self):
        """Stop both pipelines"""
        if self.input_pipeline:
            self.input_pipeline.set_state(Gst.State.NULL)
            print("Input pipeline stopped")

        if self.output_pipeline:
            # Send EOS before stopping
            self.appsrc.emit('end-of-stream')
            self.output_pipeline.set_state(Gst.State.NULL)
            print("Output pipeline stopped")

        if self.mainloop:
            self.mainloop.quit()
            self.mainloop_thread.join(timeout=2.0)

    def get_input_available(self) -> int:
        """Get number of samples available in input buffer"""
        return self.input_buffer.available_samples()


# Example usage
if __name__ == '__main__':
    import time

    print("Testing GStreamer Audio Bridge...")

    # Create bridge
    bridge = GStreamerAudioBridge(sample_rate=22050)

    # Test with sine wave input and audio output
    bridge.create_input_pipeline('test', frequency=440)
    bridge.create_output_pipeline('autoaudiosink')

    bridge.start()

    print("Playing 440Hz sine wave for 5 seconds...")
    print("(This is a passthrough test - you should hear a tone)")

    # Process in chunks
    chunk_size = 4096
    duration = 5.0  # seconds
    samples_to_process = int(22050 * duration)
    processed_samples = 0

    try:
        while processed_samples < samples_to_process:
            # Read from input
            chunk = bridge.read_input(chunk_size)

            if chunk is not None:
                # Here you would process with Seed-VC
                # For now, just pass through
                processed_chunk = chunk

                # Write to output
                bridge.write_output(processed_chunk)

                processed_samples += len(chunk)
            else:
                # Not enough data yet
                time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nStopped by user")

    finally:
        bridge.stop()
        print("Test complete!")
```

### Test the Bridge

```bash
# Run the test
python modules/gstreamer_bridge.py

# You should hear a 440Hz tone for 5 seconds
# If you hear it, the bridge is working correctly!
```

---

## Step 2: Integrate with Seed-VC

### Modify `seed_vc_wrapper.py`

Add this method to the `SeedVCWrapper` class:

```python
def convert_voice_gstreamer(self,
                           reference_wav_path: str,
                           diffusion_steps: int = 10,
                           inference_cfg_rate: float = 0.7,
                           input_type: str = 'file',
                           output_type: str = 'file',
                           **io_kwargs):
    """
    Voice conversion with GStreamer I/O.

    Args:
        reference_wav_path: Path to reference voice sample
        diffusion_steps: Number of diffusion steps (4-10 for real-time)
        inference_cfg_rate: CFG rate
        input_type: 'file', 'rtp', 'udp', 'test'
        output_type: 'file', 'rtp', 'udp', 'autoaudiosink'
        **io_kwargs: Additional args for GStreamer (e.g., input_file, port)
    """
    from modules.gstreamer_bridge import GStreamerAudioBridge
    import time

    # Initialize GStreamer bridge
    bridge = GStreamerAudioBridge(sample_rate=self.sr, channels=1)

    # Create pipelines
    bridge.create_input_pipeline(input_type, **io_kwargs)
    bridge.create_output_pipeline(output_type, **io_kwargs)
    bridge.start()

    # Load reference voice
    reference_audio, ref_sr = librosa.load(reference_wav_path, sr=self.sr, mono=True)
    reference_audio = torch.from_numpy(reference_audio).to(self.device)

    # Precompute reference features (same as current implementation)
    with torch.no_grad():
        # Resample to 16kHz for Whisper
        reference_16k = torchaudio.functional.resample(
            reference_audio, self.sr, 16000
        )

        # Extract Whisper features
        whisper_feature = self.whisper_feature_extractor(
            reference_16k.cpu().numpy(),
            sampling_rate=16000,
            return_tensors="pt"
        ).input_features.to(self.device)

        whisper_embed = self.whisper_model.encoder(
            whisper_feature.to(self.whisper_model.dtype)
        ).last_hidden_state.to(torch.float32)

        # Extract speaker style
        fbank = torchaudio.compliance.kaldi.fbank(
            reference_16k.unsqueeze(0),
            num_mel_bins=80,
            dither=0,
            sample_frequency=16000
        )
        fbank = fbank - fbank.mean(dim=0, keepdim=True)
        style_embed = self.campplus_model(fbank.unsqueeze(0))

        # Mel spectrogram of reference
        mel_ref = self.to_mel(reference_audio.unsqueeze(0).unsqueeze(0))

        # Compute prompt condition
        ref_lengths = torch.LongTensor([mel_ref.size(2)]).to(self.device)
        prompt_condition = self.model.length_regulator(
            whisper_embed, ylens=ref_lengths, n_quantizers=3, f0=None
        )[0]

    # Processing parameters
    chunk_duration = 0.18  # 180ms as in real-time-gui.py
    chunk_size = int(self.sr * chunk_duration)
    overlap_size = int(self.sr * 0.04)  # 40ms overlap

    # Accumulator for input audio
    input_accumulator = []
    previous_output_tail = None

    print(f"Starting real-time voice conversion...")
    print(f"Chunk size: {chunk_size} samples ({chunk_duration * 1000}ms)")
    print(f"Sample rate: {self.sr} Hz")
    print("Press Ctrl+C to stop")

    try:
        while True:
            # Check if we have enough input
            available = bridge.get_input_available()

            if available >= chunk_size:
                # Read chunk
                source_chunk = bridge.read_input(chunk_size)

                if source_chunk is None:
                    time.sleep(0.01)
                    continue

                # Convert to torch tensor
                source_tensor = torch.from_numpy(source_chunk).to(self.device)

                # Process with Seed-VC
                with torch.no_grad():
                    # Extract features from source
                    source_16k = torchaudio.functional.resample(
                        source_tensor, self.sr, 16000
                    )

                    # Whisper features
                    whisper_feat = self.whisper_feature_extractor(
                        source_16k.cpu().numpy(),
                        sampling_rate=16000,
                        return_tensors="pt"
                    ).input_features.to(self.device)

                    source_embed = self.whisper_model.encoder(
                        whisper_feat.to(self.whisper_model.dtype)
                    ).last_hidden_state.to(torch.float32)

                    # Mel spectrogram
                    mel_source = self.to_mel(source_tensor.unsqueeze(0).unsqueeze(0))

                    # Length regulator
                    source_lengths = torch.LongTensor([mel_source.size(2)]).to(self.device)
                    cond = self.model.length_regulator(
                        source_embed, ylens=source_lengths, n_quantizers=3, f0=None
                    )[0]

                    # Concatenate with prompt
                    cond = torch.cat([prompt_condition, cond], dim=1)

                    # Run diffusion
                    max_source_length = mel_source.size(2) + mel_ref.size(2)
                    mel_output = self.model.cfm.inference(
                        cond,
                        torch.LongTensor([max_source_length]).to(self.device),
                        mel_ref,
                        style_embed,
                        None,  # F0
                        diffusion_steps,
                        inference_cfg_rate=inference_cfg_rate
                    )

                    # Remove reference portion
                    mel_output = mel_output[:, :, mel_ref.size(2):]

                    # Vocoding
                    vocoded = self.campplus_model.bigvgan(mel_output)
                    output_chunk = vocoded.squeeze().cpu().numpy()

                # Apply overlap-add if we have previous output
                if previous_output_tail is not None and overlap_size > 0:
                    # Crossfade
                    fade_in = np.linspace(0, 1, overlap_size)
                    fade_out = 1 - fade_in

                    output_chunk[:overlap_size] = (
                        output_chunk[:overlap_size] * fade_in +
                        previous_output_tail * fade_out
                    )

                # Save tail for next iteration
                previous_output_tail = output_chunk[-overlap_size:].copy()

                # Write to output
                bridge.write_output(output_chunk)

            else:
                # Not enough data, wait
                time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nStopping...")

    finally:
        bridge.stop()
        print("Voice conversion stopped")
```

---

## Step 3: Test End-to-End

### Test with File Input/Output

```bash
# Create test script
cat > test_gstreamer_vc.py << 'EOF'
from seed_vc_wrapper import SeedVCWrapper

# Initialize wrapper
vc = SeedVCWrapper()

# Run voice conversion
# Input: test_source.wav
# Reference: test_reference.wav
# Output: output_converted.wav
vc.convert_voice_gstreamer(
    reference_wav_path='examples/reference.wav',
    diffusion_steps=10,
    input_type='file',
    output_type='file',
    input_file='examples/source.wav',
    output_file='output_converted.wav'
)

print("Done! Check output_converted.wav")
EOF

python test_gstreamer_vc.py
```

### Test with Network Streaming (RTP)

**Terminal 1 (Sender - sends audio to port 5004):**
```bash
gst-launch-1.0 filesrc location=examples/source.wav ! \
    decodebin ! audioconvert ! audioresample ! \
    audio/x-raw,rate=48000 ! opusenc ! rtpopuspay ! \
    udpsink host=127.0.0.1 port=5004
```

**Terminal 2 (Seed-VC Server - receives on 5004, sends on 5005):**
```python
from seed_vc_wrapper import SeedVCWrapper

vc = SeedVCWrapper()
vc.convert_voice_gstreamer(
    reference_wav_path='examples/reference.wav',
    diffusion_steps=10,
    input_type='rtp',
    output_type='rtp',
    port=5004,  # Input port
    host='127.0.0.1',  # Output host
    port=5005  # Output port
)
```

**Terminal 3 (Receiver - receives converted audio from port 5005):**
```bash
gst-launch-1.0 udpsrc port=5005 caps="application/x-rtp" ! \
    rtpjitterbuffer ! rtpopusdepay ! opusdec ! \
    audioconvert ! autoaudiosink
```

---

## Step 4: WebRTC Integration (Browser-to-Cloud)

See `GSTREAMER_INTEGRATION_ANALYSIS.md` Phase 2 for full WebRTC implementation.

Quick start:

1. Install additional dependencies:
```bash
pip install aiohttp aiortc
```

2. Create signaling server (see analysis doc)
3. Create HTML client (see analysis doc)
4. Run server:
```bash
python server/webrtc_server.py
```

5. Open browser to `http://localhost:8080`

---

## Performance Optimization Tips

### 1. Reduce Diffusion Steps for Real-Time

```python
# Quality vs. Speed trade-off
diffusion_steps = 10  # Real-time (150ms)
# vs.
diffusion_steps = 25  # High quality (350ms)
```

### 2. Use Model Compilation

```python
# In seed_vc_wrapper.py __init__
import torch._dynamo
torch._dynamo.config.suppress_errors = True

# Compile model for faster inference
self.model.cfm.estimator = torch.compile(
    self.model.cfm.estimator,
    mode='reduce-overhead'
)
```

### 3. Batch Processing

Process multiple streams in parallel:

```python
# Process 4 streams simultaneously
batch_size = 4
source_chunks = [stream1, stream2, stream3, stream4]
source_batch = torch.stack(source_chunks)
# Process batch together (4x throughput)
```

### 4. Hardware Encoding (NVIDIA GPU)

```python
# In GStreamer output pipeline, replace opusenc with nvopusenc
pipeline_str = """
    appsrc ! ... !
    nvopusenc ! rtpopuspay ! udpsink
"""
```

---

## Troubleshooting

### Issue: "No module named 'gi'"

**Solution:**
```bash
pip install PyGObject
# If fails, install system dependencies first:
sudo apt-get install libgirepository1.0-dev gcc libcairo2-dev pkg-config python3-dev gir1.2-gtk-3.0
```

### Issue: "Could not find element 'opusenc'"

**Solution:**
```bash
sudo apt-get install gstreamer1.0-plugins-bad
gst-inspect-1.0 opusenc  # Verify
```

### Issue: High latency / Audio dropouts

**Solutions:**
1. Reduce jitter buffer: `rtpjitterbuffer latency=20`
2. Increase buffer size: `appsink max-buffers=20`
3. Use faster GPU
4. Reduce diffusion steps

### Issue: Pipeline errors "Could not link elements"

**Solution:**
Add `audioconvert ! audioresample !` between incompatible elements

---

## Next Steps

1. ✅ Complete basic file-based testing
2. ✅ Test RTP streaming locally
3. ⏭️ Implement WebRTC signaling server
4. ⏭️ Deploy to cloud (Docker + Kubernetes)
5. ⏭️ Load testing and optimization
6. ⏭️ Add monitoring (Prometheus metrics)

---

## Additional Resources

- GStreamer Python Examples: https://github.com/GStreamer/gst-python/tree/master/examples
- WebRTC Samples: https://webrtc.github.io/samples/
- Opus Codec: https://opus-codec.org/

For questions, see the main analysis document: `GSTREAMER_INTEGRATION_ANALYSIS.md`
