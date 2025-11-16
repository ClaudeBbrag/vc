import React, { useState } from 'react';
import VoiceConversion from './components/VoiceConversion';
import './App.css';

function App() {
  const [janusServer, setJanusServer] = useState(
    process.env.REACT_APP_JANUS_SERVER || 'ws://localhost:8188/janus'
  );
  const [showSettings, setShowSettings] = useState(false);

  return (
    <div className="App">
      <header className="App-header">
        <div className="settings-toggle">
          <button onClick={() => setShowSettings(!showSettings)}>
            ⚙️ Settings
          </button>
        </div>

        {showSettings && (
          <div className="settings-panel">
            <label>
              Janus Server URL:
              <input
                type="text"
                value={janusServer}
                onChange={(e) => setJanusServer(e.target.value)}
                placeholder="ws://localhost:8188/janus"
              />
            </label>
            <button onClick={() => setShowSettings(false)}>Close</button>
          </div>
        )}
      </header>

      <main>
        <VoiceConversion janusServer={janusServer} />
      </main>

      <footer className="App-footer">
        <p>
          Powered by <strong>Seed-VC</strong> • WebRTC via <strong>Janus Gateway</strong>
        </p>
        <p className="footer-links">
          <a href="https://github.com/Plachta/Seed-VC" target="_blank" rel="noopener noreferrer">
            GitHub
          </a>
          {' • '}
          <a href="https://janus.conf.meetecho.com" target="_blank" rel="noopener noreferrer">
            Janus Gateway
          </a>
        </p>
      </footer>
    </div>
  );
}

export default App;
