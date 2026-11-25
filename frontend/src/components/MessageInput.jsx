import React, { useState, useCallback } from 'react'

export default function MessageInput({ onSend, isLoading }) {
  const [value, setValue] = useState('')

  const handleSend = useCallback(() => {
    const text = value.trim()
    if (!text || isLoading) return
    setValue('')        // clear immediately
    onSend(text)
  }, [value, isLoading, onSend])

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend]
  )

  return (
    <div className="input-row">
      <textarea
        data-testid="chat-input"
        className="chat-input"
        placeholder="Type a message… (Enter to send, Shift+Enter for newline)"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={isLoading}
        rows={2}
      />
      <button
        data-testid="send-button"
        className="send-btn"
        onClick={handleSend}
        disabled={isLoading || !value.trim()}
        aria-label="Send"
      >
        {isLoading ? '…' : '➤'}
      </button>
    </div>
  )
}
