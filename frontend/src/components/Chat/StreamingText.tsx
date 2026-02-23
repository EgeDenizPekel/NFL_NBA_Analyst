import { useEffect, useState } from 'react'

interface Props {
  text: string
  isStreaming: boolean
}

export function StreamingText({ text, isStreaming }: Props) {
  const [showCursor, setShowCursor] = useState(true)

  useEffect(() => {
    if (!isStreaming) return
    const interval = setInterval(() => setShowCursor(v => !v), 500)
    return () => clearInterval(interval)
  }, [isStreaming])

  return (
    <span>
      {text}
      {isStreaming && (
        <span className="streaming-cursor" style={{ opacity: showCursor ? 1 : 0 }}>▌</span>
      )}
    </span>
  )
}
