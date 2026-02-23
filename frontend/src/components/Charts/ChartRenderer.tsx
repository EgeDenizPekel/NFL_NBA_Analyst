import type { ChartData } from '../../types/chat'
import { BarChartWidget } from './BarChartWidget'
import { LineChartWidget } from './LineChartWidget'
import { RadarChartWidget } from './RadarChartWidget'

interface Props {
  chart: ChartData
}

export function ChartRenderer({ chart }: Props) {
  switch (chart.type) {
    case 'bar':
      return <BarChartWidget chart={chart} />
    case 'line':
      return <LineChartWidget chart={chart} />
    case 'radar':
      return <RadarChartWidget chart={chart} />
    default:
      return null
  }
}
