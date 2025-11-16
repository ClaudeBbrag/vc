"""
GStreamer Audio Bridge for Seed-VC
Handles audio I/O between GStreamer pipelines and Python/NumPy

This module provides a bridge between GStreamer multimedia pipelines and
Python-based audio processing, specifically designed for Seed-VC voice conversion.

Features:
- Network streaming protocols (RTP, WebRTC, UDP)
- File-based I/O for testing
- Thread-safe audio buffering
- Zero-copy data transfer where possible
- Support for various audio codecs (Opus, AAC, etc.)

Author: Claude Code
License: Same as Seed-VC project
"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import numpy as np
import threading
import queue
from typing import Optional, Callable
import time

# Initialize GStreamer
Gst.init(None)


class AudioBuffer:
    """Thread-safe circular audio buffer for streaming audio data"""

    def __init__(self, max_size_samples: int = 48000 * 10):  # 10 seconds at 48kHz
        """
        Initialize audio buffer.

        Args:
            max_size_samples: Maximum buffer size in samples
        """
        self.buffer = np.zeros(max_size_samples, dtype=np.float32)
        self.write_pos = 0
        self.read_pos = 0
        self.lock = threading.Lock()
        self.max_size = max_size_samples

    def write(self, data: np.ndarray):
        """
        Write audio data to buffer.

        Args:
            data: Audio samples to write (float32)
        """
        with self.lock:
            data_len = len(data)

            # Handle wraparound
            if self.write_pos + data_len <= self.max_size:
                self.buffer[self.write_pos:self.write_pos + data_len] = data
                self.write_pos += data_len
            else:
                # Split write at buffer boundary
                first_part = self.max_size - self.write_pos
                self.buffer[self.write_pos:] = data[:first_part]
                self.buffer[:data_len - first_part] = data[first_part:]
                self.write_pos = data_len - first_part

    def read(self, num_samples: int) -> Optional[np.ndarray]:
        """
        Read audio data from buffer.

        Args:
            num_samples: Number of samples to read

        Returns:
            Numpy array of audio samples or None if not enough data available
        """
        with self.lock:
            available = self._available_samples_unsafe()

            if available < num_samples:
                return None  # Not enough data

            # Handle wraparound
            if self.read_pos + num_samples <= self.max_size:
                data = self.buffer[self.read_pos:self.read_pos + num_samples].copy()
                self.read_pos += num_samples
            else:
                # Split read at buffer boundary
                first_part = self.max_size - self.read_pos
                data = np.zeros(num_samples, dtype=np.float32)
                data[:first_part] = self.buffer[self.read_pos:]
                data[first_part:] = self.buffer[:num_samples - first_part]
                self.read_pos = num_samples - first_part

            # Reset positions if buffer is empty (prevent unbounded growth)
            if self.read_pos == self.write_pos:
                self.read_pos = 0
                self.write_pos = 0

            return data

    def _available_samples_unsafe(self) -> int:
        """Get number of available samples (call with lock held)"""
        if self.write_pos >= self.read_pos:
            return self.write_pos - self.read_pos
        else:
            return (self.max_size - self.read_pos) + self.write_pos

    def available_samples(self) -> int:
        """Get number of samples available in buffer (thread-safe)"""
        with self.lock:
            return self._available_samples_unsafe()

    def clear(self):
        """Clear the buffer"""
        with self.lock:
            self.read_pos = 0
            self.write_pos = 0


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

    def __init__(self, sample_rate: int = 22050, channels: int = 1, debug: bool = False):
        """
        Initialize GStreamer audio bridge.

        Args:
            sample_rate: Target sample rate for processing (Hz)
            channels: Number of audio channels (1=mono, 2=stereo)
            debug: Enable debug output
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.debug = debug

        self.input_pipeline = None
        self.output_pipeline = None
        self.input_buffer = AudioBuffer()
        self.output_buffer = AudioBuffer()

        self.mainloop = None
        self.mainloop_thread = None
        self.running = False

        # Stats
        self.samples_received = 0
        self.samples_sent = 0
        self.errors = []

    def _log(self, message: str):
        """Log debug message if debug mode is enabled"""
        if self.debug:
            print(f"[GStreamerBridge] {message}")

    def create_input_pipeline(self, source_type: str = 'file', **kwargs):
        """
        Create input pipeline based on source type.

        Args:
            source_type: 'file', 'rtp', 'udp', 'test', 'autoaudiosrc'
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
            latency = kwargs.get('latency', 50)  # ms
            pipeline_str = f"""
                udpsrc port={port} caps="application/x-rtp,media=audio,encoding-name=OPUS,payload=96" !
                rtpjitterbuffer latency={latency} !
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

        elif source_type == 'autoaudiosrc':
            # Capture from default microphone
            pipeline_str = f"""
                autoaudiosrc !
                audioconvert !
                audioresample !
                audio/x-raw,rate={self.sample_rate},channels={self.channels},format=F32LE !
                appsink name=sink emit-signals=true max-buffers=10 drop=false
            """

        else:
            raise ValueError(f"Unsupported source type: {source_type}")

        self._log(f"Creating input pipeline ({source_type}):\n{pipeline_str}")

        # Create pipeline
        try:
            self.input_pipeline = Gst.parse_launch(pipeline_str)
        except Exception as e:
            raise RuntimeError(f"Failed to create input pipeline: {e}")

        # Get appsink and connect callback
        appsink = self.input_pipeline.get_by_name('sink')
        if appsink is None:
            raise RuntimeError("Failed to get appsink element")

        appsink.connect('new-sample', self._on_input_sample)

        # Set up bus to watch for errors
        bus = self.input_pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::error', self._on_error)
        bus.connect('message::eos', self._on_eos)
        bus.connect('message::warning', self._on_warning)

        self._log(f"Input pipeline created successfully")

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
            output_sr = kwargs.get('output_sr', 48000)  # RTP typically uses 48kHz

            pipeline_str = f"""
                appsrc name=src format=time is-live=true block=true !
                audio/x-raw,rate={self.sample_rate},channels={self.channels},format=F32LE !
                audioresample !
                audio/x-raw,rate={output_sr} !
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

        self._log(f"Creating output pipeline ({sink_type}):\n{pipeline_str}")

        # Create pipeline
        try:
            self.output_pipeline = Gst.parse_launch(pipeline_str)
        except Exception as e:
            raise RuntimeError(f"Failed to create output pipeline: {e}")

        self.appsrc = self.output_pipeline.get_by_name('src')
        if self.appsrc is None:
            raise RuntimeError("Failed to get appsrc element")

        # Set up bus
        bus = self.output_pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::error', self._on_error)
        bus.connect('message::warning', self._on_warning)

        self._log(f"Output pipeline created successfully")

    def _on_input_sample(self, appsink):
        """Callback when new audio sample arrives"""
        sample = appsink.emit('pull-sample')
        if sample is None:
            self._log("Warning: pull-sample returned None")
            return Gst.FlowReturn.ERROR

        buffer = sample.get_buffer()
        success, map_info = buffer.map(Gst.MapFlags.READ)

        if success:
            # Convert to numpy array
            audio_data = np.frombuffer(map_info.data, dtype=np.float32)
            buffer.unmap(map_info)

            # Write to input buffer
            self.input_buffer.write(audio_data)
            self.samples_received += len(audio_data)

            self._log(f"Received {len(audio_data)} samples, total: {self.samples_received}")

        return Gst.FlowReturn.OK

    def _on_error(self, bus, message):
        """Handle pipeline errors"""
        err, debug = message.parse_error()
        error_msg = f"GStreamer Error: {err}\nDebug info: {debug}"
        print(error_msg)
        self.errors.append(error_msg)

    def _on_eos(self, bus, message):
        """Handle end-of-stream"""
        self._log("End of stream reached")
        if self.mainloop:
            self.mainloop.quit()

    def _on_warning(self, bus, message):
        """Handle pipeline warnings"""
        warn, debug = message.parse_warning()
        self._log(f"GStreamer Warning: {warn}\nDebug: {debug}")

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

        # Ensure correct shape
        if len(audio_data.shape) > 1:
            audio_data = audio_data.flatten()

        # Convert to bytes
        audio_bytes = audio_data.tobytes()

        # Create GStreamer buffer
        buffer = Gst.Buffer.new_wrapped(audio_bytes)

        # Push to pipeline
        ret = self.appsrc.emit('push-buffer', buffer)

        if ret != Gst.FlowReturn.OK:
            self._log(f"Warning: push-buffer returned {ret}")
        else:
            self.samples_sent += len(audio_data)
            self._log(f"Sent {len(audio_data)} samples, total: {self.samples_sent}")

    def start(self):
        """Start both pipelines"""
        if self.running:
            self._log("Bridge already running")
            return

        if self.input_pipeline:
            ret = self.input_pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                raise RuntimeError("Failed to start input pipeline")
            self._log("Input pipeline started")

        if self.output_pipeline:
            ret = self.output_pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                raise RuntimeError("Failed to start output pipeline")
            self._log("Output pipeline started")

        # Start GLib main loop in separate thread
        self.mainloop = GLib.MainLoop()
        self.mainloop_thread = threading.Thread(target=self._run_mainloop, daemon=True)
        self.mainloop_thread.start()
        self.running = True

        self._log("GStreamer bridge started")

    def _run_mainloop(self):
        """Run GLib main loop (runs in separate thread)"""
        try:
            self.mainloop.run()
        except Exception as e:
            self._log(f"Main loop error: {e}")

    def stop(self):
        """Stop both pipelines"""
        if not self.running:
            self._log("Bridge not running")
            return

        self._log("Stopping GStreamer bridge...")

        if self.input_pipeline:
            self.input_pipeline.set_state(Gst.State.NULL)
            self._log("Input pipeline stopped")

        if self.output_pipeline:
            # Send EOS before stopping
            if self.appsrc:
                self.appsrc.emit('end-of-stream')
            time.sleep(0.1)  # Give it time to flush
            self.output_pipeline.set_state(Gst.State.NULL)
            self._log("Output pipeline stopped")

        if self.mainloop:
            self.mainloop.quit()
            if self.mainloop_thread and self.mainloop_thread.is_alive():
                self.mainloop_thread.join(timeout=2.0)

        self.running = False
        self._log("GStreamer bridge stopped")

    def get_input_available(self) -> int:
        """Get number of samples available in input buffer"""
        return self.input_buffer.available_samples()

    def get_stats(self) -> dict:
        """
        Get statistics about the bridge.

        Returns:
            Dictionary with statistics
        """
        return {
            'samples_received': self.samples_received,
            'samples_sent': self.samples_sent,
            'input_buffer_samples': self.input_buffer.available_samples(),
            'errors': len(self.errors),
            'running': self.running
        }


# Example usage and test
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='GStreamer Audio Bridge Test')
    parser.add_argument('--input', default='test', choices=['test', 'file', 'autoaudiosrc'],
                        help='Input source type')
    parser.add_argument('--output', default='autoaudiosink', choices=['autoaudiosink', 'file'],
                        help='Output sink type')
    parser.add_argument('--input-file', default='input.wav', help='Input file path')
    parser.add_argument('--output-file', default='output.wav', help='Output file path')
    parser.add_argument('--duration', type=float, default=5.0, help='Test duration in seconds')
    parser.add_argument('--sample-rate', type=int, default=22050, help='Sample rate')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')

    args = parser.parse_args()

    print(f"Testing GStreamer Audio Bridge...")
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"Sample rate: {args.sample_rate} Hz")
    print(f"Duration: {args.duration} seconds")
    print()

    # Create bridge
    bridge = GStreamerAudioBridge(sample_rate=args.sample_rate, debug=args.debug)

    # Create pipelines
    if args.input == 'test':
        bridge.create_input_pipeline('test', frequency=440)
    elif args.input == 'file':
        bridge.create_input_pipeline('file', input_file=args.input_file)
    elif args.input == 'autoaudiosrc':
        bridge.create_input_pipeline('autoaudiosrc')

    if args.output == 'autoaudiosink':
        bridge.create_output_pipeline('autoaudiosink')
    elif args.output == 'file':
        bridge.create_output_pipeline('file', output_file=args.output_file)

    bridge.start()

    print(f"Bridge started. Processing audio for {args.duration} seconds...")
    if args.input == 'test' and args.output == 'autoaudiosink':
        print("You should hear a 440Hz tone.")

    # Process in chunks
    chunk_size = 4096
    samples_to_process = int(args.sample_rate * args.duration)
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
        stats = bridge.get_stats()
        print("\nTest complete!")
        print(f"Statistics:")
        print(f"  Samples received: {stats['samples_received']}")
        print(f"  Samples sent: {stats['samples_sent']}")
        print(f"  Errors: {stats['errors']}")
