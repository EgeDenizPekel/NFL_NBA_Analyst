import { useEffect, useRef } from 'react'
import type { Message } from '../../types/chat'
import { MessageBubble } from './MessageBubble'

interface Props {
  messages: Message[]
}


export function MessageList({ messages }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="message-list">
      {messages.length === 0 ? (
        <div className="welcome-message">
          <div className="welcome-icon">🏆</div>
          <ReactMarkdownWelcome />
        </div>
      ) : (
        messages.map(m => <MessageBubble key={m.id} message={m} />)
      )}
      <div ref={bottomRef} />
    </div>
  )
}

// Inline to avoid an extra file for a single static use
function ReactMarkdownWelcome() {
  return (
    <div className="welcome-text">
      <p>Ask me anything about the <strong>NBA</strong> or <strong>NFL</strong> — player stats, team standings, game previews, historical comparisons, and more.</p>
      <p className="welcome-hint">Try: <em>"How is Jayson Tatum playing this season?"</em> or <em>"Who are the top QBs in the NFL right now?"</em></p>
    </div>
  )
}
