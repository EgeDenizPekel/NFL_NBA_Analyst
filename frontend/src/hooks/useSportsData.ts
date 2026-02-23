import { useState, useEffect } from 'react'
import type { Sport } from '../types/chat'

interface SportsDataState {
  scoreboard: string | null
  isLoading: boolean
}

export function useSportsData(sport: Sport): SportsDataState {
  const [scoreboard, setScoreboard] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (!sport) {
      setScoreboard(null)
      return
    }

    let cancelled = false
    setIsLoading(true)
    setScoreboard(null)

    fetch(`/api/sports/${sport}/scoreboard`)
      .then(r => r.json())
      .then(json => {
        if (!cancelled) setScoreboard(json.data ?? null)
      })
      .catch(() => {
        if (!cancelled) setScoreboard(null)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => { cancelled = true }
  }, [sport])

  return { scoreboard, isLoading }
}
