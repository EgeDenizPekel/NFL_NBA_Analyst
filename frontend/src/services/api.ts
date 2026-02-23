import type { Sport } from '../types/chat'

export async function fetchScoreboard(sport: NonNullable<Sport>) {
  const res = await fetch(`/api/sports/${sport}/scoreboard`)
  if (!res.ok) throw new Error(`Failed to fetch ${sport} scoreboard`)
  return res.json()
}

export async function fetchStandings(sport: NonNullable<Sport>) {
  const res = await fetch(`/api/sports/${sport}/standings`)
  if (!res.ok) throw new Error(`Failed to fetch ${sport} standings`)
  return res.json()
}
