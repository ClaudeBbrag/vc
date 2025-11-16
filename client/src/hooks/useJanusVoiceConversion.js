/**
 * useJanusVoiceConversion Hook
 *
 * Custom React hook for Janus Gateway WebRTC voice conversion
 * Handles connection, streaming, and voice conversion pipeline
 */

import { useState, useEffect, useRef, useCallback } from 'react';

// Janus will be loaded from CDN in public/index.html
const Janus = window.Janus;

const useJanusVoiceConversion = (janusConfig = {}) => {
  const {
    server = 'ws://localhost:8188/janus',
    streamId = 2, // Use bidirectional stream
    debug = true
  } = janusConfig;

  // State
  const [status, setStatus] = useState('disconnected');
  const [error, setError] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [stats, setStats] = useState({
    latency: 0,
    packetsLost: 0,
    jitter: 0
  });

  // Refs
  const janusRef = useRef(null);
  const streamingRef = useRef(null);
  const localStreamRef = useRef(null);
  const remoteAudioRef = useRef(null);
  const statsIntervalRef = useRef(null);

  /**
   * Initialize Janus
   */
  useEffect(() => {
    if (!Janus) {
      setError('Janus library not loaded. Include janus.js in index.html');
      return;
    }

    Janus.init({
      debug: debug ? 'all' : false,
      callback: () => {
        if (debug) console.log('[Janus] Library initialized');
        setStatus('initialized');
      }
    });

    return () => {
      disconnect();
    };
  }, [debug]);

  /**
   * Connect to Janus Gateway
   */
  const connect = useCallback(() => {
    if (janusRef.current) {
      console.warn('[Janus] Already connected');
      return;
    }

    setStatus('connecting');
    setError(null);

    janusRef.current = new Janus({
      server: server,
      success: () => {
        if (debug) console.log('[Janus] Connected to server');
        setStatus('connected');
        setIsConnected(true);
        attachStreamingPlugin();
      },
      error: (err) => {
        console.error('[Janus] Connection error:', err);
        setError(`Connection failed: ${err}`);
        setStatus('error');
        setIsConnected(false);
      },
      destroyed: () => {
        if (debug) console.log('[Janus] Session destroyed');
        setStatus('disconnected');
        setIsConnected(false);
        setIsStreaming(false);
      }
    });
  }, [server, debug]);

  /**
   * Attach to Janus Streaming Plugin
   */
  const attachStreamingPlugin = useCallback(() => {
    if (!janusRef.current) {
      console.error('[Janus] No session available');
      return;
    }

    janusRef.current.attach({
      plugin: 'janus.plugin.streaming',
      opaqueId: `seedvc-${Date.now()}`,
      success: (pluginHandle) => {
        streamingRef.current = pluginHandle;
        if (debug) console.log('[Janus] Streaming plugin attached', pluginHandle.getId());
        setStatus('ready');
      },
      error: (err) => {
        console.error('[Janus] Plugin attachment error:', err);
        setError(`Plugin error: ${err}`);
        setStatus('error');
      },
      onmessage: (msg, jsep) => {
        if (debug) console.log('[Janus] Message:', msg);

        const event = msg?.streaming;
        const result = msg?.result;

        if (result && result.status) {
          const status = result.status;
          if (status === 'preparing' || status === 'starting') {
            setIsStreaming(true);
          } else if (status === 'stopped') {
            setIsStreaming(false);
            stopLocalStream();
          }
        }

        if (jsep) {
          if (debug) console.log('[Janus] Handling SDP:', jsep);
          streamingRef.current.handleRemoteJsep({ jsep: jsep });
        }
      },
      onremotetrack: (track, mid, on) => {
        if (debug) console.log('[Janus] Remote track:', track.kind, mid, on);

        if (track.kind === 'audio' && on) {
          // Create audio element for converted voice
          if (remoteAudioRef.current) {
            const stream = new MediaStream([track]);
            remoteAudioRef.current.srcObject = stream;
            remoteAudioRef.current.play();
            if (debug) console.log('[Janus] Playing converted audio');
          }
        }
      },
      oncleanup: () => {
        if (debug) console.log('[Janus] Cleanup');
        setIsStreaming(false);
        stopLocalStream();
      }
    });
  }, [debug]);

  /**
   * Start voice conversion streaming
   */
  const startStreaming = useCallback(async () => {
    if (!streamingRef.current) {
      setError('Streaming plugin not attached');
      return;
    }

    if (isStreaming) {
      console.warn('[Janus] Already streaming');
      return;
    }

    try {
      setStatus('requesting-media');

      // Get user media
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 48000,
          channelCount: 1
        },
        video: false
      });

      localStreamRef.current = stream;
      setStatus('media-granted');

      // Watch the stream
      streamingRef.current.send({
        message: {
          request: 'watch',
          id: streamId
        }
      });

      // Create offer
      streamingRef.current.createOffer({
        media: {
          audioSend: true,
          audioRecv: true,
          videoSend: false,
          videoRecv: false,
          data: false
        },
        stream: stream,
        success: (jsep) => {
          if (debug) console.log('[Janus] Offer created:', jsep);
          streamingRef.current.send({
            message: { request: 'start' },
            jsep: jsep
          });
          setStatus('streaming');
          setIsStreaming(true);
          startStatsCollection();
        },
        error: (err) => {
          console.error('[Janus] Offer creation error:', err);
          setError(`Failed to create offer: ${err}`);
          setStatus('error');
          stopLocalStream();
        }
      });

    } catch (err) {
      console.error('[Janus] Media access error:', err);
      setError(`Microphone access denied: ${err.message}`);
      setStatus('error');
    }
  }, [streamId, debug, isStreaming]);

  /**
   * Stop streaming
   */
  const stopStreaming = useCallback(() => {
    if (streamingRef.current) {
      streamingRef.current.send({
        message: { request: 'stop' }
      });
      streamingRef.current.hangup();
    }

    stopLocalStream();
    setIsStreaming(false);
    setStatus('ready');
    stopStatsCollection();
  }, []);

  /**
   * Stop local media stream
   */
  const stopLocalStream = useCallback(() => {
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach(track => track.stop());
      localStreamRef.current = null;
    }
  }, []);

  /**
   * Disconnect from Janus
   */
  const disconnect = useCallback(() => {
    stopStreaming();

    if (janusRef.current) {
      janusRef.current.destroy();
      janusRef.current = null;
    }

    setIsConnected(false);
    setStatus('disconnected');
  }, [stopStreaming]);

  /**
   * Start collecting WebRTC stats
   */
  const startStatsCollection = useCallback(() => {
    stopStatsCollection(); // Clear any existing interval

    statsIntervalRef.current = setInterval(async () => {
      if (!streamingRef.current?.webrtcStuff?.pc) return;

      const pc = streamingRef.current.webrtcStuff.pc;
      const stats = await pc.getStats();

      let latency = 0;
      let packetsLost = 0;
      let jitter = 0;

      stats.forEach(report => {
        if (report.type === 'inbound-rtp' && report.kind === 'audio') {
          packetsLost = report.packetsLost || 0;
          jitter = report.jitter || 0;
        }
        if (report.type === 'candidate-pair' && report.state === 'succeeded') {
          latency = report.currentRoundTripTime * 1000 || 0; // Convert to ms
        }
      });

      setStats({
        latency: Math.round(latency),
        packetsLost,
        jitter: Math.round(jitter * 1000) // Convert to ms
      });
    }, 1000);
  }, []);

  /**
   * Stop stats collection
   */
  const stopStatsCollection = useCallback(() => {
    if (statsIntervalRef.current) {
      clearInterval(statsIntervalRef.current);
      statsIntervalRef.current = null;
    }
  }, []);

  /**
   * Set remote audio element ref
   */
  const setRemoteAudioElement = useCallback((element) => {
    remoteAudioRef.current = element;
  }, []);

  return {
    // State
    status,
    error,
    isConnected,
    isStreaming,
    stats,

    // Actions
    connect,
    disconnect,
    startStreaming,
    stopStreaming,
    setRemoteAudioElement,

    // Refs (for advanced usage)
    janus: janusRef.current,
    streaming: streamingRef.current
  };
};

export default useJanusVoiceConversion;
