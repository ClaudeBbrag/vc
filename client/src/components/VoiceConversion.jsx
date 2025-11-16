/**
 * VoiceConversion Component
 *
 * Main component for real-time voice conversion UI
 */

import React, { useEffect, useRef } from 'react';
import { Mic, MicOff, Loader, AlertCircle, CheckCircle, Activity } from 'lucide-react';
import useJanusVoiceConversion from '../hooks/useJanusVoiceConversion';
import './VoiceConversion.css';

const VoiceConversion = ({ janusServer = 'ws://localhost:8188/janus' }) => {
  const audioRef = useRef(null);

  const {
    status,
    error,
    isConnected,
    isStreaming,
    stats,
    connect,
    disconnect,
    startStreaming,
    stopStreaming,
    setRemoteAudioElement
  } = useJanusVoiceConversion({
    server: janusServer,
    streamId: 2, // Bidirectional stream
    debug: true
  });

  // Set audio element ref when component mounts
  useEffect(() => {
    if (audioRef.current) {
      setRemoteAudioElement(audioRef.current);
    }
  }, [setRemoteAudioElement]);

  // Auto-connect when component mounts
  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  const handleToggleStreaming = () => {
    if (isStreaming) {
      stopStreaming();
    } else {
      startStreaming();
    }
  };

  const getStatusColor = () => {
    if (error) return 'red';
    if (isStreaming) return 'green';
    if (isConnected) return 'blue';
    return 'gray';
  };

  const getStatusText = () => {
    if (error) return `Error: ${error}`;
    if (isStreaming) return 'Streaming (Voice Conversion Active)';
    if (isConnected) return 'Connected - Ready to Start';
    if (status === 'connecting') return 'Connecting to Janus...';
    if (status === 'initialized') return 'Initialized';
    return 'Disconnected';
  };

  const getLatencyColor = () => {
    if (stats.latency < 300) return '#00ff00';
    if (stats.latency < 600) return '#ffaa00';
    return '#ff0000';
  };

  return (
    <div className="voice-conversion">
      <div className="vc-header">
        <h1>🎙️ Seed-VC Real-Time Voice Conversion</h1>
        <p className="vc-subtitle">
          Transform your voice in real-time using state-of-the-art AI
        </p>
      </div>

      {/* Status Indicator */}
      <div className={`vc-status vc-status-${getStatusColor()}`}>
        <div className="status-indicator">
          {error && <AlertCircle size={20} />}
          {!error && isStreaming && <Activity size={20} />}
          {!error && isConnected && !isStreaming && <CheckCircle size={20} />}
          {!error && !isConnected && <Loader size={20} className="spinner" />}
        </div>
        <span className="status-text">{getStatusText()}</span>
      </div>

      {/* Main Control */}
      <div className="vc-control">
        <button
          className={`vc-button ${isStreaming ? 'vc-button-active' : ''}`}
          onClick={handleToggleStreaming}
          disabled={!isConnected || error}
        >
          {isStreaming ? (
            <>
              <MicOff size={32} />
              <span>Stop Conversion</span>
            </>
          ) : (
            <>
              <Mic size={32} />
              <span>Start Conversion</span>
            </>
          )}
        </button>

        {isStreaming && (
          <div className="vc-listening">
            <div className="pulse-animation"></div>
            <span>Listening and converting...</span>
          </div>
        )}
      </div>

      {/* Stats Display */}
      {isStreaming && (
        <div className="vc-stats">
          <h3>Performance Metrics</h3>
          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-label">Latency</div>
              <div className="stat-value" style={{ color: getLatencyColor() }}>
                {stats.latency} ms
              </div>
            </div>
            <div className="stat-item">
              <div className="stat-label">Packets Lost</div>
              <div className="stat-value">
                {stats.packetsLost}
              </div>
            </div>
            <div className="stat-item">
              <div className="stat-label">Jitter</div>
              <div className="stat-value">
                {stats.jitter} ms
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Instructions */}
      <div className="vc-instructions">
        <h3>How to Use</h3>
        <ol>
          <li>Click "Start Conversion" and allow microphone access</li>
          <li>Speak into your microphone</li>
          <li>Hear your voice converted in real-time through your speakers</li>
          <li>Click "Stop Conversion" when finished</li>
        </ol>

        <div className="vc-tips">
          <h4>💡 Tips for Best Results</h4>
          <ul>
            <li>Use headphones to prevent feedback</li>
            <li>Speak clearly and at a normal pace</li>
            <li>Keep latency under 600ms for natural conversation</li>
            <li>Ensure stable internet connection (low jitter)</li>
          </ul>
        </div>
      </div>

      {/* Technical Details */}
      <details className="vc-technical">
        <summary>Technical Details</summary>
        <div className="technical-content">
          <p><strong>Server:</strong> {janusServer}</p>
          <p><strong>Stream ID:</strong> 2 (Bidirectional)</p>
          <p><strong>Audio Codec:</strong> Opus @ 48kHz</p>
          <p><strong>Bitrate:</strong> 64 kbps</p>
          <p><strong>Status:</strong> {status}</p>
          <p><strong>Connected:</strong> {isConnected ? 'Yes' : 'No'}</p>
          <p><strong>Streaming:</strong> {isStreaming ? 'Yes' : 'No'}</p>
        </div>
      </details>

      {/* Hidden audio element for playback */}
      <audio ref={audioRef} autoPlay playsInline />
    </div>
  );
};

export default VoiceConversion;
