import React from 'react'

/**
 * Renders a single message bubble.
 * - user: right-aligned
 * - assistant: left-aligned with metadata
 * - system: centered error/notice
 */
export default function MessageBubble({ message }) {
  const { role, content, metadata } = message

  if (role === 'user') {
    return (
      <div className="msg-row msg-row--user">
        <div className="bubble bubble--user">{content}</div>
      </div>
    )
  }

  if (role === 'system') {
    return (
      <div className="msg-row msg-row--system">
        <div className="bubble bubble--system">{content}</div>
      </div>
    )
  }

  // assistant
  const isCache = metadata?.resolution_source === 'LLM_CACHE'

  return (
    <div className="msg-row msg-row--assistant" data-testid="assistant-message">
      <div className={`bubble bubble--assistant${isCache ? ' bubble--cache' : ''}`}>
        <div className="bubble__text">{content}</div>
        {metadata && (
          <div className={`meta${isCache ? ' meta--cache' : ''}`}>
            <span data-testid="meta-source" className="meta__badge">
              {metadata.resolution_source}
            </span>
            <span className="meta__sep">|</span>
            <span data-testid="meta-model">{metadata.model}</span>
            <span className="meta__sep">|</span>
            <span data-testid="meta-latency">{metadata.latency_ms} ms</span>
            <span className="meta__sep">|</span>
            <span>
              in: <span data-testid="meta-input-tokens">{metadata.input_tokens}</span>
            </span>
            <span className="meta__sep">|</span>
            <span>
              out: <span data-testid="meta-output-tokens">{metadata.output_tokens}</span>
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
