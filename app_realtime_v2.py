"""
Real-Time Voice Conversion with V2 Models - Web Interface
Uses Gradio for easy-to-use web-based real-time voice conversion
"""
import os
os.environ['HF_HUB_CACHE'] = './checkpoints/hf_cache'
import gradio as gr
import torch
import yaml
import numpy as np
import librosa
import time
import threading
import queue
from collections import deque
from omegaconf import DictConfig
from hydra.utils import instantiate

# Global variables
vc_wrapper = None
device = None
dtype = torch.float16

# Real-time processing state
class RealTimeState:
    def __init__(self):
        self.reference_audio = None
        self.reference_audio_16k = None
        self.target_style = None
        self.target_content_indices = None
        self.prompt_condition = None
        self.target_mel = None
        self.target_mel_len = 0
        self.is_processing = False
        self.audio_queue = queue.Queue(maxsize=10)
        self.output_queue = queue.Queue(maxsize=10)
        self.sola_buffer = None
        self.previous_chunk = None

    def reset(self):
        """Reset the state"""
        self.reference_audio = None
        self.reference_audio_16k = None
        self.target_style = None
        self.target_content_indices = None
        self.prompt_condition = None
        self.target_mel = None
        self.target_mel_len = 0
        self.is_processing = False
        # Clear queues
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except:
                pass
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except:
                pass
        self.sola_buffer = None
        self.previous_chunk = None

rt_state = RealTimeState()

def load_models(cfm_checkpoint_path=None, ar_checkpoint_path=None, compile_ar=False):
    """Load V2 models"""
    global vc_wrapper, device, dtype

    print("Loading V2 models...")
    cfg = DictConfig(yaml.safe_load(open("configs/v2/vc_wrapper.yaml", "r")))
    vc_wrapper = instantiate(cfg)
    vc_wrapper.load_checkpoints(
        ar_checkpoint_path=ar_checkpoint_path,
        cfm_checkpoint_path=cfm_checkpoint_path
    )
    vc_wrapper.to(device)
    vc_wrapper.eval()

    # Setup AR caches
    vc_wrapper.setup_ar_caches(max_batch_size=1, max_seq_len=4096, dtype=dtype, device=device)

    # Compile AR model if requested
    if compile_ar:
        print("Compiling AR model...")
        torch._inductor.config.coordinate_descent_tuning = True
        torch._inductor.config.triton.unique_kernel_names = True
        if hasattr(torch._inductor.config, "fx_graph_cache"):
            torch._inductor.config.fx_graph_cache = True
        vc_wrapper.compile_ar()

    print("Models loaded successfully!")
    return "[OK] Models loaded successfully!"

@torch.no_grad()
@torch.inference_mode()
def prepare_reference_audio(reference_audio_path, max_duration=25):
    """Prepare reference audio for real-time conversion"""
    global rt_state, vc_wrapper

    if reference_audio_path is None:
        return "[ERROR] Please upload a reference audio file"

    try:
        # Load and prepare reference audio
        ref_wave = librosa.load(reference_audio_path, sr=vc_wrapper.sr)[0]

        # Limit to max_duration seconds
        ref_wave = ref_wave[:vc_wrapper.sr * max_duration]

        # Store reference audio
        rt_state.reference_audio = torch.tensor(ref_wave).unsqueeze(0).float().to(device)

        # Resample to 16kHz
        ref_wave_16k = librosa.resample(ref_wave, orig_sr=vc_wrapper.sr, target_sr=16000)
        rt_state.reference_audio_16k = torch.tensor(ref_wave_16k).unsqueeze(0).to(device)

        # Compute target mel spectrogram
        rt_state.target_mel = vc_wrapper.mel_fn(rt_state.reference_audio)
        rt_state.target_mel_len = rt_state.target_mel.size(2)

        with torch.autocast(device_type=device.type, dtype=dtype):
            # Compute target style
            rt_state.target_style = vc_wrapper.compute_style(rt_state.reference_audio_16k)

            # Compute target content features
            rt_state.target_content_indices = vc_wrapper._process_content_features(
                rt_state.reference_audio_16k,
                is_narrow=False
            )

            # Compute prompt condition
            rt_state.prompt_condition, _ = vc_wrapper.cfm_length_regulator(
                rt_state.target_content_indices,
                ylens=torch.LongTensor([rt_state.target_mel_len]).to(device)
            )

        duration = len(ref_wave) / vc_wrapper.sr
        return f"[OK] Reference audio prepared successfully!\nDuration: {duration:.2f}s"

    except Exception as e:
        return f"[ERROR] Error preparing reference audio: {str(e)}"

@torch.no_grad()
@torch.inference_mode()
def process_audio_chunk(audio_chunk, diffusion_steps=10, inference_cfg_rate=0.7):
    """Process a single audio chunk for real-time conversion"""
    global rt_state, vc_wrapper

    if rt_state.reference_audio is None:
        return audio_chunk  # Return original if no reference

    try:
        # Convert audio chunk to tensor
        chunk_wave = torch.tensor(audio_chunk).unsqueeze(0).float().to(device)

        # Resample to 16kHz
        chunk_wave_16k = librosa.resample(
            audio_chunk,
            orig_sr=vc_wrapper.sr,
            target_sr=16000
        )
        chunk_wave_16k_tensor = torch.tensor(chunk_wave_16k).unsqueeze(0).to(device)

        # Compute mel spectrogram
        chunk_mel = vc_wrapper.mel_fn(chunk_wave)
        chunk_mel_len = chunk_mel.size(2)

        with torch.autocast(device_type=device.type, dtype=dtype):
            # Extract content features
            chunk_content_indices = vc_wrapper._process_content_features(
                chunk_wave_16k_tensor,
                is_narrow=False
            )

            # Length regulation
            chunk_cond, _ = vc_wrapper.cfm_length_regulator(
                chunk_content_indices,
                ylens=torch.LongTensor([chunk_mel_len]).to(device)
            )

            # Concatenate with prompt
            cat_condition = torch.cat([rt_state.prompt_condition, chunk_cond], dim=1)

            # Generate mel spectrogram
            with torch.autocast(device_type=device.type, dtype=torch.float32):
                vc_mel = vc_wrapper.cfm.inference(
                    cat_condition,
                    torch.LongTensor([cat_condition.size(1)]).to(device),
                    rt_state.target_mel,
                    rt_state.target_style,
                    diffusion_steps,
                    inference_cfg_rate=[inference_cfg_rate, inference_cfg_rate],
                )

            # Remove prompt portion
            vc_mel = vc_mel[:, :, rt_state.target_mel_len:]

        # Vocoder
        vc_wave = vc_wrapper.vocoder(vc_mel.float()).squeeze()

        return vc_wave.cpu().numpy()

    except Exception as e:
        print(f"Error processing chunk: {e}")
        return audio_chunk

def stream_audio_conversion(
    audio_stream,
    reference_audio,
    diffusion_steps,
    inference_cfg_rate,
    chunk_duration,
):
    """
    Stream audio conversion for Gradio audio streaming interface
    """
    global rt_state, vc_wrapper

    if audio_stream is None:
        return None

    # Prepare reference if needed
    if rt_state.reference_audio is None and reference_audio is not None:
        prepare_reference_audio(reference_audio)

    # Get sample rate and audio data
    sr, audio_data = audio_stream

    # Convert to mono if stereo
    if len(audio_data.shape) > 1:
        audio_data = librosa.to_mono(audio_data.T)

    # Normalize audio
    if audio_data.dtype == np.int16:
        audio_data = audio_data.astype(np.float32) / 32768.0

    # Resample if needed
    if sr != vc_wrapper.sr:
        audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=vc_wrapper.sr)

    # Process audio
    if rt_state.reference_audio is not None:
        converted_audio = process_audio_chunk(
            audio_data,
            diffusion_steps=diffusion_steps,
            inference_cfg_rate=inference_cfg_rate
        )
    else:
        converted_audio = audio_data

    return (vc_wrapper.sr, converted_audio)

def batch_convert_audio(
    source_audio,
    reference_audio,
    diffusion_steps,
    length_adjust,
    intelligibility_cfg,
    similarity_cfg,
    top_p,
    temperature,
    repetition_penalty,
    convert_style,
    anonymization_only
):
    """
    Batch conversion for non-real-time processing
    """
    global vc_wrapper

    if source_audio is None:
        return None, "[ERROR] Please upload source audio"

    if reference_audio is None and not anonymization_only:
        return None, "[ERROR] Please upload reference audio"

    try:
        status = "[PROCESSING] Converting audio..."

        # Save temporary files
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as src_f:
            src_path = src_f.name
            import soundfile as sf
            sf.write(src_path, source_audio[1], source_audio[0])

        if reference_audio is not None:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as ref_f:
                ref_path = ref_f.name
                sf.write(ref_path, reference_audio[1], reference_audio[0])
        else:
            ref_path = src_path  # Use source as reference for anonymization

        # Convert
        start_time = time.time()

        result = None
        for chunk_data, full_data in vc_wrapper.convert_voice_with_streaming(
            source_audio_path=src_path,
            target_audio_path=ref_path,
            diffusion_steps=int(diffusion_steps),
            length_adjust=length_adjust,
            intelligebility_cfg_rate=intelligibility_cfg,
            similarity_cfg_rate=similarity_cfg,
            top_p=top_p,
            temperature=temperature,
            repetition_penalty=repetition_penalty,
            convert_style=convert_style,
            anonymization_only=anonymization_only,
            device=device,
            dtype=dtype,
            stream_output=False,
        ):
            result = full_data

        elapsed = time.time() - start_time

        # Clean up temp files
        os.unlink(src_path)
        if reference_audio is not None:
            os.unlink(ref_path)

        if result is not None:
            status = f"[OK] Conversion complete! Time: {elapsed:.2f}s"
            return (vc_wrapper.sr, result), status
        else:
            return None, "[ERROR] Conversion failed"

    except Exception as e:
        return None, f"[ERROR] Error: {str(e)}"

def create_interface():
    """Create Gradio interface"""

    with gr.Blocks(title="Seed-VC V2 Real-Time Conversion") as app:
        gr.Markdown("""
        # Seed-VC V2 Real-Time Voice Conversion

        Real-time voice conversion using V2 models with style transfer capabilities.

        **Two Modes:**
        - **Batch Mode**: Upload audio files for high-quality conversion
        - **Real-Time Mode**: Process audio in real-time (experimental)
        """)

        with gr.Tabs():
            # Batch Conversion Tab
            with gr.Tab("Batch Conversion"):
                gr.Markdown("""
                Upload audio files for high-quality voice conversion with full V2 features.
                """)

                with gr.Row():
                    with gr.Column():
                        batch_source = gr.Audio(
                            label="Source Audio",
                            type="numpy"
                        )
                        batch_reference = gr.Audio(
                            label="Reference Audio (Target Voice)",
                            type="numpy"
                        )

                        with gr.Accordion("Advanced Settings", open=False):
                            batch_diffusion_steps = gr.Slider(
                                minimum=10,
                                maximum=100,
                                value=30,
                                step=1,
                                label="Diffusion Steps",
                                info="Higher = better quality, slower"
                            )

                            batch_length_adjust = gr.Slider(
                                minimum=0.5,
                                maximum=2.0,
                                value=1.0,
                                step=0.1,
                                label="Length Adjust",
                                info="<1.0 speeds up, >1.0 slows down"
                            )

                            batch_intelligibility = gr.Slider(
                                minimum=0.0,
                                maximum=1.0,
                                value=0.5,
                                step=0.1,
                                label="Intelligibility CFG Rate"
                            )

                            batch_similarity = gr.Slider(
                                minimum=0.0,
                                maximum=1.0,
                                value=0.5,
                                step=0.1,
                                label="Similarity CFG Rate"
                            )

                            batch_top_p = gr.Slider(
                                minimum=0.1,
                                maximum=1.0,
                                value=0.9,
                                step=0.1,
                                label="Top-p",
                                info="Sampling diversity"
                            )

                            batch_temperature = gr.Slider(
                                minimum=0.1,
                                maximum=2.0,
                                value=1.0,
                                step=0.1,
                                label="Temperature",
                                info="Sampling randomness"
                            )

                            batch_repetition = gr.Slider(
                                minimum=1.0,
                                maximum=3.0,
                                value=1.0,
                                step=0.1,
                                label="Repetition Penalty"
                            )

                            batch_convert_style = gr.Checkbox(
                                label="Convert Style/Accent",
                                value=False,
                                info="Enable AR model for style transfer"
                            )

                            batch_anonymization = gr.Checkbox(
                                label="Anonymization Only",
                                value=False,
                                info="Convert to neutral voice"
                            )

                        batch_convert_btn = gr.Button(
                            "Convert Audio",
                            variant="primary",
                            size="lg"
                        )

                    with gr.Column():
                        batch_output = gr.Audio(
                            label="Converted Audio",
                            type="numpy"
                        )
                        batch_status = gr.Textbox(
                            label="Status",
                            value="Ready to convert",
                            interactive=False
                        )

                batch_convert_btn.click(
                    fn=batch_convert_audio,
                    inputs=[
                        batch_source,
                        batch_reference,
                        batch_diffusion_steps,
                        batch_length_adjust,
                        batch_intelligibility,
                        batch_similarity,
                        batch_top_p,
                        batch_temperature,
                        batch_repetition,
                        batch_convert_style,
                        batch_anonymization,
                    ],
                    outputs=[batch_output, batch_status]
                )

            # Real-Time Tab (Simplified)
            with gr.Tab("Real-Time (Experimental)"):
                gr.Markdown("""
                **Note**: Real-time processing requires powerful GPU and has higher latency.
                For best results, use batch mode.

                **Setup**:
                1. Upload reference audio
                2. Click "Prepare Reference"
                3. Use microphone input (if supported by your browser)
                """)

                with gr.Row():
                    with gr.Column():
                        rt_reference = gr.Audio(
                            label="Reference Audio",
                            type="filepath"
                        )
                        rt_prepare_btn = gr.Button("Prepare Reference")
                        rt_status = gr.Textbox(
                            label="Status",
                            value="Upload reference audio and click Prepare",
                            interactive=False
                        )

                        rt_diffusion = gr.Slider(
                            minimum=5,
                            maximum=20,
                            value=10,
                            step=1,
                            label="Diffusion Steps",
                            info="Lower = faster, higher = better quality"
                        )

                        rt_cfg = gr.Slider(
                            minimum=0.0,
                            maximum=1.0,
                            value=0.7,
                            step=0.1,
                            label="CFG Rate"
                        )

                        rt_chunk_duration = gr.Slider(
                            minimum=0.5,
                            maximum=3.0,
                            value=1.0,
                            step=0.5,
                            label="Chunk Duration (seconds)",
                            info="Larger = more stable, higher latency"
                        )

                    with gr.Column():
                        gr.Markdown("""
                        ### Instructions

                        Real-time mode is experimental and may have high latency.

                        **Requirements:**
                        - Strong GPU (RTX 3060 or better recommended)
                        - Low diffusion steps (5-10) for acceptable latency
                        - Good microphone

                        **Expected Latency:**
                        - RTX 3060: ~1-2 seconds
                        - RTX 4090: ~0.5-1 second
                        - CPU: Not recommended (10-30+ seconds)

                        **For Production Use:**
                        Consider using the desktop GUI version (`real-time-gui.py` for V1)
                        which has optimized buffering and lower latency.
                        """)

                rt_prepare_btn.click(
                    fn=prepare_reference_audio,
                    inputs=[rt_reference],
                    outputs=[rt_status]
                )

            # Help Tab
            with gr.Tab("Help"):
                gr.Markdown("""
                ## Usage Guide

                ### Batch Conversion (Recommended)

                1. **Upload Source Audio**: The voice you want to convert
                2. **Upload Reference Audio**: The target voice style
                3. **Adjust Settings**:
                   - **Diffusion Steps**: 30-50 for best quality
                   - **Convert Style**: Enable for accent/emotion transfer (slower)
                   - **Anonymization**: Convert to neutral voice (ignores reference)
                4. **Click Convert**: Wait for processing to complete

                ### Model Loading

                Models are loaded automatically on first use. This may take a minute.

                ### Performance Tips

                **For Best Quality:**
                - Use 50+ diffusion steps
                - Enable style conversion
                - Use longer reference audio (10-20 seconds)

                **For Speed:**
                - Use 10-20 diffusion steps
                - Disable style conversion
                - Use shorter reference audio (3-5 seconds)

                ### Real-Time Mode

                Real-time mode is **experimental** and has limitations:
                - High latency (1-2+ seconds)
                - Requires powerful GPU
                - Lower quality than batch mode
                - Browser compatibility issues

                **For production real-time use**, consider:
                - Desktop GUI version (`real-time-gui.py` for V1 models)
                - Dedicated streaming server setup
                - V1 models (faster, lower latency)

                ### Troubleshooting

                **Out of Memory:**
                - Reduce diffusion steps
                - Use shorter audio clips
                - Disable style conversion
                - Restart the application

                **Poor Quality:**
                - Increase diffusion steps
                - Use cleaner reference audio
                - Enable style conversion
                - Check audio levels

                **Slow Processing:**
                - Reduce diffusion steps
                - Disable style conversion
                - Use shorter audio
                - Check GPU is being used

                ### Advanced Parameters

                - **Intelligibility CFG**: Controls pronunciation clarity
                - **Similarity CFG**: Controls similarity to reference
                - **Top-p**: Sampling diversity (lower = conservative)
                - **Temperature**: Randomness (lower = deterministic)
                - **Repetition Penalty**: Reduces repetitive patterns

                ### Resources

                - [GitHub](https://github.com/Plachtaa/seed-vc)
                - [Paper](https://arxiv.org/abs/2406.02402)
                - [Demo](https://plachtaa.github.io/)
                """)

        return app

def main():
    """Launch the application"""
    global device, dtype, vc_wrapper

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cfm-checkpoint-path", type=str, default=None,
                        help="Path to CFM checkpoint")
    parser.add_argument("--ar-checkpoint-path", type=str, default=None,
                        help="Path to AR checkpoint")
    parser.add_argument("--compile", action="store_true",
                        help="Compile AR model for faster inference")
    parser.add_argument("--share", action="store_true",
                        help="Create public Gradio share link")
    args = parser.parse_args()

    # Set device
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    print(f"Using device: {device}")

    # Load models
    load_models(
        cfm_checkpoint_path=args.cfm_checkpoint_path,
        ar_checkpoint_path=args.ar_checkpoint_path,
        compile_ar=args.compile
    )

    # Create and launch interface
    app = create_interface()
    app.queue()
    app.launch(
        share=args.share,
        server_name="0.0.0.0",
        server_port=7860,
    )

if __name__ == "__main__":
    main()
