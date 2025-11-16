#!/usr/bin/env python3
"""
Test script for GStreamer integration with Seed-VC

This script provides several test modes:
1. Bridge test: Test the GStreamer bridge with passthrough audio
2. File conversion: Convert voice from file to file
3. Real-time test: Test with test tone input and audio output
4. Network streaming: Test RTP streaming (requires two terminals)

Usage:
    # Test 1: Bridge passthrough (you should hear a 440Hz tone)
    python test_gstreamer.py --mode bridge

    # Test 2: File-to-file voice conversion
    python test_gstreamer.py --mode file --source examples/source.wav --reference examples/reference.wav --output output.wav

    # Test 3: Real-time with test tone (you should hear a converted 440Hz tone)
    python test_gstreamer.py --mode realtime --reference examples/reference.wav

    # Test 4: Network streaming (run in two terminals)
    # Terminal 1 (sender): gst-launch-1.0 filesrc location=source.wav ! decodebin ! audioconvert ! audioresample ! audio/x-raw,rate=48000 ! opusenc ! rtpopuspay ! udpsink host=127.0.0.1 port=5004
    # Terminal 2 (receiver): python test_gstreamer.py --mode network --reference examples/reference.wav
"""

import argparse
import sys
import os

def test_bridge():
    """Test 1: Basic GStreamer bridge with passthrough"""
    print("=" * 60)
    print("Test 1: GStreamer Bridge Passthrough")
    print("=" * 60)
    print("This test creates a sine wave input and plays it through")
    print("the audio output. You should hear a 440Hz tone for 5 seconds.")
    print()

    try:
        from modules.gstreamer_bridge import GStreamerAudioBridge
    except ImportError as e:
        print(f"Error: {e}")
        print("\nPlease install GStreamer and PyGObject:")
        print("  sudo apt-get install gstreamer1.0-tools gstreamer1.0-plugins-* python3-gi")
        print("  pip install PyGObject")
        return False

    import time

    bridge = GStreamerAudioBridge(sample_rate=22050, debug=True)

    # Test tone input, audio output
    bridge.create_input_pipeline('test', frequency=440)
    bridge.create_output_pipeline('autoaudiosink')

    bridge.start()
    print("\nPlaying 440Hz tone for 5 seconds...")

    chunk_size = 4096
    duration = 5.0
    samples_to_process = int(22050 * duration)
    processed_samples = 0

    try:
        while processed_samples < samples_to_process:
            chunk = bridge.read_input(chunk_size)

            if chunk is not None:
                # Passthrough (no processing)
                bridge.write_output(chunk)
                processed_samples += len(chunk)
            else:
                time.sleep(0.01)

        print("\n✓ Bridge test completed successfully!")
        return True

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        return False

    except Exception as e:
        print(f"\n✗ Bridge test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        bridge.stop()


def test_file_conversion(source_file, reference_file, output_file, diffusion_steps=10):
    """Test 2: File-to-file voice conversion with GStreamer"""
    print("=" * 60)
    print("Test 2: File-to-File Voice Conversion")
    print("=" * 60)
    print(f"Source: {source_file}")
    print(f"Reference: {reference_file}")
    print(f"Output: {output_file}")
    print(f"Diffusion steps: {diffusion_steps}")
    print()

    if not os.path.exists(source_file):
        print(f"✗ Source file not found: {source_file}")
        return False

    if not os.path.exists(reference_file):
        print(f"✗ Reference file not found: {reference_file}")
        return False

    try:
        from seed_vc_wrapper import SeedVCWrapper
    except ImportError as e:
        print(f"Error importing SeedVCWrapper: {e}")
        return False

    try:
        print("Loading Seed-VC models (this may take a minute)...")
        vc_wrapper = SeedVCWrapper()

        print("\nStarting voice conversion with GStreamer...")
        vc_wrapper.convert_voice_gstreamer(
            reference_wav_path=reference_file,
            diffusion_steps=diffusion_steps,
            input_type='file',
            output_type='file',
            input_file=source_file,
            output_file=output_file
        )

        if os.path.exists(output_file):
            print(f"\n✓ Voice conversion completed successfully!")
            print(f"Output saved to: {output_file}")
            return True
        else:
            print(f"\n✗ Output file was not created")
            return False

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        return False

    except Exception as e:
        print(f"\n✗ File conversion test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_realtime(reference_file, diffusion_steps=10):
    """Test 3: Real-time voice conversion with test tone"""
    print("=" * 60)
    print("Test 3: Real-Time Voice Conversion")
    print("=" * 60)
    print(f"Reference: {reference_file}")
    print(f"Diffusion steps: {diffusion_steps}")
    print()
    print("This test uses a 440Hz sine wave as input and plays")
    print("the converted audio through your speakers.")
    print()

    if not os.path.exists(reference_file):
        print(f"✗ Reference file not found: {reference_file}")
        return False

    try:
        from seed_vc_wrapper import SeedVCWrapper
    except ImportError as e:
        print(f"Error importing SeedVCWrapper: {e}")
        return False

    try:
        print("Loading Seed-VC models (this may take a minute)...")
        vc_wrapper = SeedVCWrapper()

        print("\nStarting real-time voice conversion...")
        print("Press Ctrl+C to stop")
        print()

        vc_wrapper.convert_voice_gstreamer(
            reference_wav_path=reference_file,
            diffusion_steps=diffusion_steps,
            input_type='test',
            output_type='autoaudiosink',
            frequency=440,
            chunk_duration_ms=180.0
        )

        print("\n✓ Real-time test completed successfully!")
        return True

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        return True  # User interruption is expected for real-time test

    except Exception as e:
        print(f"\n✗ Real-time test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_network(reference_file, diffusion_steps=10, input_port=5004, output_port=5005):
    """Test 4: Network streaming with RTP"""
    print("=" * 60)
    print("Test 4: Network Streaming (RTP)")
    print("=" * 60)
    print(f"Reference: {reference_file}")
    print(f"Input port: {input_port} (RTP)")
    print(f"Output port: {output_port} (RTP)")
    print()
    print("This test expects RTP audio stream on the input port.")
    print("You can send audio using GStreamer in another terminal:")
    print()
    print(f"  gst-launch-1.0 filesrc location=source.wav ! \\")
    print(f"    decodebin ! audioconvert ! audioresample ! \\")
    print(f"    audio/x-raw,rate=48000 ! opusenc ! rtpopuspay ! \\")
    print(f"    udpsink host=127.0.0.1 port={input_port}")
    print()
    print("And receive the converted audio using:")
    print()
    print(f"  gst-launch-1.0 udpsrc port={output_port} caps='application/x-rtp' ! \\")
    print(f"    rtpjitterbuffer ! rtpopusdepay ! opusdec ! \\")
    print(f"    audioconvert ! autoaudiosink")
    print()

    if not os.path.exists(reference_file):
        print(f"✗ Reference file not found: {reference_file}")
        return False

    try:
        from seed_vc_wrapper import SeedVCWrapper
    except ImportError as e:
        print(f"Error importing SeedVCWrapper: {e}")
        return False

    try:
        print("Loading Seed-VC models (this may take a minute)...")
        vc_wrapper = SeedVCWrapper()

        print("\nStarting network streaming voice conversion...")
        print("Waiting for RTP input stream...")
        print("Press Ctrl+C to stop")
        print()

        vc_wrapper.convert_voice_gstreamer(
            reference_wav_path=reference_file,
            diffusion_steps=diffusion_steps,
            input_type='rtp',
            output_type='rtp',
            port=input_port,
            host='127.0.0.1',
            output_port=output_port,
            chunk_duration_ms=180.0
        )

        print("\n✓ Network streaming test completed successfully!")
        return True

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        return True  # User interruption is expected

    except Exception as e:
        print(f"\n✗ Network streaming test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Test GStreamer integration with Seed-VC',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--mode', choices=['bridge', 'file', 'realtime', 'network'],
                        default='bridge',
                        help='Test mode (default: bridge)')

    parser.add_argument('--source', type=str,
                        help='Source audio file (for file mode)')

    parser.add_argument('--reference', type=str,
                        help='Reference voice audio file (required for file/realtime/network modes)')

    parser.add_argument('--output', type=str, default='output_gstreamer.wav',
                        help='Output file path (for file mode, default: output_gstreamer.wav)')

    parser.add_argument('--diffusion-steps', type=int, default=10,
                        help='Number of diffusion steps (default: 10)')

    parser.add_argument('--input-port', type=int, default=5004,
                        help='Input RTP port (for network mode, default: 5004)')

    parser.add_argument('--output-port', type=int, default=5005,
                        help='Output RTP port (for network mode, default: 5005)')

    args = parser.parse_args()

    # Validate arguments
    if args.mode in ['file', 'realtime', 'network'] and not args.reference:
        print("Error: --reference is required for file/realtime/network modes")
        return 1

    if args.mode == 'file' and not args.source:
        print("Error: --source is required for file mode")
        return 1

    # Run the selected test
    success = False

    if args.mode == 'bridge':
        success = test_bridge()

    elif args.mode == 'file':
        success = test_file_conversion(
            args.source,
            args.reference,
            args.output,
            args.diffusion_steps
        )

    elif args.mode == 'realtime':
        success = test_realtime(
            args.reference,
            args.diffusion_steps
        )

    elif args.mode == 'network':
        success = test_network(
            args.reference,
            args.diffusion_steps,
            args.input_port,
            args.output_port
        )

    # Print summary
    print()
    print("=" * 60)
    if success:
        print("✓ Test PASSED")
    else:
        print("✗ Test FAILED")
    print("=" * 60)

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
