# Seed-VC Web Client

Production-ready React application for real-time voice conversion via WebRTC.

## Features

- 🎙️ Real-time voice conversion using Seed-VC
- 🌐 WebRTC streaming via Janus Gateway
- 📊 Live performance metrics (latency, jitter, packet loss)
- 🎨 Modern, responsive UI
- ⚙️ Configurable Janus server URL
- 📱 Mobile-friendly design

## Tech Stack

- **React 18** - UI framework
- **Janus Gateway** - WebRTC server
- **WebRTC API** - Real-time communication
- **Lucide React** - Icons
- **CSS3** - Styling with gradients and animations

## Quick Start

### Prerequisites

- Node.js 16+ and npm
- Janus Gateway server running (see ../janus-config/)
- Seed-VC server running (see ../DOCKER_DEPLOYMENT.md)

### Installation

```bash
cd client
npm install
```

### Development

```bash
# Start development server (http://localhost:3000)
npm start
```

### Production Build

```bash
# Build for production
npm run build

# Serve the build
npx serve -s build
```

### Environment Variables

Create `.env` file:

```bash
REACT_APP_JANUS_SERVER=ws://your-janus-server.com:8188/janus
```

Or configure at runtime via the Settings button in the UI.

## Architecture

```
┌─────────────┐
│   Browser   │
│  (React App)│
└──────┬──────┘
       │ WebRTC
       ▼
┌─────────────────┐
│ Janus Gateway   │
│   (Port 8188)   │
└──────┬──────────┘
       │ RTP
       ▼
┌─────────────────┐
│  Seed-VC Server │
│  (Port 5004/5)  │
└─────────────────┘
```

## Usage

1. **Open the app** in your browser (https required for getUserMedia)
2. **Allow microphone access** when prompted
3. **Click "Start Conversion"** to begin
4. **Speak** into your microphone
5. **Hear** your converted voice through speakers/headphones
6. **Click "Stop Conversion"** when done

### Tips

- Use headphones to avoid feedback
- Keep latency under 600ms for natural conversation
- Stable internet connection improves quality
- Check browser console for debug logs

## Components

### `VoiceConversion.jsx`

Main UI component with:
- Start/Stop controls
- Status indicators
- Performance metrics
- Instructions

### `useJanusVoiceConversion.js`

Custom React hook managing:
- Janus Gateway connection
- WebRTC peer connection
- Media stream handling
- Stats collection
- Error handling

## Deployment

### Docker

```dockerfile
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

Build and run:

```bash
docker build -t seedvc-client .
docker run -p 80:80 seedvc-client
```

### Static Hosting

Deploy the `build/` directory to:
- Netlify
- Vercel
- AWS S3 + CloudFront
- GitHub Pages
- Any static host

### HTTPS Requirement

WebRTC requires HTTPS in production. Options:

1. **Let's Encrypt** (free SSL)
2. **CloudFlare** (free SSL + CDN)
3. **AWS Certificate Manager**
4. **Nginx reverse proxy** with SSL

Example Nginx config:

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        root /var/www/seedvc-client;
        try_files $uri $uri/ /index.html;
    }

    # Proxy WebSocket connections to Janus
    location /janus {
        proxy_pass http://localhost:8188;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Troubleshooting

### "Janus library not loaded"

- Check browser console for script loading errors
- Ensure janus.min.js is loaded from CDN
- Try refreshing the page

### "Microphone access denied"

- Grant microphone permission in browser
- HTTPS is required (except localhost)
- Check browser settings

### "Connection failed"

- Verify Janus Gateway is running: `curl http://localhost:8088/janus/info`
- Check Janus server URL in settings
- Verify network/firewall allows WebSocket connections

### "No audio output"

- Check browser console for WebRTC errors
- Verify Seed-VC server is running
- Check audio output device is working
- Ensure not muted

### High latency

- Use wired internet connection
- Close other bandwidth-heavy applications
- Check server location (geographic distance)
- Monitor performance metrics in app

## Browser Support

- ✅ Chrome/Edge 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Opera 76+
- ❌ IE (not supported)

## Development

### Project Structure

```
client/
├── public/
│   ├── index.html       # HTML template with Janus script
│   └── manifest.json    # PWA manifest
├── src/
│   ├── components/
│   │   ├── VoiceConversion.jsx
│   │   └── VoiceConversion.css
│   ├── hooks/
│   │   └── useJanusVoiceConversion.js
│   ├── App.jsx
│   ├── App.css
│   ├── index.js
│   └── index.css
├── package.json
└── README.md
```

### Adding Features

**Example: Add recording functionality**

```javascript
// In VoiceConversion.jsx
const [recorder, setRecorder] = useState(null);

const startRecording = () => {
  const mediaRecorder = new MediaRecorder(localStream);
  const chunks = [];

  mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
  mediaRecorder.onstop = () => {
    const blob = new Blob(chunks, { type: 'audio/webm' });
    const url = URL.createObjectURL(blob);
    // Download or upload recording
  };

  mediaRecorder.start();
  setRecorder(mediaRecorder);
};
```

### Testing

```bash
# Run tests
npm test

# Run with coverage
npm test -- --coverage
```

## Performance

Expected metrics on good connection:

- **Latency:** 300-600ms
- **Jitter:** <50ms
- **Packet Loss:** <1%
- **Bandwidth:** ~64kbps (Opus codec)

## License

Same as parent Seed-VC project

## Support

For issues:
- Client-specific: Check browser console
- Janus: https://groups.google.com/g/meetecho-janus
- Seed-VC: See main project documentation

## Credits

- **Seed-VC:** https://github.com/Plachta/Seed-VC
- **Janus Gateway:** https://janus.conf.meetecho.com/
- **React:** https://react.dev/
