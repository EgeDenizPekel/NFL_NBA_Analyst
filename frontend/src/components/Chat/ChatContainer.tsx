import type { Message } from '../../types/chat'
import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'

interface Props {
  messages: Message[]
  isLoading: boolean
  error: string | null
  onSend: (message: string) => void
}

export function ChatContainer({ messages, isLoading, error, onSend }: Props) {
  return (
    <div className="chat-container">
      <MessageList messages={messages} />
      {error && <div className="error-banner">{error}</div>}
      <ChatInput onSend={onSend} isLoading={isLoading} />
    </div>
  )
}
