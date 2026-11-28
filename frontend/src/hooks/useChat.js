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
          msg,
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
