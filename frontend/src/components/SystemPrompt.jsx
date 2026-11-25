import React from 'react'

export default function SystemPrompt({ value, onChange }) {
  return (
    <div className="system-prompt-wrap">
      <label htmlFor="system-prompt" className="system-prompt-label">
        System prompt <span className="system-prompt-opt">(optional)</span>
      </label>
      <textarea
        id="system-prompt"
        data-testid="system-prompt-input"
        className="system-prompt-input"
        placeholder="e.g. You are a helpful assistant that replies concisely."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={2}
      />
    </div>
  )
}
