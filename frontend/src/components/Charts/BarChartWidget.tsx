import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import type { ChartData } from '../../types/chat'

const COLORS = ['#4f7ef8', '#f87c4f', '#4ff8a8', '#f84f6e', '#c44ff8', '#f8d24f']

const TOOLTIP_STYLE = {
  contentStyle: {
    background: '#1a1d27',
    border: '1px solid #2e3347',
    borderRadius: '8px',
    color: '#e8eaf6',
    fontSize: '13px',
  },
  labelStyle: { color: '#8b92b8', marginBottom: '4px', fontWeight: 600 },
  cursor: { fill: 'rgba(79, 126, 248, 0.08)' },
}

interface Props {
  chart: ChartData
}

export function BarChartWidget({ chart }: Props) {
  const { title, data, xKey, yKeys } = chart

  return (
    <div className="chart-widget">
      <p className="chart-title">{title}</p>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2e3347" vertical={false} />
          <XAxis
            dataKey={xKey}
            tick={{ fill: '#8b92b8', fontSize: 12 }}
            axisLine={{ stroke: '#2e3347' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: '#8b92b8', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={36}
          />
          <Tooltip {...TOOLTIP_STYLE} />
          {yKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 12, color: '#8b92b8' }} />}
          {yKeys.map((key, i) => (
            <Bar
              key={key}
              dataKey={key}
              fill={COLORS[i % COLORS.length]}
              radius={[4, 4, 0, 0]}
              maxBarSize={56}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
