import { useEffect, useState } from 'react'
import { CheckCircle2, ChevronLeft, ChevronRight, Clock3, LockKeyhole, Mail, MapPin, MessageCircleHeart, Phone, Users } from 'lucide-react'
import { divIcon, latLngBounds } from 'leaflet'
import { GeoJSON, MapContainer, Marker, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { api, type Facility, type Municipality, type MunicipalityGeometry } from './api'
import 'leaflet/dist/leaflet.css'

function FitCareCenters({ facilities }: { facilities: Facility[] }) {
  const map = useMap()

  useEffect(() => {
    const resize = () => map.invalidateSize({ animate: false })
    const observer = new ResizeObserver(resize)
    observer.observe(map.getContainer())
    resize()
    return () => observer.disconnect()
  }, [map])

  useEffect(() => {
    const points = facilities.flatMap((facility) =>
      Number.isFinite(facility.latitude) && Number.isFinite(facility.longitude)
        ? [[facility.latitude as number, facility.longitude as number] as [number, number]]
        : [],
    )
    if (points.length) map.fitBounds(latLngBounds(points), { padding: [40, 40], maxZoom: 10 })
  }, [facilities, map])

  return null
}

const ribbonPin = divIcon({
  className: 'care-ribbon-marker',
  html: '<span aria-hidden="true">🎗</span>',
  iconSize: [36, 44],
  iconAnchor: [18, 40],
  popupAnchor: [0, -38],
  tooltipAnchor: [18, -22],
})

export default function PreRegistration({ onSubmitted, onClose }: { onSubmitted?: () => void; onClose?: () => void }) {
  const [municipalities, setMunicipalities] = useState<Municipality[]>([])
  const [geometry, setGeometry] = useState<MunicipalityGeometry | null>(null)
  const [facilities, setFacilities] = useState<Facility[]>([])
  const [selectedFacility, setSelectedFacility] = useState('')
  const [step, setStep] = useState(1)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [thankYouSlide, setThankYouSlide] = useState(0)
  const [municipality, setMunicipality] = useState('')
  const [preferredChannel, setPreferredChannel] = useState<'email' | 'sms'>('email')
  const [contactValue, setContactValue] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const selected = facilities.find((facility) => facility.facility_code === selectedFacility)

  useEffect(() => {
    api.municipalities().then(setMunicipalities).catch(() => undefined)
    api.geometry().then(setGeometry).catch(() => undefined)
    api.publicFacilities().then(setFacilities).catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!message) return
    const timer = window.setInterval(() => setThankYouSlide((slide) => (slide + 1) % 3), 2600)
    return () => window.clearInterval(timer)
  }, [message])

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setMessage('')
    setError('')
    try {
      const result = await api.submitPreRegistration({
        municipality,
        preferred_channel: preferredChannel,
        contact_value: contactValue.trim(),
        email: email.trim(),
        phone: phone.trim(),
        consent: new FormData(event.currentTarget).get('consent') === 'on',
        facility_code: selectedFacility,
      })
      setMessage(result.reference_code)
      onSubmitted?.()
      event.currentTarget.reset()
      setStep(1)
      setSelectedFacility('')
      setMunicipality('')
      setPreferredChannel('email')
      setContactValue('')
      setEmail('')
      setPhone('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to submit request')
    }
  }

  if (message) {
    const slides = [
      <><span className="thank-you-ribbon" aria-hidden="true">🎗</span><p className="eyebrow">Thank you for reaching out</p><h2>We are here with you.</h2></>,
      <><span className="thank-you-ribbon" aria-hidden="true">🎗</span><p className="eyebrow">A private next step</p><h2>We’ll always be here for you.</h2></>,
      <><CheckCircle2 size={42} /><p className="eyebrow">Pre-registration submitted</p><h2>Your request is safe with us.</h2></>,
    ]
    return <div className="care-request care-submitted"><div className="care-request-form"><div className="thank-you-slide" key={thankYouSlide}>{slides[thankYouSlide]}</div><p>Our care team will review your request. After an administrator accepts it, you will receive a private confirmation link by email.</p><strong className="care-reference">{message}</strong><p className="care-note"><LockKeyhole size={15} /> Your information stays private and is used only for care coordination.</p><div className="care-submitted-actions"><button type="button" className="home-primary" onClick={() => { setMessage(''); setThankYouSlide(0) }}>Submit another request <ChevronRight size={17} /></button><button type="button" className="care-close-button" onClick={onClose}>Close</button></div></div></div>
  }

  return <div className="care-workflow">
    <div className="care-workflow-map">
      <MapContainer center={[6.55, 124.85]} zoom={8} scrollWheelZoom>
        <TileLayer attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>' url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" subdomains="abcd" />
        {geometry && <GeoJSON data={geometry} style={{ color: '#ff5a61', weight: 1.4, opacity: 0.9, fillOpacity: 0.03 }} />}
        <FitCareCenters facilities={facilities} />
        {facilities.filter((facility) => Number.isFinite(facility.latitude) && Number.isFinite(facility.longitude)).map((facility) =>
          <Marker key={facility.facility_code} icon={ribbonPin} position={[facility.latitude as number, facility.longitude as number]} eventHandlers={{ click: () => { setSelectedFacility(facility.facility_code); setError('') } }}>
            <Tooltip direction="right">{facility.name}</Tooltip>
            <Popup><div className="care-map-preview"><small>{facility.facility_type.replaceAll('_', ' ')}</small><strong>{facility.name}</strong><span><MapPin size={13} />{facility.address || `${facility.municipality}, ${facility.province}`}</span><button type="button" onClick={() => { setSelectedFacility(facility.facility_code); setError('') }}>View center details</button></div></Popup>
          </Marker>,
        )}
      </MapContainer>
      {!facilities.length && <div className="care-map-empty"><strong>Testing-center locations coming soon</strong><small>Verified center data will appear here.</small></div>}
    </div>
    <div className="care-workflow-panel">
      <div className="care-workflow-intro"><span className="care-request-icon"><MessageCircleHeart size={24} /></span><p className="eyebrow">Private care navigation</p><h2>We are here to help.</h2><p>You can take this one step at a time. No name, diagnosis, or HIV status needed.</p><div className="care-request-points"><span><LockKeyhole size={16} />Private and limited-use information</span><span><Clock3 size={16} />About 1 minute to complete</span></div></div>
      <div className="care-steps"><span className={step === 1 ? 'active' : ''}>1 Center</span><span className={step === 2 ? 'active' : ''}>2 Contact</span><span className={step === 3 ? 'active' : ''}>3 Consent</span></div>
      {error && <p className="login-error">{error}</p>}
      <form onSubmit={submit}>
        {step === 1 && <div className="care-step"><p className="eyebrow">Step 1 of 3</p><h3>Choose a testing center close to you.</h3><p>Select a ribbon on map to review center details.</p>{selected ? <article className="care-facility-card"><span className="care-facility-pin"><MapPin size={20} /></span><div><small>{selected.facility_type.replaceAll('_', ' ')}</small><h4>{selected.name}</h4><p>{[selected.address, selected.municipality, selected.province].filter(Boolean).join(' · ')}</p>{selected.services && <div className="care-facility-services">{selected.services.split(';').map((service) => <span key={service}>{service.trim()}</span>)}</div>}<div className="care-facility-contacts">{selected.phone && <a href={`tel:${selected.phone.split(';')[0].trim()}`}><Phone size={14} />{selected.phone}</a>}{selected.email && <a href={`mailto:${selected.email.split(';')[0].trim()}`}><Mail size={14} />{selected.email}</a>}{selected.contact_people && <div><Users size={14} /><ul>{selected.contact_people.split('|').map((person) => <li key={person}>{person}</li>)}</ul></div>}{selected.opening_hours && <p className="care-facility-hours"><Clock3 size={14} /> {selected.opening_hours}</p>}</div></div></article> : <p className="care-selected">No center selected yet.</p>}<button type="button" className="home-primary" disabled={!selected} onClick={() => { setError(''); setStep(2) }}>Choose this center <ChevronRight size={17} /></button></div>}
        {step === 2 && <div className="care-step"><p className="eyebrow">Step 2 of 3</p><h3>How can our team reach you?</h3><label>Municipality<select name="municipality" required value={municipality} onChange={(event) => { setMunicipality(event.target.value); setError('') }}><option value="">Select municipality</option>{municipalities.map((item) => <option key={item.PSGC} value={item.LOCATION}>{item.LOCATION} · {item.PROVINCE}</option>)}</select></label><label>Preferred contact<select name="preferred_channel" required value={preferredChannel} onChange={(event) => { setPreferredChannel(event.target.value as 'email' | 'sms'); setError('') }}><option value="email">Email</option><option value="sms">SMS</option></select></label><label>Email address<input type="email" value={email} onChange={(event) => { setEmail(event.target.value); setContactValue(event.target.value); setError('') }} placeholder="you@example.com" /></label><label>Mobile number<input type="tel" value={phone} onChange={(event) => { setPhone(event.target.value); setContactValue(event.target.value); setError('') }} placeholder="09XX XXX XXXX" /></label><p className="care-field-note">Add both so the care team has a backup contact.</p><div className="care-step-actions"><button type="button" onClick={() => setStep(1)}><ChevronLeft size={16} />Back</button><button type="button" className="home-primary" onClick={() => { if (!municipality || (!email.trim() && !phone.trim())) { setError('Choose municipality and enter an email or mobile number.'); return } setError(''); setStep(3) }}>Continue <ChevronRight size={17} /></button></div></div>}
        {step === 3 && <div className="care-step"><p className="eyebrow">Step 3 of 3</p><h3>Your information, your choice.</h3><p>Under the Data Privacy Act, you may choose whether to share your contact details. We need consent to let an authorized care administrator contact you.</p><label className="consent"><input name="consent" type="checkbox" required />I freely consent to discreet contact about HIV care options. I understand I can withdraw consent later.</label><div className="care-step-actions"><button type="button" onClick={() => setStep(2)}><ChevronLeft size={16} />Back</button><button className="home-primary" type="submit">Submit request <CheckCircle2 size={17} /></button></div></div>}
      </form>
    </div>
  </div>
}
