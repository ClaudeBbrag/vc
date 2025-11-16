# Docker Deployment Guide for Seed-VC with GStreamer
## Cloud-Ready Voice Conversion with Janus WebRTC Gateway

This guide covers deploying Seed-VC with GStreamer and Janus Gateway using Docker.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Deployment Options](#deployment-options)
5. [Janus Integration](#janus-integration)
6. [Configuration](#configuration)
7. [Scaling](#scaling)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Prerequisites

```bash
# Install Docker and Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install NVIDIA Container Toolkit (for GPU support)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 2. Prepare Reference Voice

```bash
# Create data directory
mkdir -p data

# Copy your reference voice file
cp /path/to/your/reference.wav data/reference.wav
```

### 3. Build and Run

```bash
# Build the Seed-VC Docker image
docker-compose build

# Start services (RTP mode)
docker-compose up -d

# View logs
docker-compose logs -f seedvc-rtp
```

### 4. Test

```bash
# Send audio via RTP (in another terminal)
gst-launch-1.0 filesrc location=test.wav ! \
    decodebin ! audioconvert ! audioresample ! \
    audio/x-raw,rate=48000 ! opusenc ! rtpopuspay ! \
    udpsink host=localhost port=5004

# Receive converted audio
gst-launch-1.0 udpsrc port=5005 caps='application/x-rtp' ! \
    rtpjitterbuffer ! rtpopusdepay ! opusdec ! \
    audioconvert ! autoaudiosink
```

---

## Architecture

### Deployment Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         DOCKER HOST                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Janus Gateway Container                           │    │
│  │  - WebRTC signaling (port 8088)                    │    │
│  │  - STUN/TURN integration                           │    │
│  │  - RTP/RTCP handling                               │    │
│  │  - Multiple concurrent sessions                    │    │
│  └────────────────┬───────────────────────────────────┘    │
│                   │ RTP                                      │
│                   ▼                                          │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Seed-VC RTP Server Container                      │    │
│  │  - NVIDIA GPU access                               │    │
│  │  - GStreamer pipelines                             │    │
│  │  - Voice conversion processing                     │    │
│  │  - RTP input: 5004, output: 5005                  │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Optional: Seed-VC HTTP API Container              │    │
│  │  - REST API for file conversion                    │    │
│  │  - Port 8080                                       │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Optional: COTURN (TURN Server)                    │    │
│  │  - NAT traversal for WebRTC                        │    │
│  │  - Required for production deployment              │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

**WebRTC Flow (via Janus):**
```
Browser → Janus (WebRTC) → RTP → Seed-VC → RTP → Janus (WebRTC) → Browser
```

**Direct RTP Flow:**
```
Client → RTP (port 5004) → Seed-VC → RTP (port 5005) → Client
```

**HTTP API Flow:**
```
Client → HTTP POST /convert → Seed-VC → HTTP Response (WAV) → Client
```

---

## Deployment Options

### Option 1: RTP Mode (Default)

Best for: Direct RTP streaming, testing, controlled environments

```bash
docker-compose up -d
```

This starts:
- Janus Gateway (ports 8088, 10000-10200/udp)
- Seed-VC RTP server (ports 5004/5005 udp)

### Option 2: HTTP API Mode

Best for: File-based conversion, REST API integration

```bash
docker-compose --profile http-mode up -d
```

This starts:
- Seed-VC HTTP server (port 8080)

**Usage:**
```bash
# Convert voice via HTTP API
curl -X POST http://localhost:8080/convert \
    -F "source=@source.wav" \
    -F "reference=@reference.wav" \
    -F "diffusion_steps=10" \
    -o output.wav

# Health check
curl http://localhost:8080/health
```

### Option 3: Production Mode (with Nginx)

Best for: Production deployment, SSL termination, load balancing

```bash
docker-compose --profile production up -d
```

This starts:
- All services
- Nginx reverse proxy (ports 80, 443)
- TURN server (coturn)

---

## Janus Integration

### Why Janus Gateway?

**Janus Gateway** is a production-ready, open-source WebRTC server that handles:
- ✅ WebRTC signaling (SDP offer/answer, ICE candidates)
- ✅ Multiple protocols (HTTP, WebSocket, MQTT, RabbitMQ)
- ✅ NAT traversal (STUN/TURN integration)
- ✅ Recording and playback
- ✅ Clustering for horizontal scaling
- ✅ Plugin system for custom logic

**Advantages over custom WebRTC implementation:**
- Battle-tested in production (used by major telecom companies)
- Handles browser compatibility issues
- Built-in security features
- Active development and community support

### Janus Architecture with Seed-VC

```
┌─────────────────────────────────────────────────────────────┐
│                      Browser Client                          │
│  - WebRTC PeerConnection                                    │
│  - Microphone capture (getUserMedia)                        │
│  - Speaker playback                                         │
└───────────────────────┬─────────────────────────────────────┘
                        │
                WebRTC (DTLS-SRTP)
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                   Janus Gateway                              │
├─────────────────────────────────────────────────────────────┤
│  • WebRTC signaling (WebSocket on port 8088)               │
│  • ICE/STUN/TURN handling                                   │
│  • SDP negotiation                                          │
│  • Media encryption/decryption                              │
│                                                             │
│  Plugin: Streaming Plugin                                   │
│  - Receives WebRTC audio from browser                       │
│  - Converts to RTP                                          │
│  - Sends to Seed-VC (port 5004)                            │
│  - Receives processed audio from Seed-VC (port 5005)       │
│  - Converts back to WebRTC                                  │
│  - Sends to browser                                         │
└───────────────────────┬─────────────────────────────────────┘
                        │ RTP (Opus codec)
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                Seed-VC Processing Server                     │
│  - Receives RTP audio on port 5004                          │
│  - Processes with DiT model (300ms)                         │
│  - Sends RTP audio on port 5005                             │
└─────────────────────────────────────────────────────────────┘
```

### Browser Client Example

```html
<!DOCTYPE html>
<html>
<head>
    <title>Seed-VC WebRTC Voice Conversion</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/webrtc-adapter/8.1.1/adapter.min.js"></script>
    <script src="janus.js"></script>
</head>
<body>
    <h1>Real-Time Voice Conversion</h1>
    <button id="startBtn">Start Conversion</button>
    <button id="stopBtn" disabled>Stop</button>
    <div id="status">Ready</div>

    <script>
        let janus, streaming, localStream;

        // Initialize Janus
        Janus.init({
            debug: "all",
            callback: function() {
                // Create Janus session
                janus = new Janus({
                    server: 'ws://localhost:8088/janus',
                    success: function() {
                        attachStreamingPlugin();
                    },
                    error: function(error) {
                        console.error('Janus error:', error);
                    }
                });
            }
        });

        function attachStreamingPlugin() {
            janus.attach({
                plugin: "janus.plugin.streaming",
                success: function(pluginHandle) {
                    streaming = pluginHandle;
                    console.log("Streaming plugin attached");
                },
                onmessage: function(msg, jsep) {
                    // Handle Janus messages
                    console.log("Janus message:", msg);
                    if (jsep) {
                        streaming.handleRemoteJsep({ jsep: jsep });
                    }
                },
                onremotestream: function(stream) {
                    // Play converted audio
                    const audio = document.createElement('audio');
                    audio.srcObject = stream;
                    audio.autoplay = true;
                    document.getElementById('status').textContent = 'Playing converted audio';
                }
            });
        }

        document.getElementById('startBtn').onclick = async function() {
            // Get microphone
            localStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 48000
                },
                video: false
            });

            // Create offer
            streaming.createOffer({
                media: { audioSend: true, videoSend: false },
                stream: localStream,
                success: function(jsep) {
                    // Send offer to Janus
                    streaming.send({
                        message: { request: "watch" },
                        jsep: jsep
                    });
                    document.getElementById('status').textContent = 'Connected';
                    document.getElementById('startBtn').disabled = true;
                    document.getElementById('stopBtn').disabled = false;
                }
            });
        };

        document.getElementById('stopBtn').onclick = function() {
            streaming.hangup();
            if (localStream) {
                localStream.getTracks().forEach(track => track.stop());
            }
            document.getElementById('status').textContent = 'Disconnected';
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
        };
    </script>
</body>
</html>
```

### Janus Configuration

To use Janus with Seed-VC, you need to configure the streaming plugin to forward RTP to/from Seed-VC.

**Create `janus-config/janus.plugin.streaming.jcfg`:**

```ini
general: {
    events = false
    json = "compact"
}

# Seed-VC Voice Conversion Stream
seedvc-stream: {
    type = "rtp"
    id = 1
    description = "Seed-VC Voice Conversion"
    audio = true
    audioport = 5004          # Send to Seed-VC
    audiopt = 111
    audiocodec = "opus"
    audiofmtp = "useinbandfec=1"

    # Receive converted audio from Seed-VC
    audioport_out = 5005

    # RTP settings
    videoskew = true
    audioskew = true
}
```

**Note:** Janus Gateway configuration can be complex. For production use, consider:
1. Using the official Janus documentation: https://janus.conf.meetecho.com/docs/
2. Exploring Janus Docker images with pre-configured settings
3. Using managed Janus services

---

## Configuration

### Environment Variables

**docker-compose.yml** supports these environment variables:

```bash
# Create .env file
cat > .env << EOF
# Docker network configuration
DOCKER_IP=auto

# Seed-VC configuration
REFERENCE_VOICE=/app/data/reference.wav
DIFFUSION_STEPS=10

# GPU configuration
NVIDIA_VISIBLE_DEVICES=all

# Ports
RTP_INPUT_PORT=5004
RTP_OUTPUT_PORT=5005
HTTP_PORT=8080
JANUS_WS_PORT=8088
EOF
```

### Volume Mounts

- `./data:/app/data` - Reference voice files
- `./models:/app/models` - Cached model weights (persists across restarts)
- `./output:/app/output` - Output files
- `./janus-recordings:/opt/janus/share/janus/recordings` - Janus recordings

### Resource Limits

Edit `docker-compose.yml` to adjust GPU/memory limits:

```yaml
services:
  seedvc-rtp:
    deploy:
      resources:
        limits:
          memory: 8G
        reservations:
          devices:
            - driver: nvidia
              count: 1  # Number of GPUs
              capabilities: [gpu]
```

---

## Scaling

### Horizontal Scaling with Multiple Containers

```bash
# Scale Seed-VC containers
docker-compose up -d --scale seedvc-rtp=3

# Use a load balancer (e.g., Nginx) to distribute RTP streams
```

### Kubernetes Deployment

See separate `k8s/` directory for Kubernetes manifests:

```bash
# Deploy to Kubernetes
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml  # Horizontal Pod Autoscaler
```

### Multi-GPU Support

```yaml
# docker-compose.yml
seedvc-rtp-gpu0:
  <<: *seedvc-rtp
  environment:
    - NVIDIA_VISIBLE_DEVICES=0
  ports:
    - "5004:5004/udp"
    - "5005:5005/udp"

seedvc-rtp-gpu1:
  <<: *seedvc-rtp
  environment:
    - NVIDIA_VISIBLE_DEVICES=1
  ports:
    - "5006:5004/udp"
    - "5007:5005/udp"
```

---

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs seedvc-rtp

# Common issues:
# 1. GPU not available
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# 2. Port conflicts
sudo netstat -tulpn | grep 5004

# 3. Out of memory
docker stats
```

### No audio output

```bash
# Verify GStreamer inside container
docker-compose exec seedvc-rtp gst-inspect-1.0 opusenc

# Test RTP connectivity
docker-compose exec seedvc-rtp nc -u -l 5004  # Listen
# In another terminal:
echo "test" | nc -u localhost 5004  # Send
```

### Janus connection fails

```bash
# Check Janus is running
curl http://localhost:8088/janus/info

# Check WebSocket
websocat ws://localhost:8088/janus
```

### GPU not detected

```bash
# Check NVIDIA driver
nvidia-smi

# Check Docker can access GPU
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# Rebuild with GPU support
docker-compose build --no-cache
```

### High latency

1. Reduce diffusion steps: Edit `server.py` and change `diffusion_steps=10` to `diffusion_steps=4`
2. Adjust jitter buffer: Lower `latency` in GStreamer pipelines
3. Use faster GPU: T4 → A10 → A100

---

## Production Checklist

- [ ] SSL/TLS certificates configured for Janus (HTTPS/WSS)
- [ ] TURN server deployed for NAT traversal
- [ ] Load balancer configured (Nginx/HAProxy)
- [ ] Monitoring setup (Prometheus + Grafana)
- [ ] Log aggregation (ELK stack or similar)
- [ ] Auto-scaling configured (Kubernetes HPA)
- [ ] Backup strategy for model weights
- [ ] Security: Firewall rules, network policies
- [ ] Performance testing completed
- [ ] Disaster recovery plan

---

## Next Steps

1. **Test locally**: `docker-compose up -d`
2. **Configure Janus**: Edit `janus-config/` files
3. **Create browser client**: Use example HTML above
4. **Deploy to cloud**: Use Kubernetes manifests
5. **Set up monitoring**: Add Prometheus metrics

For Kubernetes deployment, see: `KUBERNETES_DEPLOYMENT.md`

For Janus advanced configuration, see: https://janus.conf.meetecho.com/docs/

---

## Resources

- **Janus Gateway**: https://janus.conf.meetecho.com/
- **Docker Compose**: https://docs.docker.com/compose/
- **NVIDIA Container Toolkit**: https://github.com/NVIDIA/nvidia-docker
- **GStreamer**: https://gstreamer.freedesktop.org/
- **WebRTC**: https://webrtc.org/

---

**Need help?** Check the main documentation or create an issue on GitHub.
