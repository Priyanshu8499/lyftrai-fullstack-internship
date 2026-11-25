import React from 'react'
import ChatWindow from './components/ChatWindow'
import MessageInput from './components/MessageInput'
import SystemPrompt from './components/SystemPrompt'
import { useChat } from './hooks/useChat'
import './App.css'

export default function App() {
  const { messages, isLoading, systemPrompt, setSystemPrompt, sendMessage, sessionId } = useChat()

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">AI Chat</h1>
        <span className="session-id" title="Session ID">{sessionId}</span>
      </header>

      <SystemPrompt value={systemPrompt} onChange={setSystemPrompt} />

      <ChatWindow messages={messages} isLoading={isLoading} />

      <footer className="app-footer">
        <MessageInput onSend={sendMessage} isLoading={isLoading} />
      </footer>
    </div>
  )
}
