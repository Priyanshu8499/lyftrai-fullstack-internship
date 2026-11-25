import { useState, useCallback } from 'react'
import { generateSessionId } from '../utils/session'
import { sendChatMessage } from '../utils/api'

const SESSION_ID = generateSessionId()

export function useChat() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [systemPrompt, setSystemPrompt] = useState('')

  const addMessage = useCallback((msg) => {
    setMessages((prev) => [...prev, msg])
  }, [])

  const sendMessage = useCallback(
    async (text) => {
      if (!text.trim() || isLoading) return

      // Add user message immediately
      addMessage({ role: 'user', content: text })
      setIsLoading(true)

      try {
        const data = await sendChatMessage({
          session_id: SESSION_ID,
          message: text.trim(),
          system_prompt: systemPrompt || undefined,
        })

        addMessage({
          role: 'assistant',
          content: data.reply,
          metadata: data.metadata,
        })
      } catch (err) {
        let errorText
        if (err.message === 'NETWORK_ERROR') {
          errorText = 'Network error. Please check your connection.'
        } else if (err.message === 'SERVICE_UNAVAILABLE') {
          errorText = 'All AI providers are currently unavailable. Please try again.'
        } else if (err.message === 'VALIDATION_ERROR') {
          errorText = `Invalid request: ${err.detail}`
        } else {
          errorText = `Error: ${err.message}`
        }
        addMessage({ role: 'system', content: errorText })
      } finally {
        setIsLoading(false)
      }
    },
    [isLoading, systemPrompt, addMessage]
  )

  return {
    messages,
    isLoading,
    systemPrompt,
    setSystemPrompt,
    sendMessage,
    sessionId: SESSION_ID,
  }
}
