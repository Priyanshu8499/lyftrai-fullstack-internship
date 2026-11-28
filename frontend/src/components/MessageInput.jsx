import { useCallback, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";

export default function MessageInput({ onSend, isLoading }) {
  const [value, setValue] = useState("");
  const textarea = useRef(null);
  const handleSend = useCallback(() => {
    const text = value.trim();
    if (!text || isLoading) return;
    setValue("");
    if (textarea.current) textarea.current.style.height = "auto";
    onSend(text);
  }, [value, isLoading, onSend]);
  const handleChange = (event) => {
    setValue(event.target.value);
    event.target.style.height = "auto";
    event.target.style.height = `${Math.min(event.target.scrollHeight, 180)}px`;
  };
  const handleKeyDown = (event) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="composer-box">
      <textarea
        ref={textarea}
        data-testid="chat-input"
        className="chat-input"
        placeholder="Message Jimmy…"
        aria-label="Message Jimmy"
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        disabled={isLoading}
        rows={1}
        maxLength={4000}
      />
      <div className="composer-controls">
        <span className="input-hint">
          {value.length > 3600 ? `${value.length}/4000 · ` : ""}Shift + Enter
          for a new line
        </span>
        <button
          data-testid="send-button"
          className="send-button"
          onClick={handleSend}
          disabled={isLoading || !value.trim()}
          aria-label="Send message"
        >
          {isLoading ? (
            <span className="send-spinner" />
          ) : (
            <ArrowUp size={19} strokeWidth={2.5} />
          )}
        </button>
      </div>
    </div>
  );
}
