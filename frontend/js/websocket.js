/* ═══════════════════════════════════════════════════════════
   J.A.R.V.I.S — WebSocket Manager
   Auto-reconnect, ping, reminder push handling.
   ═══════════════════════════════════════════════════════════ */

JARVIS.ws = (() => {
  let socket = null;
  let pingInterval = null;
  let reconnectTimer = null;
  let reconnectDelay = 2000;
  let isIntentionalClose = false;

  const maxDelay = 30000;

  function connect() {
    if (socket?.readyState === WebSocket.OPEN) return;

    const proto  = location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl  = `${proto}://${location.host}/ws`;

    socket = new WebSocket(wsUrl);
    updateStatus('connecting');

    socket.onopen = () => {
      reconnectDelay = 2000;
      updateStatus('connected');
      startPing();
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    socket.onclose = () => {
      updateStatus('disconnected');
      stopPing();
      if (!isIntentionalClose) scheduleReconnect();
    };

    socket.onerror = () => {
      updateStatus('disconnected');
    };
  }

  function handleMessage(data) {
    switch (data.type) {
      case 'thinking':
        JARVIS.chat?.showThinking();
        break;
      case 'chunk':
        JARVIS.chat?.appendChunk(data.text);
        break;
      case 'stream_end':
        JARVIS.chat?.finalizeStream();
        break;
      case 'response':
        JARVIS.chat?.addJarvisMessage(data.text);
        break;
      case 'reminder':
        JARVIS.toast(`⏰ REMINDER: ${data.text}`, 'reminder', 8000);
        JARVIS.chat?.addSystemMessage(`⏰ Reminder: ${data.text}`);
        if (JARVIS.voice?.autoSpeak) JARVIS.voice.speak(`Reminder: ${data.text}`);
        break;
      case 'feedback_ack':
        break;
      case 'pong':
        break;
    }
  }

  function send(payload) {
    if (socket?.readyState !== WebSocket.OPEN) {
      connect();
      return false;
    }

    const deviceId    = JARVIS.getDeviceId();
    const deviceOwner = JARVIS.storage.get('j_family_member') || JARVIS.storage.get('j_display') || '';
    const displayName = JARVIS.storage.get('j_display') || '';

    socket.send(JSON.stringify({
      device_id:    deviceId,
      device_name:  displayName + "'s Device",
      device_owner: deviceOwner,
      user_agent:   navigator.userAgent,
      private:      JARVIS.storage.get('j_private') || false,
      ...payload,
    }));
    return true;
  }

  function sendMessage(text, imageb64 = null) {
    return send({ type: 'message', text, ...(imageb64 ? { image: imageb64 } : {}) });
  }

  function sendFeedback(userMsg, jarvisResponse, feedback, topic = 'general') {
    return send({ type: 'feedback', user_msg: userMsg, jarvis_response: jarvisResponse, feedback, topic });
  }

  function startPing() {
    stopPing();
    pingInterval = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'ping', device_id: JARVIS.getDeviceId() }));
      }
    }, 30000);
  }

  function stopPing() {
    clearInterval(pingInterval);
    pingInterval = null;
  }

  function scheduleReconnect() {
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 1.5, maxDelay);
      connect();
    }, reconnectDelay);
  }

  function close() {
    isIntentionalClose = true;
    stopPing();
    clearTimeout(reconnectTimer);
    socket?.close();
  }

  function updateStatus(status) {
    const dot  = document.getElementById('conn-dot');
    const text = document.getElementById('conn-text');
    if (dot) dot.className = status;
    const labels = { connected: 'Online', connecting: 'Connecting…', disconnected: 'Offline' };
    if (text) text.textContent = labels[status] || status;
  }

  return { connect, send, sendMessage, sendFeedback, close };
})();
