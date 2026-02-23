import { useChat } from './hooks/useChat'
import { Layout } from './components/Layout/Layout'
import { ChatContainer } from './components/Chat/ChatContainer'
import './index.css'

function App() {
  const { messages, isLoading, error, sport, setSport, sendMessage, clearMessages } = useChat()

  return (
    <Layout
      onClear={clearMessages}
      sport={sport}
      onSportChange={setSport}
      onPrompt={sendMessage}
    >
      <ChatContainer
        messages={messages}
        isLoading={isLoading}
        error={error}
        onSend={sendMessage}
      />
    </Layout>
  )
}

export default App
