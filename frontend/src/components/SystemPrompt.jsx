import React from "react";

export default function SystemPrompt({ value, onChange }) {
  return (
    <textarea
      id="system-prompt"
      className="system-prompt-input"
      placeholder="e.g. Keep answers concise and use plain language."
      value={value}
      onChange={(event) => onChange(event.target.value)}
      rows={4}
      maxLength={2000}
    />
  );
}
