import { useEffect, useMemo, useState } from 'react'
import { api, type Intervention } from './api'

type Props = { visible: boolean }

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

export default function InterventionCalendar({ visible }: Props) {
  const [items, setItems] = useState<Intervention[]>([])
  const [month, setMonth] = useState(3)
  const [province, setProvince] = useState('All')
  const [selectedDay, setSelectedDay] = useState<number | null>(null)
  const year = 2026

  useEffect(() => {
    if (visible) api.interventions().then(setItems).catch(() => setItems([]))
  }, [visible])

  useEffect(() => {
    if (selectedDay === null) return
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') setSelectedDay(null) }
    document.addEventListener('keydown', close)
    return () => document.removeEventListener('keydown', close)
  }, [selectedDay])

  const provinces = [...new Set(items.map((item) => item.province).filter(Boolean))]
  const filtered = items.filter((item) => province === 'All' || item.province === province)
  const monthItems = filtered.filter((item) => {
    if (!item.start || !item.end) return false
    const monthStart = `${year}-${String(month + 1).padStart(2, '0')}-01`
    const monthEnd = `${year}-${String(month + 1).padStart(2, '0')}-${new Date(year, month + 1, 0).getDate()}`
    return item.start <= monthEnd && item.end >= monthStart
  })
  const cells = useMemo(() => {
    const firstWeekday = new Date(year, month, 1).getDay()
    const days = new Date(year, month + 1, 0).getDate()
    return Array.from({ length: 42 }, (_, index) => {
      const day = index - firstWeekday + 1
      return day > 0 && day <= days ? day : null
    })
  }, [month])

  if (!visible) return null

  const eventsForDay = (day: number) => {
    const date = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    return monthItems.filter((item) => item.start <= date && item.end >= date)
  }
  const selectedEvents = selectedDay ? eventsForDay(selectedDay) : []
  const selectedDate = selectedDay
    ? new Date(year, month, selectedDay).toLocaleDateString('en-PH', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
    : ''

  return (
    <section className="intervention-live-calendar" aria-label="Actual 2026 HIV activities">
      <header className="intervention-calendar-heading">
        <div><p className="eyebrow">DOH CHD XII · Verified schedule</p><h2>Intervention calendar</h2></div>
        <p>Browse confirmed HIV programs, training, consultations, and community activities across Region XII.</p>
      </header>

      <div className="intervention-calendar-toolbar">
        <div className="calendar-month-nav">
          <button type="button" onClick={() => { setMonth((value) => Math.max(0, value - 1)); setSelectedDay(null) }} disabled={month === 0} aria-label="Previous month">‹</button>
          <strong>{new Date(year, month).toLocaleDateString('en-PH', { month: 'long', year: 'numeric' })}</strong>
          <button type="button" onClick={() => { setMonth((value) => Math.min(11, value + 1)); setSelectedDay(null) }} disabled={month === 11} aria-label="Next month">›</button>
        </div>
        <label>Coverage<select value={province} onChange={(event) => setProvince(event.target.value)}><option>All</option>{provinces.map((item) => <option key={item}>{item}</option>)}</select></label>
      </div>

      <div className="calendar-layout">
        <div className="month-calendar">
          <div className="calendar-weekdays">{WEEKDAYS.map((day) => <span key={day}>{day}</span>)}</div>
          <div className="calendar-days">{cells.map((day, index) => {
            const events = day ? eventsForDay(day) : []
            return <div className={`calendar-cell${day ? '' : ' empty'}${events.length ? ' has-event' : ''}${day === selectedDay ? ' selected' : ''}`} key={index}>{day && <><button className="calendar-date-button" type="button" onClick={() => setSelectedDay(day)} aria-label={`View events for ${new Date(year, month, day).toLocaleDateString('en-PH', { month: 'long', day: 'numeric' })}`}><span className="calendar-day-number">{day}</span></button><div className="calendar-cell-events">{events.map((event) => <button type="button" key={event.id} title={event.title} onClick={() => setSelectedDay(day)}>{event.title}</button>)}</div></>}</div>
          })}</div>
        </div>

        <aside className="calendar-agenda" aria-label="Monthly agenda">
          <div><p className="eyebrow">Monthly agenda</p><strong>{monthItems.length} {monthItems.length === 1 ? 'activity' : 'activities'}</strong></div>
          {monthItems.map((item) => <article key={item.id}>
            <time>{new Date(`${item.start}T00:00:00`).toLocaleDateString('en-PH', { month: 'short', day: 'numeric' })}{item.end !== item.start && `–${new Date(`${item.end}T00:00:00`).getDate()}`}</time>
            <h3>{item.title}</h3><p>{item.municipality || item.province}</p><span>{item.status}</span>
          </article>)}
          {!monthItems.length && <p className="calendar-empty">No scheduled activities this month.</p>}
        </aside>
      </div>

      {selectedDay !== null && <div className="calendar-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedDay(null) }}>
        <section className="calendar-date-modal" role="dialog" aria-modal="true" aria-labelledby="calendar-modal-title">
          <header><div><p className="eyebrow">Selected date</p><h3 id="calendar-modal-title">{selectedDate}</h3><p>{selectedEvents.length} {selectedEvents.length === 1 ? 'event' : 'events'} scheduled</p></div><button type="button" onClick={() => setSelectedDay(null)} aria-label="Close event details">×</button></header>
          {!selectedEvents.length && <div className="calendar-date-empty"><strong>No scheduled activity</strong><p>No recorded DOH HIV intervention is scheduled for this date.</p></div>}
          <div className="calendar-detail-list">{selectedEvents.map((item) => <article key={item.id}>
            <div className="calendar-detail-title"><span>{item.status}</span><h4>{item.title}</h4><time>{item.start} – {item.end}</time></div>
            <p>{item.description}</p>
            <dl><dt>Location</dt><dd>{item.municipality || item.province}</dd><dt>Target population</dt><dd>{item.target}</dd><dt>Organizer</dt><dd>{item.organization}</dd><dt>Coverage</dt><dd>{item.province}</dd></dl>
          </article>)}</div>
        </section>
      </div>}
    </section>
  )
}
