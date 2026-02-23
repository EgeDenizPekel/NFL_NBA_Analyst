export interface PlayerStats {
  name: string
  team: string
  position: string
  stats: Record<string, number | string>
}

export interface TeamInfo {
  name: string
  abbreviation: string
  wins: number
  losses: number
  sport: 'nba' | 'nfl'
}

export interface GamePreview {
  homeTeam: string
  awayTeam: string
  date: string
  time: string
  sport: 'nba' | 'nfl'
  status: 'scheduled' | 'in_progress' | 'final'
  homeScore?: number
  awayScore?: number
}
