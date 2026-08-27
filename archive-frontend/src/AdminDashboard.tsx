import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Download, Layers3, MapPin, Pause, Play, Printer, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { AlertRow, Health, MunicipalityCompartments, MunicipalityDecomposition, MunicipalityGeometry, RankingRow, RegionSummaryRow, SnapshotRow } from './api'
import { api } from './api'
import MapView from './MapView'
import Plotly from 'plotly.js-dist-min'

type Props = {
  geometry: MunicipalityGeometry | null
  rows: SnapshotRow[]
  ranking: RankingRow[]
  alerts: AlertRow[]
  summary: RegionSummaryRow[]
  health: Health | null
  metric: keyof SnapshotRow
  selected: SnapshotRow | null
  onMetricChange: (metric: keyof SnapshotRow) => void
  periods: string[]
  currentPeriod: string
  onPeriodChange: (period: string) => void
  onSelect: (row: SnapshotRow | null) => void
}

const metricOptions: { value: keyof SnapshotRow; label: string }[] = [
  { value: 'TRANSMISSION_PRESSURE_INDEX', label: 'HIV risk' },
  { value: 'PREDICTED_CASES', label: 'Forecast cases' },
  { value: 'ROLLING_12M_CASES', label: '12-month cases heatmap' },
  { value: 'TESTING_CENTER_NEED_SCORE', label: 'Testing access need' },
]

function MunicipalityCharts({ rows, decomposition, compartments }: { rows: SnapshotRow[]; decomposition: MunicipalityDecomposition[]; compartments: MunicipalityCompartments[] }) {
  const plot = (id: string, title: string, traces: Plotly.Data[]) => <div className="plot-card"><h3>{title}</h3><div ref={(node) => { if (node) void Plotly.react(node, traces, { paper_bgcolor: '#202020', plot_bgcolor: '#202020', font: { color: '#dce5e8', size: 10 }, margin: { t: 12, r: 12, b: 38, l: 42 }, xaxis: { gridcolor: '#35424a' }, yaxis: { gridcolor: '#35424a' }, legend: { orientation: 'h', y: -0.22 } }, { responsive: true, displaylogo: false }) }} id={id} /></div>
  const recent = rows.slice(-18)
  const average = (key: keyof SnapshotRow) => rows.length ? rows.reduce((sum, row) => sum + (Number(row[key]) || 0), 0) / rows.length : 0
  const periods = recent.map((row) => row.PERIOD)
  return <section className="municipality-charts"><span className="charts-title">Existing model analytics · {rows.length} periods</span><div className="plot-grid">{plot('forecast-plot', 'Forecast and rolling cases', [{ x: periods, y: recent.map((row) => row.PREDICTED_CASES ?? 0), type: 'scatter', mode: 'lines+markers', name: 'Predicted cases', line: { color: '#ff5a57', width: 3 }, fill: 'tozeroy' }, { x: periods, y: recent.map((row) => row.ROLLING_12M_CASES ?? 0), type: 'scatter', mode: 'lines+markers', name: '12-month cases', line: { color: '#ffb347', width: 2 } }])}{plot('risk-plot', 'Transmission pressure', [{ x: periods, y: recent.map((row) => row.TRANSMISSION_PRESSURE_INDEX ?? 0), type: 'scatter', mode: 'lines+markers', name: 'Risk index', line: { color: '#b78cff', width: 3 } }])}{plot('scatter-plot', 'Case / risk scatter', [{ x: recent.map((row) => row.ROLLING_12M_CASES ?? 0), y: recent.map((row) => row.TRANSMISSION_PRESSURE_INDEX ?? 0), type: 'scatter', mode: 'markers', text: periods, marker: { size: 11, color: recent.map((row) => row.PREDICTED_CASES ?? 0), colorscale: 'Turbo', showscale: true } }])}{decomposition.length > 0 && plot('decomposition-plot', 'Time-series decomposition', ['TREND_COMPONENT', 'SEASONAL_COMPONENT', 'RESIDUAL_COMPONENT'].map((key, index) => ({ x: decomposition.slice(-18).map((row) => row.PERIOD), y: decomposition.slice(-18).map((row) => Number(row[key as keyof MunicipalityDecomposition]) || 0), type: 'scatter', mode: 'lines', name: key.replace('_COMPONENT', '').toLowerCase(), line: { color: ['#28b7a8', '#ffb347', '#ef476f'][index], width: 2 } })))}{compartments.length > 0 && plot('cascade-plot', 'Care cascade compartments', ['PLHIV_UNDIAGNOSED', 'PLHIV_DIAGNOSED_NOT_ON_ART', 'PLHIV_ON_ART_UNSUPPRESSED', 'PLHIV_VIRALLY_SUPPRESSED'].map((key, index) => ({ x: compartments.slice(-18).map((row) => row.PERIOD), y: compartments.slice(-18).map((row) => Number(row[key as keyof MunicipalityCompartments]) || 0), type: 'scatter', mode: 'lines', stackgroup: 'one', name: key.replace('PLHIV_', '').replaceAll('_', ' ').toLowerCase(), line: { color: ['#ef476f', '#ff9f1c', '#2ec4b6', '#4d8dff'][index] } })))}</div><div className="chart-stats"><span>Avg. cases <strong>{average('ROLLING_12M_CASES').toFixed(1)}</strong></span><span>Peak cases <strong>{Math.max(...rows.map((row) => Number(row.ROLLING_12M_CASES) || 0), 0).toFixed(0)}</strong></span><span>Avg. risk <strong>{average('TRANSMISSION_PRESSURE_INDEX').toFixed(1)}</strong></span></div></section>
}

export default function AdminDashboard({ geometry, rows, ranking, alerts, summary, health, metric, selected, periods, currentPeriod, onPeriodChange, onMetricChange, onSelect }: Props) {
  const highRisk = rows.filter((row) => Number(row.TRANSMISSION_PRESSURE_INDEX) >= 60).length
  const [playing, setPlaying] = useState(false)
  const timeline = Math.max(0, periods.indexOf(currentPeriod))
  const [side, setSide] = useState<'left' | 'right'>('left')
  const [leftMin, setLeftMin] = useState(false)
  const [rightMin, setRightMin] = useState(false)
  const [overlayMetrics, setOverlayMetrics] = useState<(keyof SnapshotRow)[]>([])
  const [showChoropleth, setShowChoropleth] = useState(true)
  const [showFacilities, setShowFacilities] = useState(true)
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailRows, setDetailRows] = useState<SnapshotRow[]>([])
  const [detailDecomposition, setDetailDecomposition] = useState<MunicipalityDecomposition[]>([])
  const [detailCompartments, setDetailCompartments] = useState<MunicipalityCompartments[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [search, setSearch] = useState('')
  const openDetail = async (row: SnapshotRow) => {
    setDetailLoading(true)
    setDetailOpen(true)
    try { const [timelineRows, decomposition, compartments] = await Promise.all([api.timeline(row.PSGC), api.decomposition(row.LOCATION), api.compartments(row.LOCATION)]); setDetailRows(timelineRows); setDetailDecomposition(decomposition); setDetailCompartments(compartments) } finally { setDetailLoading(false) }
  }
  const selectMapRow = (row?: SnapshotRow) => {
    if (!row) return
    if (selected?.PSGC === row.PSGC) { void openDetail(row); return }
    setDetailOpen(false); setDetailRows([]); setDetailDecomposition([]); setDetailCompartments([]); onSelect(row)
  }

  useEffect(() => {
    if (!playing) return
    const timer = window.setInterval(() => onPeriodChange(periods[(timeline + 1) % periods.length] ?? currentPeriod), 700)
    return () => window.clearInterval(timer)
  }, [playing, timeline, periods, currentPeriod, onPeriodChange])

  const movePeriod = (delta: number) => onPeriodChange(periods[Math.max(0, Math.min(periods.length - 1, timeline + delta))] ?? currentPeriod)
  const exportCsv = () => {
    const columns: (keyof SnapshotRow)[] = ['PERIOD', 'PSGC', 'PROVINCE', 'LOCATION', 'PREDICTED_CASES', 'ROLLING_12M_CASES', 'TRANSMISSION_PRESSURE_INDEX', 'HOTSPOT_CLASS', 'TESTING_CENTER_NEED_SCORE']
    const csv = [columns, ...rows.map((row) => columns.map((column) => row[column] ?? ''))]
      .map((record) => record.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(','))
      .join('\r\n')
    const link = document.createElement('a')
    link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    link.download = `archive-analytics-${currentPeriod || 'latest'}.csv`
    link.click()
    URL.revokeObjectURL(link.href)
  }

  return <section className={`control-v2 panels-${side} ${leftMin ? 'left-minimized' : ''} ${rightMin ? 'right-minimized' : ''}`}>
    <aside className="control-left">
      <div className="panel-actions"><button className="panel-toggle" onClick={() => setLeftMin((value) => !value)} aria-label={leftMin ? 'Expand left panel' : 'Minimize left panel'}>{leftMin ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}</button><button className="panel-toggle" onClick={() => setSide('right')} aria-label="Move panels right"><ChevronRight size={16} /></button></div>
      <div><p className="control-kicker">ARCHIVE Intelligence</p><h1>Region XII<br />HIV Risk Map</h1><p className="control-copy">Aggregate surveillance and MLR–LSTM planning scenarios.</p></div>
      <label className="control-select">Visualization layer<select value={String(metric)} onChange={(event) => onMetricChange(event.target.value as keyof SnapshotRow)}>{metricOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select><span className="layer-checklist-label">Map layers</span><label className="layer-check"><input type="checkbox" checked={showChoropleth} onChange={() => setShowChoropleth((value) => !value)} />Choropleth map</label><label className="layer-check"><input type="checkbox" checked={showFacilities} onChange={() => setShowFacilities((value) => !value)} />HIV center pins</label>{metricOptions.map((option) => <label className="layer-check" key={`overlay-${option.value}`}><input type="checkbox" checked={overlayMetrics.includes(option.value)} onChange={() => setOverlayMetrics((current) => current.includes(option.value) ? current.filter((item) => item !== option.value) : [...current, option.value])} />{option.label}</label>)}</label>
      <div className="control-scale"><span>Lower</span><i /><i /><i /><i /><i /><span>Higher</span></div>
      <div className="control-kpis"><article><span>Municipalities</span><strong>{rows.length || '—'}</strong></article><article><span>High risk areas</span><strong>{highRisk}</strong></article><article><span>Active alerts</span><strong>{alerts.length || '—'}</strong></article><article><span>Forecast periods</span><strong>{summary.length || '—'}</strong></article></div>
      <div className="analytics-actions"><button onClick={exportCsv} disabled={!rows.length}><Download size={15} />Export CSV</button><button onClick={() => window.print()}><Printer size={15} />Print / PDF</button></div>
      <div className="control-model"><span>{health?.database_available ? 'Live model' : 'Model offline'}</span><strong>MLR–LSTM + spatial analysis</strong><small>Planning support only. Not intended for diagnosis.</small></div>
    </aside>

    <main className="control-map">
      <div className="control-search"><Search size={16} /><input aria-label="Search municipality" placeholder="Search municipality" value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => { if (event.key !== 'Enter') return; const query = search.trim().toLowerCase(); const match = rows.find((row) => `${row.LOCATION} ${row.PROVINCE}`.toLowerCase().includes(query)); if (match) { onSelect(match); setSearch(match.LOCATION) } }} /><button type="button" aria-label="Find municipality" onClick={() => { const query = search.trim().toLowerCase(); const match = rows.find((row) => `${row.LOCATION} ${row.PROVINCE}`.toLowerCase().includes(query)); if (match) { onSelect(match); setSearch(match.LOCATION) } }}>Find</button></div>
      <button className="control-layers" onClick={() => { const index = metricOptions.findIndex((option) => option.value === metric); onMetricChange(metricOptions[(index + 1) % metricOptions.length].value) }} aria-label="Toggle map layer"><Layers3 size={16} /><span>{metricOptions.find((option) => option.value === metric)?.label ?? 'Map layer'}</span></button>
      {geometry && rows.length ? <MapView geometry={geometry} rows={rows} metric={metric} overlayMetrics={overlayMetrics} showChoropleth={showChoropleth} showFacilities={showFacilities} selectedPsgc={selected?.PSGC} onSelect={selectMapRow} /> : <div className="control-map-empty">Map data unavailable</div>}
      <div className="control-timeline"><button aria-label="Previous month" onClick={() => movePeriod(-1)}><ChevronLeft size={18} /></button><div><span>Model period {currentPeriod || '—'}</span><input type="range" min="0" max={Math.max(0, periods.length - 1)} value={timeline} onChange={(event) => onPeriodChange(periods[Number(event.target.value)] ?? currentPeriod)} aria-label="Forecast timeline" /></div><button aria-label={playing ? 'Pause timeline' : 'Play timeline'} onClick={() => setPlaying((value) => !value)}>{playing ? <Pause size={16} /> : <Play size={16} />}</button><button aria-label="Next month" onClick={() => movePeriod(1)}><ChevronRight size={18} /></button></div>
    </main>

    <aside className="control-right">
      <div className="panel-actions"><button className="panel-toggle" onClick={() => setRightMin((value) => !value)} aria-label={rightMin ? 'Expand right panel' : 'Minimize right panel'}>{rightMin ? <ChevronsLeft size={16} /> : <ChevronsRight size={16} />}</button><button className="panel-toggle" onClick={() => setSide('left')} aria-label="Move panels left"><ChevronLeft size={16} /></button></div>
      <p className="control-kicker">Selected municipality</p>
      {selected ? <><div className="control-place"><div><h2>{selected.LOCATION}</h2><p>{selected.PROVINCE}</p></div><span>{Number(selected.TRANSMISSION_PRESSURE_INDEX) >= 60 ? 'High priority' : 'Monitor'}</span></div><div className="control-details"><article><span>Risk score</span><strong>{selected.TRANSMISSION_PRESSURE_INDEX?.toFixed(2) ?? '—'}</strong></article><article><span>Predicted cases</span><strong>{selected.PREDICTED_CASES?.toFixed(2) ?? '—'}</strong></article><article><span>Rolling 12M cases</span><strong>{selected.ROLLING_12M_CASES?.toFixed(0) ?? '—'}</strong></article><article><span>Testing need</span><strong>{selected.TESTING_CENTER_NEED_SCORE?.toFixed(2) ?? '—'}</strong></article></div></> : <div className="control-unselected"><MapPin size={30} /><h2>Select municipality</h2><p>Click municipality once to zoom. Click again for statistical profile.</p></div>}
      <div className="control-ranking"><span>Top priorities</span>{ranking.slice(0, 4).map((row, index) => <div key={row.PSGC}><b>{index + 1}</b><p>{row.LOCATION}<small>{row.PROVINCE}</small></p><strong>{row.VALUE.toFixed(1)}</strong></div>)}</div>
    </aside>
    {detailOpen && <div className="analytics-modal-backdrop" onClick={() => setDetailOpen(false)}><section className="analytics-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}><button className="analytics-close" onClick={() => setDetailOpen(false)} aria-label="Close analytics">×</button><h2>{selected?.LOCATION} analytics</h2><p>{selected?.PROVINCE} · Existing model charts</p>{detailLoading ? <div className="detail-loader"><span />Loading municipality analytics…</div> : <MunicipalityCharts rows={detailRows} decomposition={detailDecomposition} compartments={detailCompartments} />}</section></div>}
  </section>
}
