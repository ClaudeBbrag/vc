# Janus Gateway Configuration for Seed-VC

This directory contains Janus Gateway configuration files for WebRTC voice conversion.

## Configuration Files

- `janus.jcfg` - Main Janus configuration
- `janus.transport.websockets.jcfg` - WebSocket transport configuration
- `janus.plugin.streaming.jcfg` - Streaming plugin configuration

## Quick Start

### Option 1: Using Docker Compose (Recommended)

The docker-compose.yml already mounts this directory:

```bash
docker-compose up -d janus
```

### Option 2: Manual Janus Installation

```bash
# Install Janus (Ubuntu)
sudo apt-get install libmicrohttpd-dev libjansson-dev \
    libssl-dev libsrtp2-dev libsofia-sip-ua-dev libglib2.0-dev \
    libopus-dev libogg-dev libcurl4-openssl-dev liblua5.3-dev \
    libconfig-dev pkg-config gengetopt libtool automake

# Clone and build Janus
git clone https://github.com/meetecho/janus-gateway.git
cd janus-gateway
sh autogen.sh
./configure --prefix=/opt/janus
make
sudo make install

# Copy configuration
sudo cp /path/to/seed-vc/janus-config/*.jcfg /opt/janus/etc/janus/

# Start Janus
/opt/janus/bin/janus
```

## Stream Configuration

### Stream ID 1: Basic Voice Conversion

**Sends audio TO Seed-VC:**
- Janus receives WebRTC audio from browser
- Forwards as RTP to `localhost:5004` (Seed-VC input)

**Limitation:** Standard Janus streaming plugin is unidirectional. For bidirectional flow, use Stream ID 2 with bridge.

### Stream ID 2: Bidirectional Voice Conversion (Recommended)

Uses the bridge script (`janus_seedvc_bridge.py`) for full duplex:

```
Browser → Janus (WebRTC) → RTP:6000 → Bridge → RTP:5004 → Seed-VC
Browser ← Janus (WebRTC) ← RTP:6001 ← Bridge ← RTP:5005 ← Seed-VC
```

**Start the bridge:**
```bash
python3 janus_seedvc_bridge.py \
    --seedvc-input-port 5004 \
    --seedvc-output-port 5005 \
    --janus-input-port 6000 \
    --janus-output-port 6001
```

## Testing

### Test Janus is Running

```bash
# Check Janus info endpoint
curl http://localhost:8088/janus/info

# Expected response:
# {"janus":"server_info","name":"Janus WebRTC Server",...}
```

### Test WebSocket Connection

```bash
# Using websocat (install with: cargo install websocat)
websocat ws://localhost:8188/janus

# Or use the browser client
```

### Test Audio Stream

```bash
# Send test audio to Janus stream
gst-launch-1.0 audiotestsrc freq=440 ! audioconvert ! \
    audioresample ! audio/x-raw,rate=48000,channels=2 ! \
    opusenc bitrate=64000 ! rtpopuspay ! \
    udpsink host=localhost port=5002
```

## SSL/TLS Configuration (Production)

For production, enable HTTPS/WSS:

1. **Get SSL certificate:**
```bash
# Using Let's Encrypt
sudo certbot certonly --standalone -d your-domain.com
```

2. **Update configuration:**
Edit `janus.jcfg`:
```ini
[certificates]
cert_pem = /etc/letsencrypt/live/your-domain.com/fullchain.pem
cert_key = /etc/letsencrypt/live/your-domain.com/privkey.pem
```

Edit `janus.transport.websockets.jcfg`:
```ini
[wss]
enabled = yes
port = 8989
wss_certificate = /etc/letsencrypt/live/your-domain.com/fullchain.pem
wss_key = /etc/letsencrypt/live/your-domain.com/privkey.pem
```

3. **Update browser client to use WSS:**
```javascript
server: 'wss://your-domain.com:8989/janus'
```

## STUN/TURN Configuration

For NAT traversal, configure STUN/TURN servers:

**Edit `janus.jcfg`:**
```ini
[general]
stun_server = stun.l.google.com
stun_port = 19302

[nat]
turn_server = turn:your-turn-server.com:3478
turn_user = username
turn_pwd = password
```

**Or use TURN REST API (recommended for dynamic credentials):**
```ini
[nat]
turn_rest_api = https://your-domain.com/turn-credentials
turn_rest_api_key = your-secret-key
turn_rest_api_method = POST
```

## Troubleshooting

### Janus won't start

```bash
# Check configuration syntax
/opt/janus/bin/janus --check-config

# View logs
journalctl -u janus -f
```

### WebSocket connection fails

```bash
# Check Janus is listening
netstat -tulpn | grep 8188

# Check firewall
sudo ufw allow 8188/tcp
```

### No audio in browser

1. Check browser console for WebRTC errors
2. Verify ICE connection state: `peerConnection.iceConnectionState`
3. Check Janus logs: `/opt/janus/log/janus.log`
4. Verify Seed-VC is receiving audio:
   ```bash
   # Listen on Seed-VC input port
   nc -u -l 5004
   ```

### RTP not reaching Seed-VC

```bash
# Check if RTP packets are being sent
tcpdump -i any -n udp port 5004

# Test with manual RTP send
gst-launch-1.0 audiotestsrc ! audioconvert ! \
    audioresample ! audio/x-raw,rate=48000 ! \
    opusenc ! rtpopuspay ! udpsink host=localhost port=5004
```

## Advanced: Custom Janus Plugin

For tighter integration, you can create a custom Janus plugin that:
1. Receives WebRTC audio
2. Forwards to Seed-VC via RTP
3. Receives processed audio
4. Sends back via WebRTC

This eliminates the need for the bridge script but requires C programming.

See: https://janus.conf.meetecho.com/docs/plugin.html

## Resources

- **Janus Documentation:** https://janus.conf.meetecho.com/docs/
- **Janus GitHub:** https://github.com/meetecho/janus-gateway
- **Streaming Plugin:** https://janus.conf.meetecho.com/docs/streaming.html
- **WebRTC API:** https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API

## Support

For issues with:
- Janus Gateway: https://github.com/meetecho/janus-gateway/issues
- Seed-VC integration: Check the main documentation

---

**Note:** The bridge approach (`janus_seedvc_bridge.py`) is recommended for simplicity. For production at scale, consider developing a custom Janus plugin or using Janus's RTP forwarder feature.
