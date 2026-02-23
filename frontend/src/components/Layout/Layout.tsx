import type { ReactNode } from 'react'
import { Header } from './Header'
import { Sidebar } from './Sidebar'
import type { Sport } from '../../types/chat'

interface Props {
  children: ReactNode
  onClear: () => void
  sport: Sport
  onSportChange: (sport: Sport) => void
  onPrompt: (text: string) => void
}

export function Layout({ children, onClear, sport, onSportChange, onPrompt }: Props) {
  return (
    <div className="layout">
      <Header onClear={onClear} />
      <main className="layout-main">
        <Sidebar sport={sport} onSportChange={onSportChange} onPrompt={onPrompt} />
        {children}
      </main>
    </div>
  )
}
