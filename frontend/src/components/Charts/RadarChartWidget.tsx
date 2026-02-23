import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import type { ChartData } from '../../types/chat'

const COLORS = ['#4f7ef8', '#f87c4f', '#4ff8a8', '#f84f6e', '#c44ff8', '#f8d24f']

interface Props {
  chart: ChartData
}

/**
 * Pivots data from the LLM's player-row format to Recharts' stat-row format,
 * then normalises each stat to 0–100 so wildly different magnitudes (28 PPG
 * vs 0.6 BPG) still produce a meaningful shape on the chart.
 *
 * Input (from LLM):
 *   data    = [{name:"LeBron", pts:28, reb:7, ast:8}, {name:"Curry", pts:26, reb:5, ast:7}]
 *   xKey    = "name"
 *   yKeys   = ["pts", "reb", "ast"]
 *
 * Recharts needs:
 *   [{stat:"pts", LeBron:100, Curry:93}, {stat:"reb", LeBron:100, Curry:71}, ...]
 */
function pivotAndNormalize(
  data: Record<string, unknown>[],
  xKey: string,
  yKeys: string[],
): { radarData: Record<string, unknown>[]; playerNames: string[] } {
  const playerNames = data.map(d => String(d[xKey]))

  const radarData = yKeys.map(stat => {
    const rawValues = data.map(d => Number(d[stat]) || 0)
    const maxVal = Math.max(...rawValues)

    const entry: Record<string, unknown> = { stat }
    playerNames.forEach((name, i) => {
      entry[name] = maxVal > 0 ? Math.round((rawValues[i] / maxVal) * 100) : 0
    })
    return entry
  })

  return { radarData, playerNames }
}

/** Custom tooltip that restores the original (un-normalised) values. */
function CustomTooltip({
  active,
  payload,
  label,
  originalData,
  xKey,
}: {
  active?: boolean
  payload?: { name: string; value: number; color: string }[]
  label?: string
  originalData: Record<string, unknown>[]
  xKey: string
}) {
  if (!active || !payload?.length) return null

  const stat = label as string
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-label">{stat}</p>
      {payload.map(entry => {
        const playerRow = originalData.find(d => String(d[xKey]) === entry.name)
        const rawVal = playerRow ? playerRow[stat] : '?'
        return (
          <p key={entry.name} style={{ color: entry.color }}>
            {entry.name}: {String(rawVal)}
          </p>
        )
      })}
    </div>
  )
}

export function RadarChartWidget({ chart }: Props) {
  const { title, data, xKey, yKeys } = chart
  const { radarData, playerNames } = pivotAndNormalize(data, xKey, yKeys)

  return (
    <div className="chart-widget">
      <p className="chart-title">{title}</p>
      <ResponsiveContainer width="100%" height={300}>
        <RadarChart data={radarData} margin={{ top: 8, right: 32, left: 32, bottom: 8 }}>
          <PolarGrid stroke="#2e3347" />
          <PolarAngleAxis
            dataKey="stat"
            tick={{ fill: '#8b92b8', fontSize: 12 }}
          />
          <Tooltip
            content={
              <CustomTooltip originalData={data} xKey={xKey} />
            }
          />
          <Legend wrapperStyle={{ fontSize: 12, color: '#8b92b8' }} />
          {playerNames.map((name, i) => (
            <Radar
              key={name}
              name={name}
              dataKey={name}
              stroke={COLORS[i % COLORS.length]}
              fill={COLORS[i % COLORS.length]}
              fillOpacity={0.15}
              strokeWidth={2}
            />
          ))}
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
