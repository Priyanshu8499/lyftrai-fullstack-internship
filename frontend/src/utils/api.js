import { isValidSessionId } from "./session";

const API_URL =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? "/api" : "https://lyftrai-chat-backend.onrender.com");

/**
 * Send a chat message to the backend.
 * Returns the parsed JSON response or throws an enriched error.
 */
export async function sendChatMessage({ session_id, message, system_prompt }) {
  if (!isValidSessionId(session_id)) throw new Error("INVALID_SESSION");
  let response;
  try {
    response = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id, message, system_prompt }),
    });
  } catch {
    throw new Error("NETWORK_ERROR");
  }

  if (response.ok) return await response.json();

  if (response.status === 422) {
    let detail = "Unknown validation error";
    try {
      const body = await response.json();
      if (body.detail) {
        if (Array.isArray(body.detail)) {
          detail = body.detail
            .map((e) => e.msg || JSON.stringify(e))
            .join(", ");
        } else {
          detail = String(body.detail);
        }
      }
    } catch {
      // ignore parse error
    }
    const err = new Error("VALIDATION_ERROR");
    err.detail = detail;
    throw err;
  }

  if (response.status === 503) {
    throw new Error("SERVICE_UNAVAILABLE");
  }
  if (response.status === 429) throw new Error("RATE_LIMITED");
  if (response.status === 413) throw new Error("REQUEST_TOO_LARGE");
  if (response.status === 504) throw new Error("AI_TIMEOUT");

  const error = new Error(`HTTP_ERROR_${response.status}`);
  error.status = response.status;
  throw error;
}

async function requestSession(sessionId, suffix = "", method = "GET") {
  if (!isValidSessionId(sessionId)) throw new Error("SESSION_NOT_FOUND");
  let response;
  try {
    response = await fetch(
      `${API_URL}/sessions/${encodeURIComponent(sessionId)}${suffix}`,
      { method },
    );
  } catch {
    throw new Error("NETWORK_ERROR");
  }
  if (response.ok) return method === "GET" ? response.json() : undefined;
  if (response.status === 404) throw new Error("SESSION_NOT_FOUND");
  throw new Error(`HTTP_ERROR_${response.status}`);
}

export const getSessionMessages = (sessionId, beforeId = null) =>
  requestSession(
    sessionId,
    `/messages${beforeId ? `?before_id=${encodeURIComponent(beforeId)}` : ""}`,
  );
export const deleteChatSession = (sessionId) =>
  requestSession(sessionId, "", "DELETE");
