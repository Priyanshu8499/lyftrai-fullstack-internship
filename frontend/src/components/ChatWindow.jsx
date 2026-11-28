import React, { useEffect, useRef } from "react";
import {
  ArrowRight,
  Compass,
  Lightbulb,
  PenLine,
  Sparkles,
} from "lucide-react";
import MessageBubble from "./MessageBubble";

const suggestions = [
  {
    icon: <Lightbulb size={17} />,
    title: "Explain something",
    prompt: "Explain a complex topic in a simple, clear way.",
  },
  {
    icon: <PenLine size={17} />,
    title: "Help me write",
    prompt: "Help me draft a thoughtful message about…",
  },
  {
    icon: <Compass size={17} />,
    title: "Plan a project",
    prompt: "Help me break a new project into practical steps.",
  },
  {
    icon: <Sparkles size={17} />,
    title: "Explore an idea",
    prompt: "Help me explore an idea I have been thinking about.",
  },
];

export default function ChatWindow({ messages, isLoading, onSuggestion }) {
  const bottomRef = useRef(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isLoading]);

  return (
    <div className="conversation-scroll">
      {messages.length === 0 && !isLoading && (
        <section className="welcome-screen">
          <div className="welcome-mark">
            <Sparkles size={22} />
          </div>
          <p className="welcome-overline">A little help goes a long way</p>
          <h1>
            Good to see you.
            <br />
            <span>What’s on your mind?</span>
          </h1>
          <p className="welcome-copy">
            Ask a question, work through an idea, or just get started.
          </p>
          <div className="suggestion-grid">
            {suggestions.map((item) => (
              <button
                key={item.title}
                className="suggestion-card"
                onClick={() => onSuggestion(item.prompt)}
              >
                <span className="suggestion-icon">{item.icon}</span>
                <span className="suggestion-text">
                  <strong>{item.title}</strong>
                  <span>{item.prompt}</span>
                </span>
                <ArrowRight size={16} className="suggestion-arrow" />
              </button>
            ))}
          </div>
        </section>
      )}
      {messages.length > 0 && (
        <div className="message-list">
          {messages.map((msg, i) => (
            <MessageBubble key={`${i}-${msg.role}`} message={msg} />
          ))}
          {isLoading && (
            <article className="assistant-message">
              <div className="assistant-avatar">
                <Sparkles size={16} />
              </div>
              <div className="assistant-content">
                <div className="assistant-name">Jimmy</div>
                <div
                  className="typing-indicator"
                  aria-label="Jimmy is thinking"
                >
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            </article>
          )}
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
