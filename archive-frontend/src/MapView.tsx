import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Marker, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'
import type { Feature, FeatureCollection, Geometry } from 'geojson'
import type { Layer, PathOptions } from 'leaflet'
import { divIcon, geoJSON } from 'leaflet'
import { api, type Facility, type SnapshotRow } from './api'
import 'leaflet/dist/leaflet.css'

type Properties = { PSGC: string; LOCATION: string; PROVINCE: string }
type Props = { geometry: FeatureCollection<Geometry, Properties>; rows: SnapshotRow[]; metric: keyof SnapshotRow; facilities?: Facility[]; showFacilities?: boolean; overlayMetrics?: (keyof SnapshotRow)[]; showChoropleth?: boolean; selectedPsgc?: string; onSelect?: (row: SnapshotRow | undefined) => void }

const colors = ['#fff5f0', '#fcbba1', '#fb6a4a', '#cb181d', '#67000d']
const heatColors = ['#00a83b', '#7ed321', '#f5d928', '#f28b22', '#d71920']
const facilityPin = divIcon({ className: 'care-ribbon-marker', html: '<span aria-hidden="true">🎗</span>', iconSize: [36, 44], iconAnchor: [18, 40], popupAnchor: [0, -38] })

function FitRegion({ geometry }: { geometry: FeatureCollection<Geometry, Properties> }) {
  const map = useMap()
  useEffect(() => {
    const bounds = geoJSON(geometry).getBounds()
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [18, 18], maxZoom: 10 })
  }, [geometry, map])
  useEffect(() => {
    const container = map.getContainer()
    const resize = () => map.invalidateSize({ animate: false })
    const observer = new ResizeObserver(resize)
    observer.observe(container)
    resize()
    return () => observer.disconnect()
  }, [map])
  return null
}

function MunicipalityLabelZoom() {
  const map = useMap()
  useEffect(() => {
    const update = () => map.getContainer().classList.toggle('show-municipality-labels', map.getZoom() >= 9)
    map.on('zoomend', update)
    update()
    return () => { map.off('zoomend', update) }
  }, [map])
  return null
}

function FocusMunicipality({ geometry, psgc }: { geometry: FeatureCollection<Geometry, Properties>; psgc?: string }) {
  const map = useMap()
  useEffect(() => {
    if (!psgc) return
    const feature = geometry.features.find((item) => String(item.properties.PSGC) === String(psgc))
    if (!feature) return
    const bounds = geoJSON(feature).getBounds()
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [48, 48], maxZoom: 12, animate: true })
  }, [geometry, map, psgc])
  return null
}

export default function MapView({ geometry, rows, metric, facilities = [], showFacilities = true, overlayMetrics = [], showChoropleth = true, selectedPsgc, onSelect }: Props) {
  const [loadedFacilities, setLoadedFacilities] = useState<Facility[]>(facilities)
  useEffect(() => { if (!facilities.length) api.publicFacilities().then(setLoadedFacilities).catch(() => undefined) }, [facilities.length])
  facilities = loadedFacilities
  const heatmap = metric === 'ROLLING_12M_CASES'
  const showCaseHeatmap = heatmap || overlayMetrics.includes('ROLLING_12M_CASES')
  const overlayValues = overlayMetrics.filter((item) => item !== metric)
  const values = rows.map((row) => Number(row[metric])).filter(Number.isFinite)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const caseMax = Math.max(...rows.map((row) => Number(row.ROLLING_12M_CASES)).filter(Number.isFinite), 0)
  const byPsgc = useMemo(() => new Map(rows.map((row) => [String(row.PSGC), row])), [rows])
  const heatPoints = useMemo(() => geometry.features.flatMap((feature) => {
    const row = byPsgc.get(String(feature.properties.PSGC))
    const value = Number(row?.ROLLING_12M_CASES)
    if (!row || !Number.isFinite(value) || value <= 0) return []
    const center = geoJSON(feature).getBounds().getCenter()
    return [{ row, value, center }]
  }), [geometry, byPsgc])
  const style = (feature?: Feature<Geometry, Properties>): PathOptions => {
    const selected = String(feature?.properties.PSGC) === String(selectedPsgc)
    const value = Number(byPsgc.get(String(feature?.properties.PSGC))?.[metric])
    const bucket = Number.isFinite(value) && max > min ? Math.min(4, Math.floor(((value - min) / (max - min)) * 5)) : 0
    if (selected) return { className: 'selected-municipality', color: '#fff', weight: 4, fillColor: '#ff1744', fillOpacity: heatmap ? .12 : .32 }
    return heatmap || !showChoropleth ? { color: '#8f5960', weight: .7, fillOpacity: .04 } : { color: '#f2a1a1', weight: 1, fillColor: ['#3b1118', '#751a25', '#ad2632', '#e0444d', '#ff8b86'][bucket], fillOpacity: .8 }
  }
  const heatStyle = (feature?: Feature<Geometry, Properties>): PathOptions => {
    const value = Number(byPsgc.get(String(feature?.properties.PSGC))?.ROLLING_12M_CASES)
    const intensity = caseMax > 0 && Number.isFinite(value) ? Math.min(1, Math.sqrt(value / Math.max(caseMax * .65, 1))) : 0
    return { color: 'transparent', weight: 0, fillColor: heatColors[Math.min(heatColors.length - 1, Math.floor(intensity * heatColors.length))], fillOpacity: .12 + intensity * .16, interactive: false }
  }
  const bind = (feature: Feature<Geometry, Properties>, layer: Layer) => {
    const row = byPsgc.get(String(feature.properties.PSGC))
    const value = Number(row?.[metric])
    const rolling = Number(row?.ROLLING_12M_CASES)
    const pressure = Number(row?.TRANSMISSION_PRESSURE_INDEX)
    layer.bindPopup(`<div class="municipality-popup"><span class="eyebrow">Municipality profile</span><h3>${feature.properties.LOCATION}</h3><p>${feature.properties.PROVINCE}</p><div class="municipality-popup-stats"><span><b>${Number.isFinite(value) ? value.toFixed(0) : '—'}</b>${String(metric).replaceAll('_', ' ')}</span><span><b>${Number.isFinite(rolling) ? rolling.toFixed(0) : '—'}</b>rolling 12-month cases</span><span><b>${Number.isFinite(pressure) ? pressure.toFixed(0) : '—'}</b>planning score /100</span></div><small>Aggregate model output. Not a diagnosis or individual patient count.</small></div>`)
    layer.bindTooltip(feature.properties.LOCATION, { permanent: true, direction: 'center', className: 'municipality-label', opacity: .9 })
    layer.on('click', () => onSelect?.(row))
  }

  return <div className="map-view">
    <MapContainer className="native-map" center={[6.55, 124.85]} zoom={8} scrollWheelZoom>
      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" subdomains="abc" />
      <FitRegion geometry={geometry} />
      <MunicipalityLabelZoom />
      <FocusMunicipality geometry={geometry} psgc={selectedPsgc} />
      <GeoJSON key={`${metric}-${rows.length}-${selectedPsgc ?? ''}`} data={geometry} style={style} onEachFeature={bind} />
      {showCaseHeatmap && <GeoJSON key={`heat-fill-${rows.length}`} data={geometry} style={heatStyle} />}
      {showCaseHeatmap && heatPoints.flatMap(({ row, value, center }) => {
        const intensity = caseMax > 0 ? Math.min(1, Math.sqrt(value / Math.max(caseMax * .65, 1))) : 0
        const radius = 14 + intensity * 42
        return [1, .76, .52, .28].map((scale, index) => <CircleMarker
          key={`${row.PSGC}-${index}-${row.PERIOD}`}
          center={center}
          radius={radius * scale}
          pathOptions={{ className: 'heat-kernel', stroke: false, fillColor: heatColors[Math.min(heatColors.length - 1, Math.floor(intensity * heatColors.length))], fillOpacity: (.16 + intensity * .22) * (1 - index * .1) }}
          eventHandlers={{ click: () => onSelect?.(row) }}
        >{index === 0 && <Tooltip><strong>{row.LOCATION}</strong><br />Rolling 12-month cases: {value.toFixed(0)}<br />Period: {row.PERIOD}</Tooltip>}</CircleMarker>)
      })}
      {overlayValues.includes('TRANSMISSION_PRESSURE_INDEX') && geometry.features.flatMap((feature) => {
        const row = byPsgc.get(String(feature.properties.PSGC))
        const value = Number(row?.TRANSMISSION_PRESSURE_INDEX)
        if (!row || !Number.isFinite(value)) return []
        const center = geoJSON(feature).getBounds().getCenter()
        return <CircleMarker key={`risk-${row.PSGC}-${row.PERIOD}`} center={center} radius={Math.max(3, Math.min(10, value / 10))} pathOptions={{ color: '#fff', weight: 1, fillColor: '#e31b36', fillOpacity: .7 }}><Tooltip>Risk overlay: {value.toFixed(1)}</Tooltip></CircleMarker>
      })}
      {showFacilities && facilities.filter((facility) => Number.isFinite(facility.latitude) && Number.isFinite(facility.longitude)).map((facility) => <Marker key={facility.facility_code} icon={facilityPin} position={[facility.latitude as number, facility.longitude as number]}><Popup><div className="facility-popup"><span className="facility-popup-kicker">Verified care location</span><h3>{facility.name}</h3><span className="facility-popup-type">{facility.facility_type.replaceAll('_', ' ')}</span><div className="facility-popup-address">{[facility.address, facility.municipality, facility.province].filter(Boolean).join(' · ')}</div>{facility.services && <div className="facility-popup-services">{facility.services.split(';').map((service) => <span key={service}>{service.trim()}</span>)}</div>}<small className="facility-popup-note">Contact center directly for current schedules and availability.</small></div></Popup></Marker>)}
    </MapContainer>
    <div className="legend" aria-label="Map value scale">{heatmap ? 'Lower density' : 'Lower'} {(heatmap ? heatColors : colors).map((color) => <span key={color} style={{ background: color }} />)} {heatmap ? 'Hot core' : 'Higher'}</div>
  </div>
}
