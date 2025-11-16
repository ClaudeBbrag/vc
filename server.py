#!/usr/bin/env python3
"""
Seed-VC GStreamer Server
Simple RTP/HTTP server for real-time voice conversion

Modes:
1. RTP Server: Receives audio on port 5004, sends on port 5005
2. HTTP API: REST API for file-based conversion
3. Health check endpoint
"""

import argparse
import os
import sys
import signal
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SeedVCServer:
    """Simple server for Seed-VC voice conversion"""

    def __init__(self, reference_wav, mode='rtp', port=8080):
        self.reference_wav = reference_wav
        self.mode = mode
        self.port = port
        self.running = False

    def run_rtp_server(self, input_port=5004, output_port=5005, output_host='127.0.0.1'):
        """Run as RTP streaming server"""
        logger.info("Starting Seed-VC RTP Server")
        logger.info(f"Reference voice: {self.reference_wav}")
        logger.info(f"Input: RTP on port {input_port}")
        logger.info(f"Output: RTP to {output_host}:{output_port}")

        from seed_vc_wrapper import SeedVCWrapper

        logger.info("Loading Seed-VC models (this may take 1-2 minutes)...")
        vc_wrapper = SeedVCWrapper()
        logger.info("Models loaded successfully!")

        # Set up signal handler for graceful shutdown
        def signal_handler(sig, frame):
            logger.info("Shutdown signal received, stopping server...")
            self.running = False
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.running = True
        logger.info("Server is ready to process audio streams")

        try:
            vc_wrapper.convert_voice_gstreamer(
                reference_wav_path=self.reference_wav,
                diffusion_steps=10,
                input_type='rtp',
                output_type='rtp',
                port=input_port,
                host=output_host,
                output_port=output_port,
                chunk_duration_ms=180.0
            )
        except Exception as e:
            logger.error(f"Error in RTP server: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    def run_http_server(self):
        """Run as HTTP API server"""
        logger.info("Starting Seed-VC HTTP Server")
        logger.info(f"Port: {self.port}")

        try:
            from flask import Flask, request, send_file, jsonify
            import tempfile
            import uuid
            from seed_vc_wrapper import SeedVCWrapper

            app = Flask(__name__)

            logger.info("Loading Seed-VC models...")
            vc_wrapper = SeedVCWrapper()
            logger.info("Models loaded successfully!")

            @app.route('/health', methods=['GET'])
            def health():
                """Health check endpoint"""
                import torch
                return jsonify({
                    'status': 'healthy',
                    'cuda_available': torch.cuda.is_available(),
                    'cuda_device': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
                })

            @app.route('/convert', methods=['POST'])
            def convert():
                """Voice conversion endpoint"""
                if 'source' not in request.files:
                    return jsonify({'error': 'No source audio provided'}), 400

                source_file = request.files['source']
                reference_file = request.files.get('reference')

                # Use default reference if not provided
                ref_path = self.reference_wav
                if reference_file:
                    # Save uploaded reference temporarily
                    ref_path = f"/tmp/ref_{uuid.uuid4()}.wav"
                    reference_file.save(ref_path)

                # Save source temporarily
                source_path = f"/tmp/source_{uuid.uuid4()}.wav"
                output_path = f"/tmp/output_{uuid.uuid4()}.wav"
                source_file.save(source_path)

                try:
                    # Get parameters
                    diffusion_steps = int(request.form.get('diffusion_steps', 10))
                    f0_condition = request.form.get('f0_condition', 'false').lower() == 'true'

                    logger.info(f"Converting {source_path} with reference {ref_path}")

                    # Perform conversion using GStreamer
                    vc_wrapper.convert_voice_gstreamer(
                        reference_wav_path=ref_path,
                        diffusion_steps=diffusion_steps,
                        input_type='file',
                        output_type='file',
                        input_file=source_path,
                        output_file=output_path,
                        f0_condition=f0_condition
                    )

                    # Return converted file
                    return send_file(output_path, mimetype='audio/wav')

                except Exception as e:
                    logger.error(f"Conversion error: {e}")
                    return jsonify({'error': str(e)}), 500

                finally:
                    # Cleanup
                    for path in [source_path, output_path]:
                        if os.path.exists(path):
                            os.remove(path)
                    if reference_file and os.path.exists(ref_path):
                        os.remove(ref_path)

            @app.route('/', methods=['GET'])
            def index():
                """API information"""
                return jsonify({
                    'service': 'Seed-VC GStreamer Server',
                    'version': '1.0.0',
                    'endpoints': {
                        '/health': 'GET - Health check',
                        '/convert': 'POST - Voice conversion (multipart/form-data with source and optional reference files)'
                    }
                })

            logger.info(f"HTTP server starting on port {self.port}")
            app.run(host='0.0.0.0', port=self.port, threaded=True)

        except ImportError:
            logger.error("Flask not installed. Install with: pip install flask")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error starting HTTP server: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Seed-VC GStreamer Server')

    parser.add_argument('--mode', choices=['rtp', 'http'], default='rtp',
                        help='Server mode (default: rtp)')

    parser.add_argument('--reference', type=str, required=True,
                        help='Path to reference voice audio file')

    parser.add_argument('--input-port', type=int, default=5004,
                        help='RTP input port (rtp mode, default: 5004)')

    parser.add_argument('--output-port', type=int, default=5005,
                        help='RTP output port (rtp mode, default: 5005)')

    parser.add_argument('--output-host', type=str, default='127.0.0.1',
                        help='RTP output host (rtp mode, default: 127.0.0.1)')

    parser.add_argument('--http-port', type=int, default=8080,
                        help='HTTP server port (http mode, default: 8080)')

    args = parser.parse_args()

    # Check reference file exists
    if not os.path.exists(args.reference):
        logger.error(f"Reference file not found: {args.reference}")
        sys.exit(1)

    server = SeedVCServer(args.reference, mode=args.mode, port=args.http_port)

    if args.mode == 'rtp':
        server.run_rtp_server(args.input_port, args.output_port, args.output_host)
    elif args.mode == 'http':
        server.run_http_server()


if __name__ == '__main__':
    main()
