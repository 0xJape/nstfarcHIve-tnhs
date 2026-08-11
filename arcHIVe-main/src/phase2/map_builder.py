from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from shapely.geometry import shape


def _number(value: Any, decimals: int = 3) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return round(number, decimals)


def build_interactive_map(
    output: Path,
    municipality_geojson: dict[str, Any],
    province_geojson: dict[str, Any],
    region_geojson: dict[str, Any],
    outside_mask: dict[str, Any],
    forecast: pd.DataFrame,
    decomposition: pd.DataFrame,
    recommendations: pd.DataFrame,
    regional: pd.DataFrame,
    metadata: dict[str, Any],
    playback_interval_ms: int = 2600,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    features = municipality_geojson.get("features") or []
    nodes = []
    for index, feature in enumerate(features):
        props = feature.get("properties") or {}
        point = shape(feature["geometry"]).representative_point()
        nodes.append({
            "index": index,
            "psgc": str(props.get("PSGC") or feature.get("id")),
            "name": str(props.get("LOCATION") or ""),
            "province": str(props.get("PROVINCE") or ""),
            "lat": round(float(point.y), 6),
            "lon": round(float(point.x), 6),
            "areaKm2": _number(props.get("AREA_KM2_APPROX"), 2),
        })
    node_index = {node["name"]: node["index"] for node in nodes}
    dates = sorted(forecast["PERIOD"].unique().tolist())
    date_index = {period: i for i, period in enumerate(dates)}
    metrics = {
        "cases": "PREDICTED_CASES",
        "rate": "ROLLING_12M_RATE_PER_100K",
        "hotspot": "GI_STAR_Z_SCORE",
        "pressure": "TRANSMISSION_PRESSURE_INDEX",
        "centerNeed": "TESTING_CENTER_NEED_SCORE",
        "lower95": "LOWER_95",
        "upper95": "UPPER_95",
        "growth": "DIAGNOSIS_GROWTH_RATIO",
        "moran": "LOCAL_MORANS_I",
        "clusterSize": "HOTSPOT_CLUSTER_SIZE",
        "alert": "AUTOMATIC_ALERT",
        "centers": "ACTIVE_TESTING_CENTERS",
        "population": "POPULATION",
        "populationGrowth": "MONTHLY_POPULATION_GROWTH_RATE",
        "newInfections": "NEW_INFECTIONS_ESTIMATE",
        "undiagnosed": "PLHIV_UNDIAGNOSED",
        "suppressed": "PLHIV_VIRALLY_SUPPRESSED",
        "infectiousPool": "EFFECTIVE_INFECTIOUS_POOL",
        "neighborInfectious": "NEIGHBOR_INFECTIOUS_POOL_PER_100K",
        "artCoverage": "ART_COVERAGE",
        "suppressionCoverage": "VIRAL_SUPPRESSION_COVERAGE",
        "testingAccess": "TESTING_ACCESS_SCORE",
        "centersOpened": "NEW_TESTING_CENTERS_OPENED",
        "pendingCenters": "PENDING_TESTING_CENTERS",
    }
    arrays: dict[str, list[list[Any]]] = {
        key: [[0] * len(nodes) for _ in dates] for key in metrics
    }
    text_arrays: dict[str, list[list[str]]] = {
        "hotspotClass": [["NOT_SIGNIFICANT"] * len(nodes) for _ in dates],
        "moranCluster": [["NOT_SIGNIFICANT"] * len(nodes) for _ in dates],
        "pressureLevel": [["LOW"] * len(nodes) for _ in dates],
        "alertReason": [["NONE"] * len(nodes) for _ in dates],
    }
    for row in forecast.itertuples(index=False):
        di = date_index[row.PERIOD]
        ni = node_index[row.LOCATION]
        row_dict = row._asdict()
        for key, column in metrics.items():
            arrays[key][di][ni] = _number(row_dict[column], 4)
        text_arrays["hotspotClass"][di][ni] = str(row.HOTSPOT_CLASS)
        text_arrays["moranCluster"][di][ni] = str(row.LOCAL_MORAN_CLUSTER)
        text_arrays["pressureLevel"][di][ni] = str(row.TRANSMISSION_PRESSURE_LEVEL)
        text_arrays["alertReason"][di][ni] = str(row.ALERT_REASON)

    decomposition_future = decomposition[decomposition["PERIOD"].isin(dates)]
    decomposition_arrays = {
        "trend": [[0] * len(nodes) for _ in dates],
        "seasonal": [[0] * len(nodes) for _ in dates],
        "residual": [[0] * len(nodes) for _ in dates],
        "residualZ": [[0] * len(nodes) for _ in dates],
    }
    for row in decomposition_future.itertuples(index=False):
        di = date_index[row.PERIOD]
        ni = node_index[row.LOCATION]
        decomposition_arrays["trend"][di][ni] = _number(row.TREND_COMPONENT, 4)
        decomposition_arrays["seasonal"][di][ni] = _number(row.SEASONAL_COMPONENT, 4)
        decomposition_arrays["residual"][di][ni] = _number(row.RESIDUAL_COMPONENT, 4)
        decomposition_arrays["residualZ"][di][ni] = _number(row.RESIDUAL_Z_SCORE, 4)

    recs = []
    for row in recommendations.itertuples(index=False):
        recs.append({
            "psgc": str(row.PSGC), "name": str(row.LOCATION), "province": str(row.PROVINCE),
            "lat": _number(row.CANDIDATE_LATITUDE, 6), "lon": _number(row.CANDIDATE_LONGITUDE, 6),
            "score": _number(row.TESTING_CENTER_NEED_SCORE, 2), "priority": str(row.PRIORITY_LEVEL),
            "additional": int(row.RECOMMENDED_ADDITIONAL_CENTERS),
            "currentCenters": _number(row.CURRENT_ESTIMATED_TESTING_CENTERS, 0),
            "population": _number(row.POPULATION, 0), "method": str(row.CANDIDATE_METHOD),
        })
    regional_rows = [{key: (_number(value, 4) if isinstance(value, (float, int, np.number)) else value) for key, value in row.items()} for row in regional.to_dict(orient="records")]

    payload = {
        "dates": dates,
        "nodes": nodes,
        "geojson": municipality_geojson,
        "provinceGeojson": province_geojson,
        "regionGeojson": region_geojson,
        "outsideMask": outside_mask,
        "values": arrays,
        "texts": text_arrays,
        "decomposition": decomposition_arrays,
        "recommendations": recs,
        "regional": regional_rows,
        "playbackIntervalMs": max(1600, int(playback_interval_ms)),
        "metadata": metadata,
    }
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)

    html = r'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>arcHIVe Region XII HIV Forecast Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
<style>
:root{--navy:#102a43;--panel:rgba(255,255,255,.97);--border:#cbd5e1;--text:#14213d;--muted:#667085;--danger:#ff0015;--shadow:0 8px 28px rgba(15,23,42,.24)}
*{box-sizing:border-box}html,body,#map{height:100%;width:100%;margin:0}body{overflow:hidden;font-family:Inter,Arial,sans-serif;color:var(--text);background:#88939c}#map{position:fixed;inset:0;background:#8d98a1}.leaflet-container{font-family:Inter,Arial,sans-serif}.leaflet-tile-pane{filter:grayscale(.84) saturate(.15) brightness(.72) contrast(.93)}
.leaflet-control-zoom{margin-top:82px!important;border:none!important;box-shadow:var(--shadow)!important}.leaflet-control-zoom a{border:none!important;color:#102a43!important}.floating{position:fixed;z-index:1000;background:var(--panel);border:1px solid rgba(255,255,255,.7);box-shadow:var(--shadow);backdrop-filter:blur(8px)}
.title-card{left:14px;top:14px;max-width:445px;border-radius:12px;padding:10px 13px}.title-card h1{font-size:17px;margin:0}.title-card p{font-size:11px;color:var(--muted);margin:3px 0 0;line-height:1.3}.scenario-pill{display:inline-block;margin-top:6px;padding:3px 7px;background:#fff7ed;border:1px solid #fdba74;border-radius:999px;font-size:10px;color:#9a3412}
.button-dock{top:14px;right:14px;border-radius:13px;padding:6px;display:flex;gap:6px}.float-btn{border:0;border-radius:9px;padding:9px 11px;background:white;color:#102a43;font:700 12px Inter,Arial;cursor:pointer;box-shadow:0 1px 4px rgba(15,23,42,.15)}.float-btn.primary{background:#102a43;color:white}.float-btn.alerting{background:#ff0015;color:white}.float-btn:hover{transform:translateY(-1px)}
.settings{right:14px;top:68px;width:320px;border-radius:12px;padding:11px;display:none}.settings.open{display:block}.settings label{display:block;font-size:11px;color:var(--muted);margin-bottom:8px}.settings select,.settings input{width:100%;padding:8px;border:1px solid var(--border);border-radius:7px;background:white;font:12px Inter,Arial;margin-top:3px}
.timeline{left:50%;bottom:16px;transform:translateX(-50%);width:min(780px,calc(100vw - 34px));border-radius:14px;padding:9px 12px}.timeline-top{display:flex;align-items:center;gap:10px;font-size:11px}.timeline strong{font-size:14px;color:#102a43}.timeline input{width:100%;accent-color:#dc2626}.timeline-status{margin-left:auto;color:var(--muted);white-space:nowrap}
.legend{left:14px;bottom:16px;border-radius:12px;padding:9px 11px;font-size:10px;width:245px}.gradient{height:12px;border-radius:5px;background:linear-gradient(90deg,#10b981 0%,#fde047 50%,#ef4444 100%);border:1px solid rgba(255,255,255,.8)}.legend-labels{display:flex;justify-content:space-between;margin-top:3px}.legend-extra{margin-top:6px;line-height:1.45;color:#475467}.legend-ping{display:inline-block;width:12px;height:12px;background:#ff0015;border-radius:50%;box-shadow:0 0 0 5px rgba(255,0,21,.25);vertical-align:middle}.legend-center{display:inline-block;width:12px;height:12px;background:#1d4ed8;border:2px solid white;transform:rotate(45deg);vertical-align:middle}
.drawer{position:fixed;z-index:1100;right:0;top:0;width:min(610px,94vw);height:100%;background:#f8fafc;box-shadow:-10px 0 32px rgba(15,23,42,.28);transform:translateX(102%);transition:transform .26s ease;display:flex;flex-direction:column}.drawer.open{transform:translateX(0)}.drawer-head{background:#102a43;color:white;padding:13px 15px;display:flex;align-items:center;gap:10px}.drawer-head h2{font-size:17px;margin:0;flex:1}.drawer-head button{border:0;background:white;color:#102a43;border-radius:7px;padding:6px 9px;cursor:pointer}.tabs{display:flex;gap:4px;padding:8px;background:white;border-bottom:1px solid var(--border);overflow-x:auto}.tab-btn{border:1px solid var(--border);background:white;border-radius:7px;padding:7px 10px;font:700 11px Inter;white-space:nowrap;cursor:pointer}.tab-btn.active{background:#102a43;color:white}.tab-panel{display:none;overflow:auto;padding:12px;flex:1}.tab-panel.active{display:block}.card{background:white;border:1px solid var(--border);border-radius:10px;padding:11px;margin-bottom:10px}.card h3{font-size:14px;margin:0 0 8px}.small{font-size:11px;color:var(--muted);line-height:1.45}.metric-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.metric{border:1px solid #e2e8f0;border-radius:8px;padding:8px}.metric span{display:block;font-size:10px;color:var(--muted)}.metric b{font-size:15px;font-variant-numeric:tabular-nums}.alert-row{border-left:5px solid #ff0015;background:#fff1f2;border-radius:7px;padding:8px;margin:6px 0;font-size:11px;cursor:pointer}.selected-card{line-height:1.55}.factor-box{background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:9px;font-size:11px;line-height:1.45}
.chart{width:100%;height:230px;border:1px solid #eef2f6;border-radius:7px}.chart text{font:10px Inter,Arial;fill:#475467}.axis{stroke:#94a3b8}.grid{stroke:#e2e8f0}.chart-line{fill:none;stroke-width:2}.credible{fill:#93c5fd;opacity:.3}.cursor{stroke:#0f172a;stroke-dasharray:4 3}.ranking{max-height:560px;overflow:auto}.rank-row{display:grid;grid-template-columns:36px minmax(155px,1fr) 85px;gap:7px;align-items:center;padding:6px;border-bottom:1px solid #edf2f7;cursor:pointer;font-size:11px}.rank-row:hover{background:#f1f5f9}.rank-number{font-weight:800}.rank-name b{display:block}.rank-name span{color:var(--muted);font-size:9px}.rank-value{text-align:right;font-variant-numeric:tabular-nums}.rank-bar-wrap{grid-column:2/4;height:6px;background:#edf2f7;border-radius:999px;overflow:hidden}.rank-bar{height:100%;border-radius:999px}.rank-row.outbreak{background:#fff1f2;box-shadow:inset 4px 0 #ff0015}
.table-tools{position:sticky;top:-12px;background:#f8fafc;padding:0 0 8px;z-index:2}.table-tools input{width:100%;padding:8px;border:1px solid var(--border);border-radius:7px}.table-wrap{overflow:auto;max-height:calc(100vh - 160px);border:1px solid var(--border);background:white}.live-table{border-collapse:separate;border-spacing:0;font-size:9px;white-space:nowrap}.live-table th,.live-table td{padding:5px 6px;border-right:1px solid #e2e8f0;border-bottom:1px solid #e2e8f0;text-align:right}.live-table th{position:sticky;top:0;background:#102a43;color:white;z-index:1}.live-table th:nth-child(-n+3),.live-table td:nth-child(-n+3){text-align:left}.live-table tr{cursor:pointer}.live-table tbody tr:hover{background:#eff6ff}.live-table tbody tr.outbreak{background:#fff1f2;font-weight:700}.live-table td:first-child,.live-table th:first-child{position:sticky;left:0;background:inherit;z-index:1}.live-table th:first-child{background:#102a43}
.municipality-label-icon{background:transparent!important;border:none!important;pointer-events:none!important}.municipality-label-icon span{position:absolute;transform:translate(-50%,-50%);white-space:nowrap;font:800 var(--label-size,8px)/1 Inter,Arial;color:white;text-shadow:-1px -1px 1px #102a43,1px -1px 1px #102a43,-1px 1px 1px #102a43,1px 1px 1px #102a43}.labels-hidden .municipality-label-icon{display:none}.outbreak-ping{width:17px;height:17px;background:#ff0015;border:2px solid white;border-radius:50%;box-shadow:0 0 0 0 rgba(255,0,21,.75);animation:pulse 1.4s infinite}.center-marker{width:15px;height:15px;background:#1d4ed8;border:2px solid white;transform:rotate(45deg);box-shadow:0 2px 8px rgba(15,23,42,.45)}@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(255,0,21,.7)}70%{box-shadow:0 0 0 15px rgba(255,0,21,0)}100%{box-shadow:0 0 0 0 rgba(255,0,21,0)}}
.leaflet-popup-content{margin:11px 13px;min-width:305px}.popup-title{font-weight:800;font-size:14px}.popup-sub{font-size:10px;color:#667085;margin-bottom:6px}.popup-grid{display:grid;grid-template-columns:1fr 1fr;gap:5px;font-size:10px}.popup-grid div{border:1px solid #e2e8f0;border-radius:5px;padding:5px}.popup-grid b{display:block;font-size:12px}.popup-alert{background:#ff0015;color:white;padding:5px;border-radius:6px;text-align:center;font-weight:800;margin:6px 0}.spark{width:100%;height:82px;background:#f8fafc;border-radius:6px;margin:7px 0}.popup-button{width:100%;border:0;background:#102a43;color:white;padding:7px;border-radius:6px;cursor:pointer}
@media(max-width:900px){.title-card{max-width:285px}.title-card p{display:none}.legend{display:none}.timeline{bottom:10px}.button-dock{top:10px;right:10px}.float-btn{padding:8px}.settings{right:10px}.metric-grid{grid-template-columns:1fr}}
</style></head><body>
<div id="map"></div>
<div class="floating title-card"><h1>arcHIVe · Region XII HIV Forecast Map</h1><p>Population-coupled MLR–LSTM projections, HIV care-cascade simulation, treatment decomposition, neighbor transmission pressure, dynamic hotspots, and testing-center planning through 2050.</p><span class="scenario-pill">Development scenario · not official surveillance</span></div>
<div class="floating button-dock"><button class="float-btn" id="labels">Aa Labels</button><button class="float-btn" id="centersButton">◆ Centers</button><button class="float-btn" id="reset">⌂ Reset</button><button class="float-btn" id="settingsButton">⚙ Settings</button><button class="float-btn primary" id="analytics">▤ Analytics</button></div>
<div class="floating settings" id="settingsPanel"><label>Map metric<select id="metric"><option value="cases">Predicted monthly cases</option><option value="rate">Rolling 12-month rate per 100,000</option><option value="hotspot">Gi* hotspot z-score</option><option value="pressure">Transmission-pressure proxy</option><option value="centerNeed">Testing-center need score</option></select></label><label>Playback speed<select id="speed"><option value="1400">Fast</option><option value="2600" selected>Normal</option><option value="4800">Slow</option></select></label><label>Search municipality<input id="search" placeholder="Type municipality name"></label></div>
<div class="floating timeline"><div class="timeline-top"><button class="float-btn primary" id="play">▶ Play</button><strong id="dateLabel"></strong><span id="metricLabel"></span><span class="timeline-status" id="timelineStatus"></span></div><input id="slider" type="range" min="0" max="__MAX_INDEX__" value="0" step="1"></div>
<div class="floating legend"><b id="legendTitle">Predicted monthly cases</b><div class="gradient"></div><div class="legend-labels"><span id="legendLow">Low</span><span id="legendHigh">High</span></div><div class="legend-extra"><span class="legend-ping"></span> Dynamic alert&nbsp;&nbsp; <span class="legend-center"></span> Center candidate<br>White lines: municipality boundaries<br>Gray mask: outside Region XII</div></div>
<div class="drawer" id="drawer"><div class="drawer-head"><h2>arcHIVe Intelligence</h2><button id="closeDrawer">Close</button></div><div class="tabs"><button class="tab-btn active" data-tab="intelligence">Intelligence</button><button class="tab-btn" data-tab="graphs">Graphs</button><button class="tab-btn" data-tab="decomposition">Decomposition</button><button class="tab-btn" data-tab="centers">Testing Centers</button><button class="tab-btn" data-tab="table">Data</button></div>
<div class="tab-panel active" id="tab-intelligence"><div class="card"><h3>Selected municipality</h3><div class="selected-card" id="selectedCard">Click a municipality.</div></div><div class="card"><h3>Regional snapshot</h3><div class="metric-grid" id="regionalMetrics"></div></div><div class="card"><h3>Active alerts</h3><div id="alertList"></div></div><div class="factor-box"><b>Interpretation boundary:</b> “Transmission pressure” combines diagnosed-case rate, the simulated effective infectious pool, estimated new infections, neighboring infectious prevalence, hotspot intensity, treatment coverage, and testing access. It is a population-level planning scenario, not R₀, individual risk, or proof of direct transmission.</div></div>
<div class="tab-panel" id="tab-graphs"><div class="card"><h3>Regional forecast and 95% scenario interval</h3><svg class="chart" id="regionalChart"></svg></div><div class="card"><h3>Selected municipality trend</h3><svg class="chart" id="selectedChart"></svg></div><div class="card"><h3>Current municipality ranking</h3><div class="ranking" id="ranking"></div></div></div>
<div class="tab-panel" id="tab-decomposition"><div class="card"><h3>Time-series decomposition</h3><p class="small">The displayed values are on the log(1+cases) scale. Trend captures the smoothed path, seasonality captures recurring month effects, and residual captures unexplained variation.</p><svg class="chart" id="decompositionChart"></svg></div><div class="metric-grid" id="decompositionMetrics"></div></div>
<div class="tab-panel" id="tab-centers"><div class="card"><h3>Recommended testing-center establishment areas</h3><p class="small">Candidates identify priority municipalities and a representative map point only. Exact sites require the official facility registry, accessibility analysis, staffing, privacy, land, and DOH/LGU approval.</p><div class="ranking" id="centerRanking"></div></div></div>
<div class="tab-panel" id="tab-table"><div class="table-tools"><input id="tableSearch" placeholder="Filter municipality or province"></div><div class="table-wrap"><table class="live-table" id="liveTable"></table></div></div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
const DATA=__PAYLOAD__;let current=0,selected=0,timer=null,labelsVisible=true,centersVisible=true,searchQuery='';
const map=L.map('map',{zoomControl:true,preferCanvas:true,minZoom:5,maxZoom:12});L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'}).addTo(map);
['outsideMaskPane','municipalityPane','provincePane','regionPane','labelPane','pingPane','centerPane'].forEach(name=>map.createPane(name));map.getPane('outsideMaskPane').style.zIndex=350;map.getPane('municipalityPane').style.zIndex=430;map.getPane('provincePane').style.zIndex=470;map.getPane('regionPane').style.zIndex=490;map.getPane('labelPane').style.zIndex=610;map.getPane('pingPane').style.zIndex=650;map.getPane('centerPane').style.zIndex=670;map.getPane('labelPane').style.pointerEvents='none';
L.geoJSON(DATA.outsideMask,{pane:'outsideMaskPane',interactive:false,style:{fillColor:'#4b5563',fillOpacity:.76,color:'#4b5563',weight:0}}).addTo(map);
const layers=[],labels=[],pings=[],centerMarkers=[];const metricNames={cases:'Predicted monthly cases',rate:'Rolling 12-month rate per 100,000',hotspot:'Gi* hotspot z-score',pressure:'Transmission-pressure proxy',centerNeed:'Testing-center need score'};
function values(){return DATA.values[document.getElementById('metric').value][current]}
function extent(arr){const f=arr.filter(v=>Number.isFinite(v));if(!f.length)return[0,1];f.sort((a,b)=>a-b);const q=p=>f[Math.min(f.length-1,Math.max(0,Math.round((f.length-1)*p)))];let lo=q(.03),hi=q(.97);if(hi<=lo)hi=lo+1;return[lo,hi]}
function color(v,lo,hi){const t=Math.max(0,Math.min(1,(v-lo)/(hi-lo||1)));if(t<.5){const p=t*2;return `rgb(${Math.round(16+(253-16)*p)},${Math.round(185+(224-185)*p)},${Math.round(129+(71-129)*p)})`}const p=(t-.5)*2;return `rgb(${Math.round(253+(239-253)*p)},${Math.round(224+(68-224)*p)},${Math.round(71+(68-71)*p)})`}
function fmt(v,d=2){return Number.isFinite(v)?Number(v).toLocaleString(undefined,{maximumFractionDigits:d}):'—'}
function row(i){const v=DATA.values,t=DATA.texts;return{node:DATA.nodes[i],cases:v.cases[current][i],rate:v.rate[current][i],hotspot:v.hotspot[current][i],pressure:v.pressure[current][i],centerNeed:v.centerNeed[current][i],low:v.lower95[current][i],high:v.upper95[current][i],growth:v.growth[current][i],cluster:v.clusterSize[current][i],alert:!!v.alert[current][i],centers:v.centers[current][i],population:v.population[current][i],populationGrowth:v.populationGrowth[current][i],newInfections:v.newInfections[current][i],undiagnosed:v.undiagnosed[current][i],suppressed:v.suppressed[current][i],infectiousPool:v.infectiousPool[current][i],neighborInfectious:v.neighborInfectious[current][i],artCoverage:v.artCoverage[current][i],suppressionCoverage:v.suppressionCoverage[current][i],testingAccess:v.testingAccess[current][i],centersOpened:v.centersOpened[current][i],pendingCenters:v.pendingCenters[current][i],hotspotClass:t.hotspotClass[current][i],moranCluster:t.moranCluster[current][i],pressureLevel:t.pressureLevel[current][i],alertReason:t.alertReason[current][i]}}
function popupHtml(i){const r=row(i);return `<div class="popup-title">${r.node.name}</div><div class="popup-sub">${r.node.province} · PSGC ${r.node.psgc}</div>${r.alert?`<div class="popup-alert">${r.pressureLevel} WATCH · ${r.alertReason}</div>`:''}<div class="popup-grid"><div>Predicted cases<b>${fmt(r.cases)}</b></div><div>95% interval<b>${fmt(r.low)}–${fmt(r.high)}</b></div><div>12-month rate<b>${fmt(r.rate)}</b></div><div>Gi* z-score<b>${fmt(r.hotspot)}</b></div><div>Pressure proxy<b>${fmt(r.pressure,1)}/100</b></div><div>Center need<b>${fmt(r.centerNeed,1)}/100</b></div><div>Hotspot class<b>${r.hotspotClass}</b></div><div>Testing centers<b>${fmt(r.centers,0)}</b></div></div><button class="popup-button" onclick="selectNode(${i},true)">Open detailed analytics</button>`}
function updateMap(){const arr=values(),[lo,hi]=extent(arr);document.getElementById('legendLow').textContent=fmt(lo);document.getElementById('legendHigh').textContent=fmt(hi);layers.forEach((layer,i)=>{const visible=!searchQuery||DATA.nodes[i].name.includes(searchQuery)||DATA.nodes[i].province.toUpperCase().includes(searchQuery);layer.setStyle({fillColor:color(arr[i],lo,hi),fillOpacity:visible?.86:.18,color:'#ffffff',weight:1.15,opacity:visible?1:.45});layer.setPopupContent(popupHtml(i));});pings.forEach(p=>map.removeLayer(p));pings.length=0;DATA.nodes.forEach((node,i)=>{if(DATA.values.alert[current][i]){const icon=L.divIcon({className:'',html:'<div class="outbreak-ping"></div>',iconSize:[17,17],iconAnchor:[8,8]});const marker=L.marker([node.lat,node.lon],{pane:'pingPane',icon,interactive:true}).bindPopup(popupHtml(i)).addTo(map);pings.push(marker)}})}
function updateCenters(){centerMarkers.forEach(m=>centersVisible?m.addTo(map):map.removeLayer(m));document.getElementById('centersButton').textContent=centersVisible?'◆ Centers':'◇ Hidden'}
function selectNode(i,open=false){selected=i;layers[i].openPopup();renderSelected();drawSelectedTrend();drawDecomposition();if(open)openDrawer('intelligence')}
DATA.geojson.features.forEach((feature,i)=>{const layer=L.geoJSON(feature,{pane:'municipalityPane',style:{fillColor:'#10b981',fillOpacity:.86,color:'#fff',weight:1.15},onEachFeature:(f,l)=>{l.bindPopup(popupHtml(i));l.on('click',()=>selectNode(i,false))}}).addTo(map);layers.push(layer.getLayers()[0]);const node=DATA.nodes[i];labels.push(L.marker([node.lat,node.lon],{pane:'labelPane',interactive:false,icon:L.divIcon({className:'municipality-label-icon',html:`<span>${node.name}</span>`,iconSize:[1,1]})}).addTo(map))});
const provinceLayer=L.geoJSON(DATA.provinceGeojson,{pane:'provincePane',interactive:false,style:{fillOpacity:0,color:'#fff',weight:3.2,opacity:.92}}).addTo(map);const regionLayer=L.geoJSON(DATA.regionGeojson,{pane:'regionPane',interactive:false,style:{fillOpacity:0,color:'#fff',weight:5,opacity:1}}).addTo(map);const regionBounds=regionLayer.getBounds();map.fitBounds(regionBounds,{padding:[25,25]});
DATA.recommendations.filter(r=>r.additional>0).forEach(rec=>{const icon=L.divIcon({className:'',html:'<div class="center-marker"></div>',iconSize:[15,15],iconAnchor:[7,7]});const marker=L.marker([rec.lat,rec.lon],{pane:'centerPane',icon}).bindPopup(`<div class="popup-title">Testing-center candidate · ${rec.name}</div><div class="popup-sub">${rec.province}</div><div class="popup-grid"><div>Priority<b>${rec.priority}</b></div><div>Need score<b>${fmt(rec.score,1)}</b></div><div>Current estimate<b>${fmt(rec.currentCenters,0)}</b></div><div>Additional suggested<b>${rec.additional}</b></div></div><p class="small">${rec.method}</p>`);centerMarkers.push(marker);marker.addTo(map)});
function regionalRow(){return DATA.regional[current]||{}}
function renderSelected(){const r=row(selected);document.getElementById('selectedCard').innerHTML=`<b>${r.node.name}</b><br><span class="small">${r.node.province} · ${DATA.dates[current]}</span><div class="metric-grid" style="margin-top:8px"><div class="metric"><span>Predicted diagnoses</span><b>${fmt(r.cases)}</b></div><div class="metric"><span>Estimated new infections</span><b>${fmt(r.newInfections)}</b></div><div class="metric"><span>95% scenario interval</span><b>${fmt(r.low)}–${fmt(r.high)}</b></div><div class="metric"><span>12-month rate</span><b>${fmt(r.rate)}</b></div><div class="metric"><span>Transmission-active pool</span><b>${fmt(r.infectiousPool)}</b></div><div class="metric"><span>Neighbor pressure /100k</span><b>${fmt(r.neighborInfectious)}</b></div><div class="metric"><span>Testing access</span><b>${fmt(100*r.testingAccess,1)}%</b></div><div class="metric"><span>Viral suppression</span><b>${fmt(100*r.suppressionCoverage,1)}%</b></div><div class="metric"><span>Pressure proxy</span><b>${fmt(r.pressure,1)}</b></div><div class="metric"><span>Hotspot</span><b>${r.hotspotClass}</b></div></div><p class="small"><b>Alert:</b> ${r.alertReason}<br><b>Population growth this month:</b> ${fmt(100*r.populationGrowth,3)}%<br><b>ART coverage:</b> ${fmt(100*r.artCoverage,1)}% · <b>Undiagnosed PLHIV:</b> ${fmt(r.undiagnosed)}<br><b>Centers:</b> ${fmt(r.centers,0)} active, ${fmt(r.pendingCenters,0)} pending · <b>Need:</b> ${fmt(r.centerNeed,1)}/100</p>`}
function renderRegional(){const r=regionalRow();document.getElementById('regionalMetrics').innerHTML=`<div class="metric"><span>Reported diagnoses</span><b>${fmt(r.REGIONAL_SCENARIO_CASES)}</b></div><div class="metric"><span>New infections</span><b>${fmt(r.NEW_INFECTIONS_ESTIMATE)}</b></div><div class="metric"><span>Regional population</span><b>${fmt(r.TOTAL_POPULATION,0)}</b></div><div class="metric"><span>Active testing centers</span><b>${fmt(r.ACTIVE_TESTING_CENTERS,0)}</b></div><div class="metric"><span>Undiagnosed PLHIV</span><b>${fmt(r.PLHIV_UNDIAGNOSED)}</b></div><div class="metric"><span>Virally suppressed</span><b>${fmt(r.PLHIV_VIRALLY_SUPPRESSED)}</b></div><div class="metric"><span>Hotspot municipalities</span><b>${fmt(r.HOT_SPOT_MUNICIPALITIES,0)}</b></div><div class="metric"><span>Active alerts</span><b>${fmt(r.ACTIVE_ALERTS,0)}</b></div>`}
function renderAlerts(){const rows=DATA.nodes.map((n,i)=>row(i)).filter(r=>r.alert).sort((a,b)=>b.pressure-a.pressure);document.getElementById('alertList').innerHTML=rows.length?rows.slice(0,18).map(r=>`<div class="alert-row" onclick="selectNode(${r.node.index},false)"><b>${r.node.name}</b> · ${r.pressureLevel}<br>${r.alertReason}<br><span class="small">Pressure ${fmt(r.pressure,1)} · Gi* ${fmt(r.hotspot)}</span></div>`).join(''):'<p class="small">No automatic scenario watch at this month.</p>'}
function renderRanking(){const arr=DATA.nodes.map((n,i)=>row(i)).sort((a,b)=>b.pressure-a.pressure),max=Math.max(...arr.map(r=>r.pressure),1);document.getElementById('ranking').innerHTML=arr.map((r,k)=>`<div class="rank-row ${r.alert?'outbreak':''}" onclick="selectNode(${r.node.index},false)"><div class="rank-number">${k+1}</div><div class="rank-name"><b>${r.node.name}</b><span>${r.node.province}</span></div><div class="rank-value">${fmt(r.pressure,1)}</div><div class="rank-bar-wrap"><div class="rank-bar" style="width:${100*r.pressure/max}%;background:${r.alert?'#ef4444':'#2563eb'}"></div></div></div>`).join('')}
function renderCenterRanking(){const rows=[...DATA.recommendations].sort((a,b)=>b.additional-a.additional||b.score-a.score),max=Math.max(...rows.map(r=>r.score),1);document.getElementById('centerRanking').innerHTML=rows.map((r,k)=>`<div class="rank-row ${r.additional>0?'outbreak':''}"><div class="rank-number">${k+1}</div><div class="rank-name"><b>${r.name}</b><span>${r.province} · +${r.additional} suggested</span></div><div class="rank-value">${fmt(r.score,1)}</div><div class="rank-bar-wrap"><div class="rank-bar" style="width:${100*r.score/max}%;background:${r.additional>0?'#ef4444':'#2563eb'}"></div></div></div>`).join('')}
function renderTable(){const q=document.getElementById('tableSearch').value.toUpperCase().trim(),rows=DATA.nodes.map((n,i)=>row(i)).filter(r=>!q||r.node.name.includes(q)||r.node.province.toUpperCase().includes(q)).sort((a,b)=>b.pressure-a.pressure);document.getElementById('liveTable').innerHTML='<thead><tr><th>Municipality</th><th>Province</th><th>Cases</th><th>Rate</th><th>Gi*</th><th>Hotspot</th><th>Pressure</th><th>Center need</th><th>Alert</th></tr></thead><tbody>'+rows.map(r=>`<tr class="${r.alert?'outbreak':''}" onclick="selectNode(${r.node.index},false)"><td>${r.node.name}</td><td>${r.node.province}</td><td>${fmt(r.cases)}</td><td>${fmt(r.rate)}</td><td>${fmt(r.hotspot)}</td><td>${r.hotspotClass}</td><td>${fmt(r.pressure,1)}</td><td>${fmt(r.centerNeed,1)}</td><td>${r.alert?'YES':'NO'}</td></tr>`).join('')+'</tbody>'}
function svgLine(svgId,seriesList,indexCursor){const svg=document.getElementById(svgId),w=560,h=220,p=30;svg.setAttribute('viewBox',`0 0 ${w} ${h}`);const all=seriesList.flatMap(s=>s.values).filter(Number.isFinite);if(!all.length){svg.innerHTML='';return}let lo=Math.min(...all),hi=Math.max(...all);if(hi<=lo)hi=lo+1;const x=i=>p+(w-2*p)*i/Math.max(DATA.dates.length-1,1),y=v=>h-p-(h-2*p)*(v-lo)/(hi-lo);let html=`<line class="axis" x1="${p}" y1="${h-p}" x2="${w-p}" y2="${h-p}"/><line class="axis" x1="${p}" y1="${p}" x2="${p}" y2="${h-p}"/>`;seriesList.forEach((s,k)=>{const d=s.values.map((v,i)=>`${i?'L':'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');html+=`<path class="chart-line" stroke="${s.color}" d="${d}"/>`});if(Number.isFinite(indexCursor))html+=`<line class="cursor" x1="${x(indexCursor)}" y1="${p}" x2="${x(indexCursor)}" y2="${h-p}"/>`;html+=`<text x="${p}" y="${h-7}">${DATA.dates[0]}</text><text x="${w-p}" y="${h-7}" text-anchor="end">${DATA.dates.at(-1)}</text><text x="4" y="${p+4}">${fmt(hi)}</text><text x="4" y="${h-p}">${fmt(lo)}</text>`;svg.innerHTML=html}
function drawRegionalTrend(){svgLine('regionalChart',[{values:DATA.regional.map(r=>r.REGIONAL_SCENARIO_CASES),color:'#102a43'},{values:DATA.regional.map(r=>r.UPPER_95_SUM),color:'#93c5fd'}],current)}
function drawSelectedTrend(){svgLine('selectedChart',[{values:DATA.values.cases.map(row=>row[selected]),color:'#dc2626'},{values:DATA.values.rate.map(row=>row[selected]),color:'#2563eb'}],current)}
function drawDecomposition(){svgLine('decompositionChart',[{values:DATA.decomposition.trend.map(row=>row[selected]),color:'#102a43'},{values:DATA.decomposition.seasonal.map(row=>row[selected]),color:'#16a34a'},{values:DATA.decomposition.residual.map(row=>row[selected]),color:'#dc2626'}],current);const z=DATA.decomposition.residualZ[current][selected];document.getElementById('decompositionMetrics').innerHTML=`<div class="metric"><span>Trend</span><b>${fmt(DATA.decomposition.trend[current][selected])}</b></div><div class="metric"><span>Seasonal</span><b>${fmt(DATA.decomposition.seasonal[current][selected])}</b></div><div class="metric"><span>Residual</span><b>${fmt(DATA.decomposition.residual[current][selected])}</b></div><div class="metric"><span>Residual z-score</span><b>${fmt(z)}</b></div>`}
function update(){document.getElementById('dateLabel').textContent=DATA.dates[current];const key=document.getElementById('metric').value;document.getElementById('metricLabel').textContent=metricNames[key];document.getElementById('legendTitle').textContent=metricNames[key];document.getElementById('timelineStatus').textContent=`${current+1} / ${DATA.dates.length}`;updateMap();renderSelected();renderRegional();renderAlerts();renderRanking();renderTable();drawRegionalTrend();drawSelectedTrend();drawDecomposition()}
function openDrawer(tab='intelligence'){document.getElementById('drawer').classList.add('open');setTab(tab)}function closeDrawer(){document.getElementById('drawer').classList.remove('open')}function setTab(tab){document.querySelectorAll('.tab-btn').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));document.querySelectorAll('.tab-panel').forEach(p=>p.classList.toggle('active',p.id===`tab-${tab}`));if(tab==='graphs'){drawRegionalTrend();drawSelectedTrend();renderRanking()}if(tab==='decomposition')drawDecomposition();if(tab==='table')renderTable()}
function stop(){if(timer){clearInterval(timer);timer=null;document.getElementById('play').textContent='▶ Play'}}function play(){stop();timer=setInterval(()=>{current=(current+1)%DATA.dates.length;document.getElementById('slider').value=current;update()},Number(document.getElementById('speed').value));document.getElementById('play').textContent='Ⅱ Pause'}
document.getElementById('play').onclick=()=>timer?stop():play();document.getElementById('analytics').onclick=()=>openDrawer();document.getElementById('closeDrawer').onclick=closeDrawer;document.getElementById('settingsButton').onclick=()=>document.getElementById('settingsPanel').classList.toggle('open');document.getElementById('labels').onclick=()=>{labelsVisible=!labelsVisible;document.getElementById('map').classList.toggle('labels-hidden',!labelsVisible);document.getElementById('labels').textContent=labelsVisible?'Aa Labels':'Aa Hidden'};document.getElementById('centersButton').onclick=()=>{centersVisible=!centersVisible;updateCenters()};document.getElementById('reset').onclick=()=>map.fitBounds(regionBounds,{padding:[25,25]});document.getElementById('slider').oninput=e=>{current=+e.target.value;update()};document.getElementById('metric').onchange=update;document.getElementById('speed').onchange=()=>{if(timer)play()};document.getElementById('search').oninput=e=>{searchQuery=e.target.value.toUpperCase().trim();updateMap()};document.getElementById('tableSearch').oninput=renderTable;document.querySelectorAll('.tab-btn').forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
renderCenterRanking();update();
</script></body></html>'''
    html = html.replace("__PAYLOAD__", payload_json).replace("__MAX_INDEX__", str(max(len(dates) - 1, 0)))
    output.write_text(html, encoding="utf-8")
