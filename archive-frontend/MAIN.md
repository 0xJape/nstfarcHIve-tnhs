# Main Dashboard Design Guide

## Purpose

Reuse this design pattern for future AI-assisted public health intelligence platforms.

**Goal:** Make the dashboard feel like an HIV Spatial Intelligence and Decision Support Center, not a CRUD management system.

- Full-screen dark interface
- Map as the main visual element
- Minimal navigation
- HIV risk color visualization
- White municipality boundaries
- Dark glass-like panels
- Large readable KPI numbers
- Small uppercase labels
- Collapsible side panels
- Municipality details appear after map selection
- AI-generated insights integrated throughout the interface

---

# 1. Main Layout

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ ARCHIVE     Region XII Status      Methodology   AI Assistant    Login     │
├───────────────┬──────────────────────────────┬─────────────────────────────┤
│ Intelligence  │                              │ Selected Municipality       │
│ Controls      │                              │ HIV Risk Details            │
│ Legend        │         Full GIS Map         │ AI Summary                  │
│ KPI Cards     │                              │ Forecast                    │
│ Mini Charts   │                              │ Rankings                    │
│ Timeline      │                              │ Recommendations             │
└───────────────┴──────────────────────────────┴─────────────────────────────┘
```

Use three primary regions:

1. Top Navigation
2. Left Intelligence Panel
3. Center GIS Map
4. Right Municipality Detail Panel

The GIS map must always remain the dominant visual element. Side panels exist only to explain and support the map.

---

# 2. Main Map Design

The map should immediately answer:

> **Where are the current and projected HIV risk areas in Region XII?**

### Map Layers

1. Dark basemap
2. Region XII boundary
3. Province boundaries
4. Municipality boundaries
5. Municipality labels
6. HIV risk polygons
7. Risk heatmap
8. HIV hotspot markers
9. HIV testing centers
10. HIV treatment hubs
11. Selected municipality outline

---

### Color System

```text
Very Low Risk      Green
Low Risk           Yellow
Moderate Risk      Orange
High Risk          Red
Critical Risk      Dark Red
No Data            Dark Gray
Healthcare         Cyan
```

Use thin white municipality boundaries.

Province boundaries should be thicker.

Selected municipality should use a bright red outline.

---

# 3. Map Interaction

Required interactions

- Hover municipality → Tooltip
- Click municipality → Open detail panel
- Change visualization metric
- Toggle GIS layers
- Zoom
- Search municipality
- Select forecast month
- Previous month
- Next month
- Automatic timeline playback
- Collapse left panel
- Collapse right panel
- Highlight selected municipality
- Display hotspot indicators
- Display testing centers
- Display treatment hubs

Avoid excessive floating buttons.

Keep controls minimal.

---

# 4. Left Intelligence Panel

The left panel explains the current visualization.

Include

- Dashboard title
- Brief system description
- Visualization selector
- Risk legend
- KPI cards
- AI model information
- Mini charts

Example

```text
ARCHIVE INTELLIGENCE

HIV Surveillance
and Forecasting

MLR-LSTM Spatiotemporal
Decision Support

Visualization Layer

[ HIV Risk ▼ ]

Very Low ━━━━━━━━━━━━━━━━━ Critical

Total HIV Cases          4,182
Predicted Cases            263
High Risk Areas             12
Treatment Hubs              19

Model

Forecast generated using
MLR-LSTM and spatial analysis.

Not intended for diagnosis.
```

Panel should collapse.

The map should always remain the primary focus.

---

# 5. Right Detail Panel

Before municipality selection

```text
SELECTED MUNICIPALITY

Select any municipality
on the map to view
its HIV intelligence profile.
```

After selection

```text
SELECTED MUNICIPALITY

Koronadal City

HIGH RISK

Risk Score             81%

Predicted Cases         96

Trend
Increasing

Hotspot Status
Persistent

Testing Centers
4

Treatment Hubs
2

Forecast
[line chart]

AI Summary

Risk is primarily influenced by
historical incidence and surrounding
high-risk municipalities.

Recommended Action

Increase community testing
and awareness activities.

[ Open Full Analytics ]
```

Only show summary.

More detailed analytics belong in dedicated pages.

---

# 6. Timeline Design

Timeline remains below the map.

```text
‹ January 2025 ━━━━━━━●━━━━━━ December 2026 ›

                 ▶ Play
```

Requirements

- Timeline slider
- Current month
- Previous
- Next
- Play/Pause
- Loading state
- Historical vs Forecast distinction

Animation

1–2 seconds per step.

---

# 7. Layer Control

Compact floating control.

```text
MAP LAYERS

☑ HIV Risk

☑ Predicted Cases

☑ Hotspots

☑ Municipality Boundaries

☑ Municipality Labels

☑ Testing Centers

☑ Treatment Hubs

☑ Healthcare Facilities
```

Do not expose GIS terminology such as GeoJSON or vector tiles.

---

# 8. Municipality Detail Modal

Selecting

"Open Full Analytics"

opens a modal containing

- Municipality
- Province
- Current HIV Cases
- Predicted Cases
- Risk Classification
- Hotspot Status
- AI Explanation
- Historical Trend
- Forecast Graph
- Intervention Priority
- Healthcare Facilities
- Resource Allocation Recommendation

Dark modal.

Red accents.

Avoid information overload.

---

# 9. AI Decision Support

Integrated throughout the dashboard.

Example

```text
AI Summary

Koronadal remains one of the
highest-priority municipalities.

The model projects continued
case growth over the next
three months.

Recommended Actions

• Expand HIV Testing
• Increase Awareness Campaigns
• Deploy Additional Resources
```

---

# 10. Design System

## Background

```css
--bg: #081116;
--panel: #101c22;
--panel-dark: #0c171d;
--border: #2b3b42;
```

## Text

```css
--text: #eef5f6;
--muted: #a7b8bd;
--dim: #82969d;
```

## Colors

```css
--red: #D71920;
--dark-red: #A50F15;
--orange: #FF7A3D;
--yellow: #FFD166;
--green: #00C878;
--cyan: #00B8D9;
```

---

# 11. Responsive Behavior

### Desktop

Three-column layout

Map centered

Panels collapsible

---

### Tablet

Left panel collapsed

Right panel overlays

---

### Mobile

Map occupies full screen

Bottom sheet for municipality details

Floating layer controls

Timeline becomes bottom control

---

# 12. Recommended Frontend Stack

```json
{
  "react": "^19",
  "react-dom": "^19",
  "maplibre-gl": "^6",
  "recharts": "^3"
}
```

Development

```json
{
  "typescript": "^5",
  "vite": "^7",
  "@vitejs/plugin-react": "^5",
  "oxlint": "^1"
}
```

---

# 13. Implementation Order

1. Build dashboard shell
2. Create three-column layout
3. Add MapLibre map
4. Load municipality GeoJSON
5. Apply HIV risk layers
6. Add municipality labels
7. Build Intelligence Panel
8. Build Detail Panel
9. Add map tooltips
10. Add municipality selection
11. Add timeline controls
12. Add layer selector
13. Add charts
14. Add AI summaries
15. Optimize animations and responsiveness

Use static data first.

Connect APIs later.

---

# Design Rule

The GIS map is the heart of ARCHIVE.

Every panel, chart, KPI, AI recommendation, and interaction should help users answer one question:

> **Where are the current and emerging HIV risk areas, and what actions should be taken?**

The map is the main character.

Everything else exists to explain it.