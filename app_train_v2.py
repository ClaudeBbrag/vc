"""
Gradio Web UI for Training Seed-VC V2 Models
Wraps train_v2.py functionality in an easy-to-use web interface
"""
import os
os.environ['HF_HUB_CACHE'] = './checkpoints/hf_cache'
import gradio as gr
import subprocess
import threading
import time
import glob
from pathlib import Path
import queue
import signal

# Global variables for training process management
training_process = None
training_thread = None
stop_training_flag = False
log_queue = queue.Queue()

def get_available_checkpoints():
    """Get list of available checkpoint directories"""
    runs_dir = "runs"
    if not os.path.exists(runs_dir):
        return []
    return [d for d in os.listdir(runs_dir) if os.path.isdir(os.path.join(runs_dir, d))]

def get_checkpoint_files(run_name):
    """Get checkpoint files from a specific run"""
    if not run_name:
        return "No run selected"

    run_dir = os.path.join("runs", run_name)
    if not os.path.exists(run_dir):
        return f"Run directory not found: {run_dir}"

    cfm_checkpoints = sorted(glob.glob(os.path.join(run_dir, "CFM_epoch_*_step_*.pth")))
    ar_checkpoints = sorted(glob.glob(os.path.join(run_dir, "AR_epoch_*_step_*.pth")))

    result = f" **Run: {run_name}**\n\n"

    if cfm_checkpoints:
        result += "**CFM Checkpoints:**\n"
        for ckpt in cfm_checkpoints:
            result += f"  - {os.path.basename(ckpt)}\n"
    else:
        result += "**CFM Checkpoints:** None\n"

    if ar_checkpoints:
        result += "\n**AR Checkpoints:**\n"
        for ckpt in ar_checkpoints:
            result += f"  - {os.path.basename(ckpt)}\n"
    else:
        result += "\n**AR Checkpoints:** None\n"

    return result

def read_process_output(process, queue):
    """Read process output line by line and put in queue"""
    for line in iter(process.stdout.readline, ''):
        if line:
            queue.put(line)
    process.stdout.close()

def start_training(
    dataset_dir,
    run_name,
    batch_size,
    max_steps,
    max_epochs,
    save_every,
    num_workers,
    train_cfm,
    train_ar,
    config_path,
    pretrained_cfm_ckpt,
    pretrained_ar_ckpt,
):
    """Start training process"""
    global training_process, training_thread, stop_training_flag

    # Validation
    if not dataset_dir or not os.path.exists(dataset_dir):
        return "[X] Error: Dataset directory does not exist!"

    if not run_name:
        return "[X] Error: Please provide a run name!"

    if not train_cfm and not train_ar:
        return "[X] Error: Please select at least one model to train (CFM or AR)!"

    if training_process is not None:
        return "[WARNING] Training is already running!"

    # Clear log queue
    while not log_queue.empty():
        try:
            log_queue.get_nowait()
        except:
            pass

    # Build command
    cmd = ["accelerate", "launch", "train_v2.py"]
    cmd.extend(["--config", config_path])
    cmd.extend(["--dataset-dir", dataset_dir])
    cmd.extend(["--run-name", run_name])
    cmd.extend(["--batch-size", str(batch_size)])
    cmd.extend(["--max-steps", str(max_steps)])
    cmd.extend(["--max-epochs", str(max_epochs)])
    cmd.extend(["--save-every", str(save_every)])
    cmd.extend(["--num-workers", str(num_workers)])

    if train_cfm:
        cmd.append("--train-cfm")
    if train_ar:
        cmd.append("--train-ar")
    if pretrained_cfm_ckpt and pretrained_cfm_ckpt.strip():
        cmd.extend(["--pretrained-cfm-ckpt", pretrained_cfm_ckpt])
    if pretrained_ar_ckpt and pretrained_ar_ckpt.strip():
        cmd.extend(["--pretrained-ar-ckpt", pretrained_ar_ckpt])

    # Start training process
    try:
        stop_training_flag = False
        training_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        # Start thread to read output
        training_thread = threading.Thread(
            target=read_process_output,
            args=(training_process, log_queue),
            daemon=True
        )
        training_thread.start()

        command_str = " ".join(cmd)
        return f"[OK] **Training started!**\n\n**Command:**\n```bash\n{command_str}\n```\n\n**Run name:** {run_name}\n**Output directory:** runs/{run_name}\n\nMonitor the logs below for training progress."

    except Exception as e:
        training_process = None
        return f"[X] **Error starting training:**\n{str(e)}"

def stop_training():
    """Stop the training process"""
    global training_process, stop_training_flag

    if training_process is None:
        return "[INFO] No training process is running."

    try:
        stop_training_flag = True
        training_process.terminate()
        training_process.wait(timeout=10)
        training_process = None
        return "[STOP] **Training stopped successfully!**"
    except subprocess.TimeoutExpired:
        training_process.kill()
        training_process = None
        return "[STOP] **Training force-killed (did not stop gracefully).**"
    except Exception as e:
        return f"[X] **Error stopping training:**\n{str(e)}"

def get_training_logs():
    """Get accumulated training logs from queue"""
    logs = []
    while not log_queue.empty():
        try:
            logs.append(log_queue.get_nowait())
        except:
            break

    if logs:
        return "".join(logs)

    if training_process is not None:
        # Check if process is still running
        if training_process.poll() is not None:
            return "\n\n[OK] **Training process finished!**\n"

    return ""

def check_training_status():
    """Check if training is currently running"""
    global training_process

    if training_process is None:
        return "[IDLE] **Status:** Not running"

    if training_process.poll() is None:
        return "[ACTIVE] **Status:** Training in progress..."
    else:
        exit_code = training_process.poll()
        training_process = None
        if exit_code == 0:
            return "[OK] **Status:** Training completed successfully!"
        else:
            return f"[X] **Status:** Training stopped with exit code {exit_code}"

def create_interface():
    """Create Gradio interface"""

    with gr.Blocks(title="Seed-VC V2 Training") as app:
        gr.Markdown("""
        #  Seed-VC V2 Model Training Interface

        Train custom voice conversion models (V2) with an easy-to-use web interface.

        For more information, visit the [GitHub repository](https://github.com/Plachtaa/seed-vc)
        """)

        with gr.Tabs():
            # Training Tab
            with gr.Tab(" Training"):
                with gr.Row():
                    with gr.Column(scale=2):
                        gr.Markdown("###  Dataset Configuration")

                        dataset_dir = gr.Textbox(
                            label="Dataset Directory",
                            placeholder="/path/to/your/audio/files",
                            info="Path to directory containing training audio files (wav/flac/mp3/m4a/opus/ogg)"
                        )

                        run_name = gr.Textbox(
                            label="Run Name",
                            placeholder="my_custom_voice",
                            value="my_run",
                            info="Name for this training run (checkpoints will be saved to runs/<run_name>)"
                        )

                        gr.Markdown("###  Training Parameters")

                        with gr.Row():
                            batch_size = gr.Slider(
                                minimum=1,
                                maximum=16,
                                value=2,
                                step=1,
                                label="Batch Size",
                                info="Increase if you have more GPU memory"
                            )

                            num_workers = gr.Slider(
                                minimum=0,
                                maximum=8,
                                value=0,
                                step=1,
                                label="Num Workers",
                                info="Data loading workers (set to 0 on Windows)"
                            )

                        with gr.Row():
                            max_steps = gr.Number(
                                value=1000,
                                label="Max Steps",
                                info="Maximum training steps (recommended: 1000+)"
                            )

                            max_epochs = gr.Number(
                                value=1000,
                                label="Max Epochs",
                                info="Maximum training epochs"
                            )

                        save_every = gr.Number(
                            value=500,
                            label="Save Every N Steps",
                            info="Checkpoint save interval"
                        )

                        gr.Markdown("###  Model Selection")

                        with gr.Row():
                            train_cfm = gr.Checkbox(
                                label="Train CFM Model",
                                value=True,
                                info="Conditional Flow Matching model (recommended)"
                            )

                            train_ar = gr.Checkbox(
                                label="Train AR Model",
                                value=False,
                                info="Autoregressive model"
                            )

                        gr.Markdown("###  Pretrained Checkpoints (Optional)")

                        config_path = gr.Textbox(
                            label="Config Path",
                            value="configs/v2/vc_wrapper.yaml",
                            info="Path to model configuration file"
                        )

                        pretrained_cfm_ckpt = gr.Textbox(
                            label="Pretrained CFM Checkpoint",
                            placeholder="path/to/cfm_checkpoint.pth (optional)",
                            info="Start from a pretrained CFM model (leave empty to start from scratch)"
                        )

                        pretrained_ar_ckpt = gr.Textbox(
                            label="Pretrained AR Checkpoint",
                            placeholder="path/to/ar_checkpoint.pth (optional)",
                            info="Start from a pretrained AR model (leave empty to start from scratch)"
                        )

                        with gr.Row():
                            start_btn = gr.Button(" Start Training", variant="primary", size="lg")
                            stop_btn = gr.Button(" Stop Training", variant="stop", size="lg")

                    with gr.Column(scale=1):
                        gr.Markdown("###  Training Monitor")

                        status_box = gr.Textbox(
                            label="Status",
                            value="[IDLE] Not running",
                            interactive=False,
                            lines=2
                        )

                        training_info = gr.Markdown("Waiting to start...")

                        gr.Markdown("###  Training Logs")

                        logs_box = gr.Textbox(
                            label="Real-time Logs",
                            lines=20,
                            max_lines=30,
                            interactive=False,
                            autoscroll=True
                        )

                # Button actions
                start_btn.click(
                    fn=start_training,
                    inputs=[
                        dataset_dir,
                        run_name,
                        batch_size,
                        max_steps,
                        max_epochs,
                        save_every,
                        num_workers,
                        train_cfm,
                        train_ar,
                        config_path,
                        pretrained_cfm_ckpt,
                        pretrained_ar_ckpt,
                    ],
                    outputs=training_info
                )

                stop_btn.click(
                    fn=stop_training,
                    outputs=training_info
                )

                # Auto-update logs and status
                app.load(
                    fn=check_training_status,
                    outputs=status_box,
                    every=2
                )

                app.load(
                    fn=get_training_logs,
                    outputs=logs_box,
                    every=1
                )

            # Checkpoints Tab
            with gr.Tab(" Checkpoints"):
                gr.Markdown("""
                ### Saved Model Checkpoints

                View and manage your trained model checkpoints.
                """)

                with gr.Row():
                    with gr.Column(scale=1):
                        refresh_btn = gr.Button(" Refresh List", size="sm")
                        runs_dropdown = gr.Dropdown(
                            label="Select Training Run",
                            choices=get_available_checkpoints(),
                            interactive=True
                        )

                    with gr.Column(scale=2):
                        checkpoint_info = gr.Markdown("Select a run to view checkpoints")

                refresh_btn.click(
                    fn=lambda: gr.Dropdown(choices=get_available_checkpoints()),
                    outputs=runs_dropdown
                )

                runs_dropdown.change(
                    fn=get_checkpoint_files,
                    inputs=runs_dropdown,
                    outputs=checkpoint_info
                )

            # Help Tab
            with gr.Tab(" Help"):
                gr.Markdown("""
                ## Training Guide

                ###  Quick Start

                1. **Prepare your dataset:**
                   - Collect audio files (wav/flac/mp3/m4a/opus/ogg)
                   - Place them in a single directory
                   - Recommended: 1-30 seconds per file, at least 1 minute total

                2. **Configure training:**
                   - Set **Dataset Directory** to your audio folder
                   - Choose a **Run Name** (e.g., "my_voice_v1")
                   - Adjust **Batch Size** based on GPU memory (2-4 typical)
                   - Set **Max Steps** (1000+ recommended, 100 minimum)

                3. **Select model type:**
                   - [OK] **Train CFM** (recommended for voice conversion)
                   - **Train AR** (optional, for advanced style transfer)

                4. **Start training:**
                   - Click **Start Training**
                   - Monitor logs in real-time
                   - Checkpoints saved every N steps

                ###  Training Tips

                - **Minimum data:** 1 utterance, but more is better (5-10 minutes recommended)
                - **Training time:** ~2 minutes on T4 GPU for 100 steps
                - **Batch size:** Start with 2, increase if you have 16GB+ VRAM
                - **Steps:** 100 minimum, 1000+ for best results
                - **GPU recommended:** Training on CPU is very slow

                ###  Output Files

                Checkpoints are saved to: `runs/<run_name>/`

                - **CFM checkpoints:** `CFM_epoch_*_step_*.pth`
                - **AR checkpoints:** `AR_epoch_*_step_*.pth`
                - **Config copy:** `<config_name>.yaml`

                ###  Using Trained Models

                After training, use your models with:

                ```bash
                # For inference (V2)
                python inference_v2.py \\
                  --cfm-checkpoint-path runs/my_run/CFM_epoch_00000_step_01000.pth \\
                  --ar-checkpoint-path runs/my_run/AR_epoch_00000_step_01000.pth \\
                  --source source.wav \\
                  --target reference.wav \\
                  --output ./output

                # For web UI (V2)
                python app_vc_v2.py \\
                  --cfm-checkpoint-path runs/my_run/CFM_epoch_00000_step_01000.pth \\
                  --ar-checkpoint-path runs/my_run/AR_epoch_00000_step_01000.pth
                ```

                ###  Advanced Options

                - **Pretrained checkpoints:** Continue training from existing models
                - **Config path:** Use custom model architectures
                - **Num workers:** Parallel data loading (0 for Windows)
                - **Multi-GPU:** Use `accelerate config` before training

                ###  Troubleshooting

                - **Out of memory:** Reduce batch size to 1
                - **Training too slow:** Check GPU is being used
                - **No improvement:** Train for more steps (1000+)
                - **Process won't stop:** Click Stop button twice

                ###  Resources

                - [GitHub Repository](https://github.com/Plachtaa/seed-vc)
                - [Paper](https://arxiv.org/abs/2406.02402)
                - [Demo](https://plachtaa.github.io/)
                """)

    return app

def main():
    """Launch the Gradio interface"""
    app = create_interface()
    app.queue()  # Enable queuing for better performance
    app.launch(
        share=False,
        server_name="0.0.0.0",
        server_port=7860,
    )

if __name__ == "__main__":
    main()
