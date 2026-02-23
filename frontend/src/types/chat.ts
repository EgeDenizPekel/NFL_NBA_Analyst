export type Sport = 'nba' | 'nfl' | null

export interface ChartData {
  type: 'bar' | 'line' | 'radar'
  title: string
  data: Record<string, unknown>[]
  xKey: string
  yKeys: string[]
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  charts: ChartData[]
  isStreaming: boolean
}
