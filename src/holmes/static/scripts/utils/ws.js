// WebSocket reconnection configuration
export const WS_CONFIG = {
  initialDelay: 1000, // Start with 1 second
  maxDelay: 30000, // Cap at 30 seconds
  maxRetries: 10, // Circuit breaker after 10 failures
  backoffFactor: 2, // Double delay each retry
  connectionTimeout: 10000, // 10 second connection timeout
};

// Track reconnection state per URL
const reconnectState = new Map();

/**
 * Get current reconnection state for a URL
 */
export function getReconnectState(url) {
  return (
    reconnectState.get(url) || {
      attempts: 0,
      delay: WS_CONFIG.initialDelay,
    }
  );
}

/**
 * Increment reconnection attempt counter and calculate next delay
 */
export function incrementReconnectAttempt(url) {
  const state = getReconnectState(url);
  state.attempts++;
  state.delay = Math.min(
    state.delay * WS_CONFIG.backoffFactor,
    WS_CONFIG.maxDelay,
  );
  reconnectState.set(url, state);
  return state;
}

/**
 * Reset reconnection state (call on successful connection)
 */
export function resetReconnectState(url) {
  reconnectState.delete(url);
}

/**
 * Check if circuit breaker is open (max retries exceeded)
 */
export function isCircuitBreakerOpen(url) {
  const state = getReconnectState(url);
  return state.attempts >= WS_CONFIG.maxRetries;
}

export function connect(url, handleMessage, dispatch, globalDispatch) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const fullUrl = `${protocol}//${window.location.host}/${url}`;

  const ws = new WebSocket(fullUrl);

  // Connection timeout
  const connectionTimeout = setTimeout(() => {
    if (ws.readyState !== WebSocket.OPEN) {
      console.error(`WebSocket connection timeout: ${fullUrl}`);
      ws.close();
    }
  }, WS_CONFIG.connectionTimeout);

  ws.onopen = () => {
    clearTimeout(connectionTimeout);
    resetReconnectState(url);
    dispatch({ type: "Connected", data: ws });
  };

  ws.onmessage = (event) => {
    handleMessage(event, dispatch, globalDispatch);
  };

  ws.onclose = (event) => {
    clearTimeout(connectionTimeout);
    dispatch({ type: "Disconnected" });
  };

  ws.onerror = (error) => {
    console.error(`WebSocket error: ${fullUrl}`, error);
    globalDispatch({
      type: "AddNotification",
      data: { text: `WebSocket error : ${error}`, isError: true },
    });
  };
}
