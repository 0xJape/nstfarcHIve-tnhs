import { useEffect, useState } from 'react'
import Plotly from 'plotly.js-dist-min'
import { api, type HistoricalRow, type Municipality, type SampleTrendRow } from './api'

const metrics: { key: keyof HistoricalRow; label: string }[] = [
  { key: 'REPORTED_HIV_CASES', label: 'Annual HIV cases' },
  { key: 'ROLLING_12M_CASES', label: 'Rolling 12-month cases' },
  { key: 'CASES_PER_100K', label: 'Average monthly cases per 100,000' },
  { key: 'SIX_MONTH_GROWTH_PCT', label: 'Average six-month growth (%)' },
  { key: 'ACTIVE_TESTING_CENTERS', label: 'Active testing centers' },
  { key: 'FACILITY_NEED_SCORE', label: 'Average facility-need score' },
]

export default function HistoricalTrends() {
  const [municipalities, setMunicipalities] = useState<Municipality[]>([])
  const [psgc, setPsgc] = useState('')
  const [rows, setRows] = useState<HistoricalRow[]>([])
  const [metric, setMetric] = useState<keyof HistoricalRow>('REPORTED_HIV_CASES')
  const [endYear, setEndYear] = useState(2024)
  const [group, setGroup] = useState<'AGE BRACKET' | 'GENDER'>('AGE BRACKET')
  const [sampleRows, setSampleRows] = useState<SampleTrendRow[]>([])
  useEffect(() => { api.municipalities().then(setMunicipalities).catch(() => undefined) }, [])
  useEffect(() => { api.historicalTrend(psgc).then((data) => { setRows(data); setEndYear(Number(data.at(-1)?.PERIOD ?? 2024)) }).catch(() => setRows([])) }, [psgc])
  useEffect(() => { api.hivSample(group, municipalities.find((item) => item.PSGC === psgc)?.LOCATION).then(setSampleRows).catch(() => setSampleRows([])) }, [group, psgc, municipalities])
  const visible = rows.filter((row) => Number(row.PERIOD) <= endYear)
  const selectedMetric = metrics.find((item) => item.key === metric) ?? metrics[0]
  return <section className="historical-trends">
    <header><div><p className="eyebrow">1998–2024 development series</p><h2>Municipality HIV trends</h2><p>Filter municipality and year to inspect annual changes.</p></div><div className="historical-filters"><label>Municipality<select value={psgc} onChange={(event) => setPsgc(event.target.value)}><option value="">Region XII</option>{municipalities.map((item) => <option key={item.PSGC} value={item.PSGC}>{item.LOCATION} · {item.PROVINCE}</option>)}</select></label><label>Metric<select value={String(metric)} onChange={(event) => setMetric(event.target.value as keyof HistoricalRow)}>{metrics.map((item) => <option key={String(item.key)} value={String(item.key)}>{item.label}</option>)}</select></label><label>Breakdown<select value={group} onChange={(event) => setGroup(event.target.value as typeof group)}><option value="AGE BRACKET">Age bracket</option><option value="GENDER">Gender</option></select></label></div></header>
    <div className="historical-year"><span>1998</span><input type="range" min="1998" max="2024" value={endYear} onChange={(event) => setEndYear(Number(event.target.value))} aria-label="Historical end year" /><strong>{endYear}</strong></div>
    <div className="historical-plot" ref={(node) => { if (node) void Plotly.react(node, [{ x: visible.map((row) => row.PERIOD), y: visible.map((row) => Number(row[metric]) || 0), type: 'scatter', mode: 'lines+markers', name: selectedMetric.label, line: { color: '#ff5a57', width: 3 }, fill: 'tozeroy', fillcolor: 'rgba(255,90,87,.12)' }], { paper_bgcolor: '#17191c', plot_bgcolor: '#17191c', font: { color: '#dce5e8' }, margin: { t: 20, r: 20, b: 45, l: 60 }, xaxis: { title: { text: 'Year' }, gridcolor: '#30363d' }, yaxis: { title: { text: selectedMetric.label }, gridcolor: '#30363d' } }, { responsive: true, displaylogo: false }) }} />
    <p className="historical-warning">Constrained development simulation based on regional totals. Not official municipality-level surveillance.</p>
    <div className="historical-plot" ref={(node) => { if (node) { const categories = [...new Set(sampleRows.map((row) => row.CATEGORY))]; void Plotly.react(node, categories.map((category) => ({ x: sampleRows.filter((row) => row.CATEGORY === category && Number(row.YEAR) <= endYear).map((row) => row.YEAR), y: sampleRows.filter((row) => row.CATEGORY === category && Number(row.YEAR) <= endYear).map((row) => row.CASES), type: 'bar', name: category })), { barmode: 'group', paper_bgcolor: '#17191c', plot_bgcolor: '#17191c', font: { color: '#dce5e8' }, margin: { t: 20, r: 20, b: 45, l: 60 }, xaxis: { title: { text: 'Year' }, gridcolor: '#30363d' }, yaxis: { title: { text: 'Sample records' }, gridcolor: '#30363d' } }, { responsive: true, displaylogo: false }) } }} />
  </section>
}