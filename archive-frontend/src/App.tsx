import { useEffect, useRef, useState } from 'react'
import { Activity, ArrowRight, BookOpen, Database, HeartHandshake, Map, Menu, MessageCircle, ShieldCheck, Volume2, Users, X } from 'lucide-react'
import { api, type AlertRow, type Health, type Metadata, type MunicipalityGeometry, type RankingRow, type RegionSummaryRow, type SnapshotRow } from './api'
import Intro from './Intro'
import MapView from './MapView'
import AdminDashboard from './AdminDashboard'
import AdminPatients from './AdminPatients'
import PreRegistration from './PreRegistration'
import ModelPage from './ModelPage'
import HistoricalTrends from './HistoricalTrends'
import ModelAnalytics from './ModelAnalytics'
import './App.css'
import './care-dialog.css'

type View = 'intro' | 'home' | 'map' | 'education' | 'model' | 'care' | 'about' | 'confirm' | 'control' | 'analytics' | 'patients'
type HistoryPoint = { period: string; cases: number; reported: number; pressure: number }
const paths: Record<View, string> = { intro: '/', home: '/home', map: '/map', education: '/education', model: '/model', care: '/care', about: '/about', confirm: '/confirm', control: '/control', analytics: '/control/analytics', patients: '/control/patients' }
const viewFromPath = (): View => (Object.entries(paths).find(([, path]) => path === location.pathname)?.[0] as View | undefined) ?? 'intro'

const publicNav: { id: View; label: string }[] = [
  { id: 'home', label: 'Home' },
  { id: 'education', label: 'Education' },
  { id: 'model', label: 'How model works' },
  { id: 'about', label: 'About' },
]

function ChatGuide({ onFindCare }: { onFindCare: () => void }) {
  const [open, setOpen] = useState(false); const [input, setInput] = useState(''); const [messages, setMessages] = useState<{ role: 'user' | 'assistant'; content: string }[]>([{ role: 'assistant', content: 'I can guide you through HIV testing and ARCHIVE care navigation.\n\n• Learn where to test\n• Understand private registration\n• Review what happens after submission\n\nWhat would help right now?' }]); const [busy, setBusy] = useState(false)
  const send = async (event: React.FormEvent) => { event.preventDefault(); const message = input.trim(); if (!message || busy) return; const next = [...messages, { role: 'user' as const, content: message }]; setMessages(next); setInput(''); setBusy(true); try { const result = await api.chat(message, messages); setMessages([...next, { role: 'assistant', content: result.reply }]) } catch { setMessages([...next, { role: 'assistant', content: 'Chat is unavailable right now. You can still use Find care to submit a private request or visit a verified testing center.' }]) } finally { setBusy(false) } }
  const speak = async (text: string) => { try { const source = await api.tts(text); const audio = new Audio(source); audio.onended = () => URL.revokeObjectURL(source); await audio.play() } catch { if ('speechSynthesis' in window) { speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance(text)) } } }
  useEffect(() => { const latest = messages.at(-1); if (messages.length > 1 && latest?.role === 'assistant' && !latest.content.startsWith('Chat is unavailable')) void speak(latest.content) }, [messages])
  const quickPrompts = ['Find HIV testing', 'How registration works', 'Privacy and consent', 'After I submit']
  const ask = (prompt: string) => setInput(prompt)
  return <aside className={`chat-guide ${open ? 'open' : ''}`}><button className="chat-toggle" onClick={() => setOpen(!open)} aria-expanded={open}><MessageCircle size={19} /> Ask ARCHIVE</button>{open && <div className="chat-panel"><header className="chat-header"><div><p className="eyebrow">Private HIV navigation</p><h2>ARCHIVE Care Guide</h2></div><div className="chat-header-actions"><span className="chat-online">● Ready</span><button type="button" className="chat-minimize" onClick={() => setOpen(false)} aria-label="Minimize ARCHIVE Care Guide"><X size={17} /></button></div></header><p className="chat-disclaimer">Guidance, not diagnosis. Avoid sharing personal or medical details.</p><div className="chat-messages" aria-live="polite">{messages.map((item, index) => <div className={`chat-message ${item.role}`} key={`${item.role}-${index}`}><span>{item.content}</span>{item.role === 'assistant' && <button onClick={() => void speak(item.content)} aria-label="Read response aloud"><Volume2 size={15} /></button>}</div>)}{busy && <p className="chat-thinking"><span /><span /><span /> ARCHIVE is checking guidance</p>}</div><div className="chat-quick-actions" aria-label="Suggested questions">{quickPrompts.map((prompt) => <button key={prompt} onClick={() => ask(prompt)}>{prompt}</button>)}</div><button className="chat-care-action" type="button" onClick={onFindCare}>Open private care registration <ArrowRight size={14} /></button><form onSubmit={send}><input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask about HIV testing or ARCHIVE…" maxLength={2000} aria-label="Message ARCHIVE Care Guide" /><button className="home-primary" disabled={busy || !input.trim()}>Send</button></form></div>}</aside>
}

function ConfirmReferral() {
  const query = new URLSearchParams(location.search); const reference = query.get('reference') ?? ''; const token = query.get('token') ?? ''
  const [state, setState] = useState<'ready' | 'sending' | 'done' | 'error'>(reference && token ? 'ready' : 'error')
  const confirm = async () => { setState('sending'); try { await api.confirmPreRegistration(reference, token); setState('done') } catch { setState('error') } }
  return <main className="confirmation-shell"><section className="confirmation-modal" aria-live="polite"><div className="confirmation-mark"><ShieldCheck size={30} /></div><p className="eyebrow">Private care referral</p>{state === 'done' ? <><h1>Referral confirmed.</h1><p className="confirmation-lead">You took an important step. Your selected HIV center can now contact you to help book an appointment.</p><div className="confirmation-reassurance"><HeartHandshake size={22} /><span><strong>We are here for you.</strong> You are not alone. Take things at your own pace; ARCHIVE will help connect you with care.</span></div><p className="confirmation-note">No diagnosis or HIV status is included in this referral. The center now handles follow-up and care coordination.</p></> : <><h1>Confirm your referral</h1><p className="confirmation-lead">Allow your selected HIV center to contact you using details you submitted through ARCHIVE.</p><div className="confirmation-choice"><ShieldCheck size={19} /><span><strong>Private and optional</strong>You control this step. Nothing is forwarded until you continue.</span></div>{state === 'error' && <p className="login-error">This confirmation link is invalid, expired, or already used.</p>}<button className="home-primary confirmation-button" disabled={state !== 'ready'} onClick={() => void confirm()}>{state === 'sending' ? 'Confirming…' : 'Yes, connect me with care'} <ArrowRight size={16} /></button><p className="confirmation-note">If you do not wish to continue, close this page. We respect your choice.</p></>}</section></main>
}

function App() {
  const welcomeDialog = useRef<HTMLDialogElement>(null)
  const loginDialog = useRef<HTMLDialogElement>(null)
  const [view, setView] = useState<View>(viewFromPath)
  const [rows, setRows] = useState<SnapshotRow[]>([])
  const [periods, setPeriods] = useState<string[]>([])
  const [currentPeriod, setCurrentPeriod] = useState('')
  const [health, setHealth] = useState<Health | null>(null)
  const [metadata, setMetadata] = useState<Metadata | null>(null)
  const [summary, setSummary] = useState<RegionSummaryRow[]>([])
  const [alerts, setAlerts] = useState<AlertRow[]>([])
  const [ranking, setRanking] = useState<RankingRow[]>([])
  const [geometry, setGeometry] = useState<MunicipalityGeometry | null>(null)
  const [metric, setMetric] = useState<keyof SnapshotRow>('ROLLING_12M_CASES')
  const [selectedMunicipality, setSelectedMunicipality] = useState<SnapshotRow | null>(null)
  const [history, setHistory] = useState<HistoryPoint[]>([])
  const [menuOpen, setMenuOpen] = useState(false)
  const [careKey, setCareKey] = useState(0)
  const [careOpen, setCareOpen] = useState(false)
  const [loggedIn, setLoggedIn] = useState(() => Boolean(sessionStorage.getItem('archive-auth-token')))
  const [loginError, setLoginError] = useState('')
  const [dataLoading, setDataLoading] = useState(true)
  const openCare = () => { setCareKey((key) => key + 1); setCareOpen(true) }

  useEffect(() => {
    const onPopState = () => setView(viewFromPath())
    addEventListener('popstate', onPopState)
    Promise.all([api.health(), api.dates(), api.geometry(), api.historicalTrend()])
      .then(async ([nextHealth, dates, nextGeometry, historical]) => {
        setHealth(nextHealth)
        setGeometry(nextGeometry)
        const nextPeriods = dates.map((date) => date.PERIOD)
        setPeriods(nextPeriods)
        const latest = nextPeriods.at(-1) ?? ''
        setCurrentPeriod(latest)
        setHistory(historical.map((point) => ({ period: point.PERIOD, cases: Number(point.REPORTED_HIV_CASES ?? 0), reported: Number(point.REPORTED_HIV_CASES ?? 0), pressure: 0 })))
        if (latest) {
          const [nextRows, nextRanking] = await Promise.all([api.snapshot(latest), api.ranking(latest, String(metric))])
          setRows(nextRows); setRanking(nextRanking)
        }
      })
      .then(() => setDataLoading(false))
        .catch(() => {
          setDataLoading(false);
        })
    return () => removeEventListener('popstate', onPopState)
  }, [])

  useEffect(() => {
    if (!currentPeriod) return
    Promise.all([api.snapshot(currentPeriod), api.ranking(currentPeriod, String(metric))])
      .then(([nextRows, nextRanking]) => { setRows(nextRows); setRanking(nextRanking); setSelectedMunicipality(null) })
      .catch(() => undefined)
      .finally(() => setDataLoading(false))
  }, [currentPeriod, metric])

  useEffect(() => {
    if (!loggedIn || (view !== 'control' && view !== 'analytics' && view !== 'patients')) return
    Promise.all([api.metadata(), api.regionSummary(), api.alerts()]).then(([nextMetadata, nextSummary, nextAlerts]) => { setMetadata(nextMetadata); setSummary(nextSummary); setAlerts(nextAlerts) }).catch(() => { sessionStorage.removeItem('archive-auth-token'); setLoggedIn(false) })
  }, [loggedIn, view])

  useEffect(() => {
    if ((view === 'control' || view === 'analytics' || view === 'patients') && !loggedIn) {
      globalThis.history.replaceState(null, '', paths.home)
      setView('home')
      loginDialog.current?.showModal()
    }
  }, [loggedIn, view])

  useEffect(() => {
    if (view === 'home' && !sessionStorage.getItem('archive-welcome-seen')) welcomeDialog.current?.showModal()
  }, [view])

  const closeWelcome = () => {
    sessionStorage.setItem('archive-welcome-seen', 'true')
    welcomeDialog.current?.close()
  }

  const login = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    try { await api.login(String(form.get('username')), String(form.get('password'))); setLoggedIn(true); setLoginError(''); loginDialog.current?.close(); navigate('control') } catch { setLoginError('Invalid username or password') }
  }

  const logout = () => {
    sessionStorage.removeItem('archive-auth-token')
    setLoggedIn(false)
    navigate('home')
  }

  const navigate = (next: View) => {
    if (view !== next) globalThis.history.pushState(null, '', paths[next])
    setView(next)
    setMenuOpen(false)
    scrollTo({ top: 0, behavior: 'smooth' })
  }

  const actualHistory = history.filter((point) => Number(point.period) <= 2026)
  const last = actualHistory.at(-1)
  const previous = actualHistory.at(-2) ?? last
  const yearlyChange = last && previous ? last.cases - previous.cases : 0
  const reportedSince1998 = history.reduce((sum, point) => sum + point.cases, 0)
  const projectedHistory: HistoryPoint[] = last ? [1, 2, 3, 4].map((offset) => ({ period: String(Number(last.period) + offset), cases: Math.max(0, last.cases + yearlyChange * offset), reported: 0, pressure: last.pressure })) : []
  const chartHistory = [...actualHistory, ...projectedHistory]

  if (view === 'intro') return <Intro onEnter={() => navigate('home')} />

  return (
    <div className="app-shell">
      {!loggedIn && <ChatGuide onFindCare={openCare} />}
      {dataLoading && <div className="data-loading" role="status" aria-live="polite"><div className="data-loading-card"><div className="loading-spinner" aria-hidden="true" /><strong>Loading regional data</strong><p>Preparing current municipality information and public-health trends.</p><small>This may take a few seconds. No personal HIV status is collected.</small></div></div>}
      <header className="site-header">
        <button className="brand" onClick={() => navigate('home')} aria-label="ARCHIVE home">
          <span className="ribbon" aria-hidden="true">🎗</span>
          <span>arc<span>HIV</span>e</span>
        </button>
        <button className="menu-toggle" onClick={() => setMenuOpen((open) => !open)} aria-expanded={menuOpen} aria-controls="main-navigation" aria-label="Toggle navigation">
          {menuOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
        </button>
        <nav id="main-navigation" className={menuOpen ? 'open' : ''} aria-label="Main navigation">
          {!loggedIn && publicNav.map((item) => (
            <button key={item.id} className={view === item.id ? 'active' : ''} aria-current={view === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}>{item.label}</button>
          ))}
          {loggedIn && <button className={view === 'control' ? 'active' : ''} onClick={() => navigate('control')}>Data Center</button>}
          {loggedIn && <button className={view === 'analytics' ? 'active' : ''} onClick={() => navigate('analytics')}>Analytics</button>}
          {loggedIn && <button className={view === 'patients' ? 'active' : ''} onClick={() => navigate('patients')}>Patients</button>}
          {!loggedIn && <button className="login-link" onClick={() => loginDialog.current?.showModal()}>Log in</button>}
          {loggedIn ? <button className="login-link" onClick={logout}>Log out</button> : <button className="header-care" onClick={openCare}>Find care <ArrowRight size={15} aria-hidden="true" /></button>}
        </nav>
      </header>

      <main>
        {view === 'confirm' && <ConfirmReferral />}
        {view === 'model' && <ModelPage />}
        {view === 'control' && <AdminDashboard geometry={geometry} rows={rows} ranking={ranking} alerts={alerts} summary={summary} health={health} metric={metric} selected={selectedMunicipality} periods={periods} currentPeriod={currentPeriod} onPeriodChange={setCurrentPeriod} onMetricChange={setMetric} onSelect={setSelectedMunicipality} />}
        {view === 'control' && <HistoricalTrends />}
        {view === 'analytics' && <ModelAnalytics />}
        {view === 'patients' && <AdminPatients />}
        {view === 'control' && <section className="admin-command-center"><aside className="intelligence-panel"><strong>ARCHIVE Intelligence</strong><p>HIV surveillance and MLR–LSTM forecasting.</p><label>Visualization<select value={String(metric)} onChange={(event) => setMetric(event.target.value as keyof SnapshotRow)}><option value="TRANSMISSION_PRESSURE_INDEX">HIV risk</option><option value="PREDICTED_CASES">Predicted cases</option><option value="TESTING_CENTER_NEED_SCORE">Care need</option></select></label><div className="intelligence-kpis"><span>Municipalities<strong>{rows.length || '—'}</strong></span><span>High-risk areas<strong>{rows.filter((row) => Number(row.TRANSMISSION_PRESSURE_INDEX) >= 60).length}</strong></span><span>Alerts<strong>{alerts.length || '—'}</strong></span><span>Forecast periods<strong>{summary.length || '—'}</strong></span></div><small>Aggregate planning scenarios. Not intended for diagnosis.</small></aside><div className="admin-command-map"><div className="admin-command-toolbar"><div><span className="eyebrow">Administrator GIS workspace</span><h1>Region XII Risk Intelligence</h1></div><label className="field">Time period<select><option>Latest available</option></select></label></div>{geometry && rows.length ? <MapView geometry={geometry} rows={rows} metric={metric} onSelect={(row) => setSelectedMunicipality(row ?? null)} /> : <div className="map-placeholder"><p>Start analytics API to load municipality geometry.</p></div>}</div><aside className="admin-ai-panel"><span className="eyebrow">Selected municipality</span>{selectedMunicipality ? <><h2>{selectedMunicipality.LOCATION}</h2><p>{selectedMunicipality.PROVINCE}</p><dl className="municipality-stats"><div><dt>Risk score</dt><dd>{selectedMunicipality.TRANSMISSION_PRESSURE_INDEX?.toFixed(2) ?? '—'}</dd></div><div><dt>Predicted cases</dt><dd>{selectedMunicipality.PREDICTED_CASES?.toFixed(2) ?? '—'}</dd></div><div><dt>Hotspot</dt><dd>{selectedMunicipality.HOTSPOT_CLASS || 'No classification'}</dd></div><div><dt>Testing need</dt><dd>{selectedMunicipality.TESTING_CENTER_NEED_SCORE?.toFixed(2) ?? '—'}</dd></div></dl><div className="ai-recommendation"><span>Planning signal</span><strong>Review testing access and surveillance trend for this municipality.</strong></div></> : <><h2>Select a municipality</h2><p>Click any municipality on map to view its HIV intelligence profile.</p></>}<small>Latest aggregate model run. Not a diagnosis.</small></aside><div className="admin-bottom-cards"><article><span>Municipality rankings</span><strong>{ranking.length || '—'}</strong><small>priority signals</small></article><article><span>Recent alerts</span><strong>{alerts.length || '—'}</strong><small>model-generated</small></article><article><span>Recent reports</span><strong>1</strong><small>latest valid run</small></article><article><span>Recent data uploads</span><strong>1</strong><small>aggregate source</small></article></div></section>}
        {view === 'control' && <><aside className="admin-side-nav admin-side-nav-left"><strong>ARCHIVE</strong><button className="active">Map overview</button><button onClick={() => document.querySelector('.data-center-grid')?.scrollIntoView({ behavior: 'smooth' })}>Analytics</button><button onClick={() => document.querySelector('.alert-list')?.scrollIntoView({ behavior: 'smooth' })}>Alerts</button></aside><aside className="admin-side-nav admin-side-nav-right"><span>MAP LAYERS</span><label><input type="checkbox" defaultChecked /> Municipalities</label><label><input type="checkbox" defaultChecked /> Risk surface</label><label><input type="checkbox" /> Testing centers</label><button onClick={() => setMetric('TRANSMISSION_PRESSURE_INDEX')}>Pressure</button><button onClick={() => setMetric('PREDICTED_CASES')}>Forecast</button><button onClick={() => setMetric('TESTING_CENTER_NEED_SCORE')}>Care need</button></aside></>}
        {view === 'control' && <section className="admin-map-panel"><div className="admin-map-heading"><div><p className="eyebrow">Administrator GIS workspace</p><h2>Region XII surveillance map</h2><p>Aggregate municipality analytics for planning. Forecast scenarios are not diagnoses.</p></div><label className="field">Map metric<select value={String(metric)} onChange={(event) => setMetric(event.target.value as keyof SnapshotRow)}><option value="TRANSMISSION_PRESSURE_INDEX">Transmission pressure</option><option value="PREDICTED_CASES">Predicted cases</option><option value="TESTING_CENTER_NEED_SCORE">Testing-center need</option></select></label></div>{geometry && rows.length ? <MapView geometry={geometry} rows={rows} metric={metric} /> : <div className="map-placeholder"><p>Start analytics API to load municipality geometry.</p></div>}</section>}
          {careOpen && <div className="care-dialog-overlay" role="presentation"><section className="care-dialog" role="dialog" aria-modal="true" aria-label="Care registration"><PreRegistration key={careKey} onClose={() => setCareOpen(false)} /></section></div>}
        <dialog ref={loginDialog} className="login-dialog"><button className="welcome-close" onClick={() => loginDialog.current?.close()} aria-label="Close login"><X size={20} /></button><p className="eyebrow">Protected workspace</p><h2>Log in to Data Center</h2><form onSubmit={login}><label>Username<input name="username" autoComplete="username" required /></label><label>Password<input name="password" type="password" autoComplete="current-password" required /></label>{loginError && <p className="login-error">{loginError}</p>}<button className="home-primary" type="submit">Log in <ArrowRight size={17} /></button></form></dialog>
        {view === 'home' && <>
          <dialog ref={welcomeDialog} className="welcome-dialog" aria-labelledby="welcome-title" onCancel={closeWelcome}>
            <button className="welcome-close" onClick={closeWelcome} aria-label="Close welcome message"><X aria-hidden="true" size={20} /></button>
            <p className="welcome-eyebrow">A private place to begin</p>
            <h2 id="welcome-title">We are here for you.<br /><span>Do you need help?</span></h2>
            <p className="welcome-lead">Take your time. ARCHIVE can guide you toward clear information, regional resources, and care-planning options without asking about your HIV status.</p>
            <div className="welcome-privacy">
              <ShieldCheck aria-hidden="true" />
              <div><strong>Your privacy matters</strong><p>No personal health response is collected, sent, or stored. This browser keeps only a temporary note that you closed this message.</p></div>
            </div>
            <ol className="welcome-steps">
              <li><span>1</span><p><strong>Choose privately</strong>Tell us only what kind of resource you want.</p></li>
              <li><span>2</span><p><strong>Explore discreetly</strong>Browse public information without an account.</p></li>
              <li><span>3</span><p><strong>Decide for yourself</strong>You control what to open and when to leave.</p></li>
            </ol>
            <div className="welcome-actions">
              <button className="home-primary" onClick={closeWelcome}>Continue privately <ArrowRight size={17} aria-hidden="true" /></button>
              <button className="welcome-secondary" onClick={closeWelcome}>Not now</button>
            </div>
          </dialog>
          <section className="home-hero">
            <div className="home-shader" aria-hidden="true" />
            <div className="home-hero-copy">
              <p className="home-pill"><span /> Private, supportive, stigma-free</p>
              <h1>Start with what<br /><span>you need today.</span></h1>
              <p>Clear HIV information, regional insights, and care-planning resources for people across Region XII. No judgment. No personal data required.</p>
              <div className="home-actions">
                <button className="home-primary" onClick={openCare}>Find care options <ArrowRight size={18} aria-hidden="true" /></button>
                <button className="home-secondary" onClick={() => navigate('education')}>Learn about HIV</button>
              </div>
            </div>
            <aside className="home-start" aria-labelledby="start-title">
              <p>Not sure where to begin?</p>
              <h2 id="start-title">Choose what feels right.</h2>
              <button onClick={() => navigate('education')}><span>01</span><strong>I want clear, reliable HIV information</strong><ArrowRight size={17} /></button>
              <button onClick={() => navigate('care')}><span>02</span><strong>I want to explore care access</strong><ArrowRight size={17} /></button>
              <button onClick={() => navigate('map')}><span>03</span><strong>I want to understand my region</strong><ArrowRight size={17} /></button>
              <small>No sign-in required. ARCHIVE does not ask for your HIV status.</small>
            </aside>
          </section>

          <section className="home-guide" aria-labelledby="guide-title">
            <p className="eyebrow">Choose your next step</p>
            <h2 id="guide-title">Resources, without the guesswork.</h2>
            <div className="guide-grid">
              <article><span className="guide-icon"><HeartHandshake aria-hidden="true" /></span><small>Need support</small><h3>Find care options</h3><p>See where expanded testing access may be most needed across Region XII.</p><button onClick={openCare}>Start private registration <ArrowRight size={16} /></button></article>
              <article><span className="guide-icon"><BookOpen aria-hidden="true" /></span><small>Get informed</small><h3>Understand HIV</h3><p>Learn about testing, prevention, PrEP, PEP, treatment, and U=U.</p><button onClick={() => navigate('education')}>Start learning <ArrowRight size={16} /></button></article>
              <article><span className="guide-icon"><Map aria-hidden="true" /></span><small>Explore the region</small><h3>View public insights</h3><p>Explore aggregate municipality-level planning scenarios—never individual status.</p><button onClick={() => navigate('map')}>Open risk map <ArrowRight size={16} /></button></article>
            </div>
          </section>

          <section className="home-map-section" aria-labelledby="home-map-title">
            <div className="home-map-heading"><div><p className="eyebrow">Public regional view</p><h2 id="home-map-title">See Region XII at a glance.</h2><p>Explore aggregate planning scenarios by municipality. These values support public-health planning; they do not identify individual people or confirm diagnoses.</p></div><button onClick={() => navigate('map')}>Open full map <ArrowRight size={16} /></button></div>
            {geometry && rows.length ? <MapView geometry={geometry} rows={rows} metric={metric} /> : <div className="home-map-empty">Regional map data will appear when the analytics service is available.</div>}
          </section>

          <section className="home-insights" aria-labelledby="home-insights-title">
            <div className="home-insights-heading"><div><p className="eyebrow">Region XII public health view</p><h2 id="home-insights-title">What the latest data is telling us.</h2><p>Explore model-derived regional signals across municipalities. Values show planning estimates, not confirmed diagnoses or named people.</p></div><span className="home-data-badge"><Activity size={15} /> {currentPeriod || 'Latest available'}</span></div>
            <div className="home-kpis"><article><Users size={20} /><strong>{rows.reduce((sum, row) => sum + Number(row.ROLLING_12M_CASES || 0), 0).toFixed(0)}</strong><span>modeled recent cases</span></article><article><Activity size={20} /><strong>{reportedSince1998.toFixed(0)}</strong><span>reported aggregate cases, 1998–2024</span></article><article><Map size={20} /><strong>{rows.length || '—'}</strong><span>municipalities monitored</span></article></div>
            <div className="home-history-card"><small>Historical Region XII record · 1998–2026</small><h3>How HIV signals changed through the years</h3><svg className="home-history-chart" viewBox="0 0 900 260" role="img" aria-label="Historical aggregate HIV trend with dotted projection"><path d="M40 220H870M40 20V220" />{chartHistory.length > 1 && (() => { const max = Math.max(...chartHistory.map((item) => item.cases), 1); const point = (item: HistoryPoint, index: number) => `${40 + index * (830 / Math.max(chartHistory.length - 1, 1))},${220 - (item.cases / max) * 180}`; const actualPoints = actualHistory.map((item, index) => point(item, index)).join(' '); const projectionPoints = [actualHistory.at(-1), ...projectedHistory].filter(Boolean).map((item) => point(item as HistoryPoint, chartHistory.indexOf(item as HistoryPoint))).join(' '); return <><polyline className="home-history-actual" points={actualPoints} /><polyline className="home-history-projection" points={projectionPoints} />{chartHistory.map((item, index) => { const [x, y] = point(item, index).split(','); return <text className="home-history-value" key={`${item.period}-value`} x={x} y={Math.max(15, Number(y) - 9)} textAnchor="middle">{item.cases.toFixed(0)}</text> })}</> })()}<g>{chartHistory.filter((_, index) => index === 0 || index === chartHistory.length - 1 || index % Math.max(1, Math.floor(chartHistory.length / 5)) === 0).map((point) => { const index = chartHistory.indexOf(point); return <text key={point.period} x={40 + index * (830 / Math.max(chartHistory.length - 1, 1))} y="247" textAnchor="middle">{point.period}</text> })}</g></svg><p className="home-chart-note">Solid line: historical records. Dotted line: directional projection after latest available year, not confirmed data.</p></div>
            <div className="home-trend-card"><div><small>For planning teams and the public</small><h3>Where may more support be useful?</h3><p className="home-chart-note">Each bar compares municipalities using a modeled planning score from 0–100. Longer bar means the model suggests greater need for outreach, testing access, or public-health resources. It is not a patient count, infection probability, or personal risk score.</p></div><div className="home-signal-bars">{[...rows].sort((a, b) => Number(b.TRANSMISSION_PRESSURE_INDEX || 0) - Number(a.TRANSMISSION_PRESSURE_INDEX || 0)).map((row) => <div className="home-signal-row" key={row.PSGC}><span>{row.LOCATION}</span><i><b style={{ width: `${Math.min(100, Math.max(4, Number(row.TRANSMISSION_PRESSURE_INDEX || 0)))}%` }} /></i><strong>{Number(row.TRANSMISSION_PRESSURE_INDEX || 0).toFixed(0)}<small>/100</small></strong></div>)}</div><div className="home-signal-definition"><strong>How to read it</strong><span>Read municipality name, then compare bar length and score.</span><span>High score means stronger combined planning signal.</span><span>Low score does not mean no HIV cases or no need for care.</span></div><p className="home-chart-note">This public view supports awareness and resource planning. It does not diagnose anyone or replace official surveillance or medical advice.</p></div>
          </section>

          {view === 'home' && <HistoricalTrends />}
          <section className="home-trust">
            <ShieldCheck size={30} aria-hidden="true" />
            <div><p className="eyebrow">Built with care</p><h2>Your privacy comes first.</h2><p>ARCHIVE displays aggregate planning data only. It does not collect personal HIV status, diagnose anyone, or replace qualified medical advice.</p></div>
            <button onClick={() => navigate('about')}>How ARCHIVE works <ArrowRight size={16} /></button>
          </section>
        </>}

        {view === 'map' && <section className="map-page"><div className="map-toolbar"><div><p className="eyebrow">Public aggregate view</p><h1>Region XII Risk Map</h1><p>Planning scenarios, not diagnoses.</p></div><label className="field">Metric<select value={String(metric)} onChange={(event) => setMetric(event.target.value as keyof SnapshotRow)}><option value="TRANSMISSION_PRESSURE_INDEX">Transmission pressure</option><option value="PREDICTED_CASES">Predicted cases</option><option value="TESTING_CENTER_NEED_SCORE">Testing-center need</option></select></label></div>{geometry && rows.length ? <MapView geometry={geometry} rows={rows} metric={metric} /> : <div className="map-placeholder"><div className="map-mark">XII</div><p>Start backend to load municipality geometry and analytics.</p></div>}<p className="map-disclaimer">Aggregate municipality-level planning information. No individual HIV status is collected or displayed.</p></section>}
        {view === 'education' && <section className="page education-page"><p className="eyebrow">Know. Prevent. Support.</p><h1>HIV Education</h1><p className="lead">Clear videos and practical facts about prevention, testing, treatment, and living well with HIV.</p><div className="content-grid"><article><h2>HIV basics</h2><p>HIV affects immune system. It is not spread through hugging, sharing food, toilets, or mosquito bites.</p></article><article><h2>Testing</h2><p>Testing is only way to know HIV status. Confidential testing and early care protect health.</p></article><article><h2>Prevention</h2><p>Condoms, regular testing, PrEP, sterile injecting equipment, and effective treatment reduce transmission.</p></article><article><h2>PrEP and PEP</h2><p>PrEP is taken before possible exposure. PEP is emergency medicine started as soon as possible, no later than 72 hours after exposure.</p></article><article><h2>Treatment and U=U</h2><p>Effective treatment can suppress HIV. An undetectable viral load means no sexual transmission: U=U.</p></article><article><h2>Respect and support</h2><p>HIV status does not define a person. Privacy, consent, accurate language, and stigma-free care matter.</p></article></div><div className="education-videos"><div className="education-videos-heading"><div><p className="eyebrow">Watch and learn</p><h2>Stories, prevention, and action</h2></div><p>Use these videos to understand HIV services, prevention, stigma, and community support.</p></div><div className="video-grid"><article><div className="video-frame"><iframe src="https://www.youtube.com/embed/E3IgQlauYw4" title="Equalize Access to HIV services" loading="lazy" allowFullScreen /></div><h3>Equalize Access to HIV services</h3><p>Learn why accessible, respectful HIV services matter for every community.</p></article><article><div className="video-frame"><iframe src="https://www.youtube.com/embed/4K0Cmq7T3yU" title="Living with HIV in Koronadal, Philippines" loading="lazy" allowFullScreen /></div><h3>Living with HIV in Koronadal, Philippines</h3><p>A local perspective that centers dignity, lived experience, and support.</p></article><article><div className="video-frame"><iframe src="https://www.youtube.com/embed/pVlsNxIkcZQ" title="The HIV AIDS Epidemic" loading="lazy" allowFullScreen /></div><h3>The HIV/AIDS Epidemic</h3><p>Explore the global HIV response and why prevention and treatment remain important.</p></article><article><div className="video-frame"><iframe src="https://www.youtube.com/embed/sN6rFDkRD40" title="World AIDS Day" loading="lazy" allowFullScreen /></div><h3>World AIDS Day</h3><p>Remember communities affected by HIV and renew commitment to ending stigma.</p></article><article><div className="video-frame"><iframe src="https://www.youtube.com/embed/Y6U6JySZgrk" title="DOH HIV Campaign Video" loading="lazy" allowFullScreen /></div><h3>DOH HIV Campaign Video</h3><p>Public-health guidance on HIV awareness and prevention in the Philippines.</p></article></div><p className="sources">Video content belongs to its respective publishers. ARCHIVE provides links for education, not endorsement of every statement. For personal decisions, contact a qualified health professional or verified testing center.</p></div></section>}
        {view === 'care' && <section className="page"><p className="eyebrow">Confidential care access</p><h1>Request care guidance</h1><p className="lead">Submit a request. An administrator reviews it before assigning a verified center.</p><PreRegistration /></section>}
        {view === 'about' && <section className="page narrow about-page"><p className="eyebrow">About ARCHIVE</p><h1>Evidence for action.<br /><span>Information for everyone.</span></h1><p className="lead">ARCHIVE combines aggregate surveillance, MLR-LSTM forecast scenarios, spatial statistics, and GIS outputs to support HIV prevention planning across Region XII.</p><div className="about-principles"><article><strong>01</strong><h2>Public first</h2><p>Clear regional information helps communities understand trends without exposing anyone’s private health status.</p></article><article><strong>02</strong><h2>Evidence led</h2><p>Historical records, operational data, spatial analysis, and forecast scenarios work together in one view.</p></article><article><strong>03</strong><h2>Action ready</h2><p>Use insights to explore testing access, plan services, and find verified care options.</p></article></div><div className="about-note"><p className="eyebrow">Important boundary</p><p>ARCHIVE does not diagnose HIV or replace qualified medical care. Public counts are aggregate reports, not a count of unique people. Forecasts are planning scenarios, not personal risk predictions.</p></div></section>}
        {view === 'control' && <section className="page data-center"><div className="data-center-heading"><div><p className="eyebrow">Model operations · read-only</p><h1>Data Center</h1><p className="lead">Core machine-learning outputs behind ARCHIVE planning views.</p></div><span className={`service-status ${health?.database_available ? 'online' : ''}`}><Activity size={15} /> {health?.database_available ? 'Analytics online' : 'Backend offline'}</span></div><div className="model-banner"><Database size={24} /><div><strong>MLR–LSTM forecasting pipeline</strong><p>Forecast values, transmission pressure, hotspot analysis, and testing-access recommendations. Aggregate municipality data only.</p></div></div><div className="data-metrics"><article><small>Forecast periods</small><strong>{summary.length || '—'}</strong><span>regional snapshots</span></article><article><small>Municipalities scored</small><strong>{rows.length || '—'}</strong><span>latest period</span></article><article><small>Planning alerts</small><strong>{alerts.length || '—'}</strong><span>aggregate signals</span></article><article><small>API version</small><strong>{health?.api_version || '—'}</strong><span>{String(metadata?.project || 'Phase 2 runtime')}</span></article></div><div className="data-center-grid"><article className="data-panel"><div className="panel-heading"><div><small>Priority ranking</small><h2>Highest transmission pressure</h2></div><span>Latest model output</span></div>{ranking.length ? <ol className="signal-list">{ranking.slice(0, 8).map((row) => <li key={row.PSGC}><span>{row.LOCATION}<small>{row.PROVINCE}</small></span><strong>{row.VALUE.toFixed(2)}</strong></li>)}</ol> : <p className="panel-empty">Start analytics API to load model rankings.</p>}</article><article className="data-panel"><div className="panel-heading"><div><small>Model signals</small><h2>Recent planning alerts</h2></div><span>Not diagnoses</span></div>{alerts.length ? <ul className="alert-list">{alerts.slice(0, 6).map((alert, index) => <li key={`${alert.PSGC}-${alert.PERIOD}-${index}`}><strong>{alert.LOCATION}</strong><span>{alert.ALERT_TYPE || alert.ALERT_LEVEL || 'Planning signal'}</span></li>)}</ul> : <p className="panel-empty">No alert data available.</p>}</article></div><p className="data-note">Data Center exposes aggregate model outputs for planning. It does not expose personal records, HIV status, or diagnostic conclusions.</p></section>}
      </main>

      <footer><strong>ARCHIVE</strong><span>HIV awareness and decision support for Region XII</span><span>Not medical diagnosis</span></footer>
    </div>
  )
}

export default App
