import { useState, useCallback } from "react";
import { sendChatMessage } from "../utils/api";

export function useChat(sessionId, initialPrompt = "") {
  const [messageState, setMessageState] = useState({ sessionId, messages: [] });
  const messages =
    messageState.sessionId === sessionId ? messageState.messages : [];
  const [isLoading, setIsLoading] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState(initialPrompt);

  const addMessage = useCallback(
    (msg) => {
      setMessageState((state) => ({
        sessionId,
        messages: [
          ...(state.sessionId === sessionId ? state.messages : []),
          { ...msg, localId: msg.localId || crypto.randomUUID() },
        ],
      }));
    },
    [sessionId],
  );

  const replaceMessages = useCallback(
    (items, targetSessionId = sessionId) =>
      setMessageState({ sessionId: targetSessionId, messages: items }),
    [sessionId],
  );

  const sendMessage = useCallback(
    async (text) => {
      if (!text.trim() || isLoading) return;

      // Add user message immediately
      addMessage({ role: "user", content: text });
      setIsLoading(true);

      try {
        const data = await sendChatMessage({
          session_id: sessionId,
          message: text.trim(),
          system_prompt: systemPrompt || undefined,
        });

        addMessage({
          role: "assistant",
          content: data.reply,
          metadata: data.metadata,
        });
      } catch (err) {
        let errorText;
        if (err.message === "NETWORK_ERROR") {
          errorText = "Network error. Please check your connection.";
        } else if (err.message === "SERVICE_UNAVAILABLE") {
          errorText =
            "AI providers are unavailable. Check provider credentials or quota, then try again.";
        } else if (err.message === "VALIDATION_ERROR") {
          errorText = `Invalid request: ${err.detail}`;
        } else if (err.message === "RATE_LIMITED") {
          errorText = "Jimmy is receiving many requests. Please wait a minute and try again.";
        } else if (err.message === "REQUEST_TOO_LARGE") {
          errorText = "This message is too large to send. Please shorten it and try again.";
        } else if (err.message === "INVALID_SESSION") {
          errorText = "This chat needs a fresh session. Start a new chat and try again.";
        } else if (err.message === "AI_TIMEOUT") {
          errorText = "Jimmy took too long to respond. Please try again.";
        } else if (err.message.startsWith("HTTP_ERROR_")) {
          errorText =
            "Jimmy could not respond right now. Please try again in a moment.";
        } else {
          errorText =
            "Something went wrong while sending your message. Please try again.";
        }
        addMessage({ role: "system", content: errorText });
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, systemPrompt, addMessage, sessionId],
  );

  return {
    messages,
    isLoading,
    systemPrompt,
    setSystemPrompt,
    sendMessage,
    replaceMessages,
  };
}
