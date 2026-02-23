import { useState, useCallback } from 'react'
import { v4 as uuidv4 } from 'uuid'
import type { Message, ChartData, Sport } from '../types/chat'

const CHART_PATTERN = /\|\|\|CHART\|\|\|([\s\S]*?)\|\|\|END_CHART\|\|\|/g

function extractCharts(text: string): { cleanText: string; charts: ChartData[] } {
  const charts: ChartData[] = []
  const cleanText = text.replace(CHART_PATTERN, (_, json) => {
    try {
      charts.push(JSON.parse(json) as ChartData)
    } catch {
      // silently skip malformed chart JSON
    }
    return ''
  }).trim()
  return { cleanText, charts }
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sport, setSport] = useState<Sport>(null)

  const sendMessage = useCallback(async (content: string) => {
    setError(null)

    const userMessage: Message = {
      id: uuidv4(),
      role: 'user',
      content,
      charts: [],
      isStreaming: false,
    }

    const assistantId = uuidv4()
    const assistantMessage: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      charts: [],
      isStreaming: true,
    }

    setMessages(prev => [...prev, userMessage, assistantMessage])
    setIsLoading(true)

    try {
      const history = messages.map(m => ({ role: m.role, content: m.content }))
      history.push({ role: 'user', content })

      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history, sport }),
      })

      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      if (!response.body) throw new Error('No response body')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let accumulated = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6)
          if (payload === '[DONE]') break

          try {
            const parsed = JSON.parse(payload)
            if (parsed.error) throw new Error(parsed.error)
            if (parsed.token) {
              accumulated += parsed.token
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId ? { ...m, content: accumulated } : m
                )
              )
            }
          } catch (e) {
            if (e instanceof Error && e.message !== 'Unexpected token') {
              throw e
            }
          }
        }
      }

      // Stream complete — extract charts from full text
      const { cleanText, charts } = extractCharts(accumulated)
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId
            ? { ...m, content: cleanText, charts, isStreaming: false }
            : m
        )
      )
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Something went wrong'
      setError(msg)
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId
            ? { ...m, content: 'Sorry, something went wrong. Please try again.', isStreaming: false }
            : m
        )
      )
    } finally {
      setIsLoading(false)
    }
  }, [messages, sport])

  const clearMessages = useCallback(() => {
    setMessages([])
    setError(null)
  }, [])

  return { messages, isLoading, error, sport, setSport, sendMessage, clearMessages }
}
