// websocket.js
JARVIS.ws = (() => {
  let _ws = null;
  let _token = null;
  let _pingInterval = null;
  let _reconnectTimer = null;
  let _reconnectAttempts = 0;
  let _missedPings = 0;
  const MAX_RECONNECT = 10;

  function connect(token) {
    _token = token;
    _reconnectAttempts = 0;
    _doConnect();
  }

  function _doConnect() {
    if (_ws) { _ws.onclose = null; _ws.close(); }
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${location.host}/ws/${_token}`;
    _ws = new WebSocket(url);

    _ws.onopen = () => {
      _reconnectAttempts = 0;
      _missedPings = 0;
      _setStatus(true);
      _startPing();
    };

    _ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        _handleMsg(msg);
      } catch {}
    };

    _ws.onerror = () => {};

    _ws.onclose = () => {
      _setStatus(false);
      _stopPing();
      if (_reconnectAttempts < MAX_RECONNECT) {
        const delay = Math.min(1000 * Math.pow(2, _reconnectAttempts), 30000);
        _reconnectAttempts++;
        _reconnectTimer = setTimeout(_doConnect, delay);
      }
    };
  }

  function disconnect() {
    clearTimeout(_reconnectTimer);
    _stopPing();
    if (_ws) { _ws.onclose = null; _ws.close(); _ws = null; }
    _setStatus(false);
  }

  function send(text, imageB64 = null, isPrivate = false) {
    if (!_ws || _ws.readyState !== WebSocket.OPEN) {
      JARVIS.toast("Not connected. Reconnecting...", "error");
      _doConnect();
      return false;
    }
    _ws.send(JSON.stringify({
      type: "message",
      text,
      image: imageB64 || undefined,
      private: isPrivate,
    }));
    return true;
  }

  function sendFeedback(userMsg, jarvisMsg, feedback) {
    if (!_ws || _ws.readyState !== WebSocket.OPEN) return;
    _ws.send(JSON.stringify({ type: "feedback", user_msg: userMsg, jarvis_msg: jarvisMsg, feedback }));
  }

  function _handleMsg(msg) {
    switch (msg.type) {
      case "connected":
        JARVIS.storage.set("j_device_id", msg.device_id);
        break;
      case "thinking":
        if (JARVIS.chat) JARVIS.chat.showThinking();
        break;
      case "chunk":
        if (JARVIS.chat) JARVIS.chat.appendChunk(msg.text || "");
        break;
      case "stream_end":
        if (JARVIS.chat) JARVIS.chat.finalizeStream();
        break;
      case "response":
        if (JARVIS.chat) JARVIS.chat.addJarvisMessage(msg.text || "");
        break;
      case "reminder":
        JARVIS.toast(msg.text, "info", 8000);
        if (JARVIS.chat) JARVIS.chat.addSystemMessage(msg.text);
        break;
      case "error":
        if (JARVIS.chat) JARVIS.chat.addSystemMessage("Error: " + (msg.text || "Something went wrong"));
        break;
      case "pong":
        _missedPings = 0;
        break;
    }
  }

  function _startPing() {
    _stopPing();
    _pingInterval = setInterval(() => {
      if (_ws && _ws.readyState === WebSocket.OPEN) {
        _missedPings++;
        if (_missedPings >= 3) {
          _doConnect();
          return;
        }
        _ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 30000);
  }

  function _stopPing() {
    if (_pingInterval) { clearInterval(_pingInterval); _pingInterval = null; }
  }

  function _setStatus(online) {
    const dot = document.getElementById("status-dot");
    const lbl = document.getElementById("status-label");
    if (dot) { dot.className = "status-dot " + (online ? "online" : "offline"); }
    if (lbl) lbl.textContent = online ? "Online" : "Reconnecting...";
  }

  return { connect, disconnect, send, sendFeedback };
})();
