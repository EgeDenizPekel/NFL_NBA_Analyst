import ReactMarkdown from 'react-markdown'
import type { Message } from '../../types/chat'
import { StreamingText } from './StreamingText'
import { ChartRenderer } from '../Charts/ChartRenderer'

interface Props {
  message: Message
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'

  return (
    <div className={`message-bubble ${isUser ? 'message-user' : 'message-assistant'}`}>
      <div className="message-role">{isUser ? 'You' : 'Analyst'}</div>
      <div className="message-content">
        {isUser ? (
          <p>{message.content}</p>
        ) : message.isStreaming && message.content === '' ? (
          <span className="loading-dots">
            <span /><span /><span />
          </span>
        ) : message.isStreaming ? (
          <StreamingText text={message.content} isStreaming={message.isStreaming} />
        ) : (
          <ReactMarkdown>{message.content}</ReactMarkdown>
        )}
      </div>
      {message.charts.length > 0 && (
        <div className="message-charts">
          {message.charts.map((chart, i) => (
            <ChartRenderer key={i} chart={chart} />
          ))}
        </div>
      )}
    </div>
  )
}
