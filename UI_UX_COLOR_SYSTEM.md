# ARCHIVE UI/UX Color System

## Design Direction

ARCHIVE uses an awareness-focused visual system: compassionate, serious, accessible, and action-oriented. Red communicates HIV awareness and urgent action. Charcoal supports trust and professional decision-making. White space keeps health information readable and calm.

Reference palette: **Calm Teal**. Color must communicate care and clarity, never fear or diagnosis.

## Color Tokens

| Token | Hex | Usage |
|---|---|---|
| `--calm-teal` | `#287F82` | Primary brand color, actions, links, supportive highlights |
| `--deep-teal` | `#1F6268` | Hover states, pressed states, accents, depth |
| `--slate` | `#203238` | Navigation, strong text emphasis, high-information surfaces |
| `--pure-white` | `#FFFFFF` | Main page background, high-contrast surfaces |
| `--soft-mist` | `#F5F8F7` | Cards, secondary sections, dividers, muted surfaces |
| `--muted-slate` | `#5F7074` | Body text, icons, secondary controls |
| `--warm-amber` | `#E8B86A` | Focus indicator, time-sensitive emphasis, selected states |

## Semantic Tokens

| Semantic role | Default token |
|---|---|
| Brand | `--calm-teal` |
| Brand hover/active | `--deep-teal` |
| Primary action | `--calm-teal` |
| Secondary action | `--slate` |
| Page background | `--pure-white` |
| Section background | `--soft-mist` |
| Primary text | `--slate` |
| Secondary text | `--muted-slate` |
| Critical alert | Accessible red plus text/icon label |
| Focus indicator | `--warm-amber` |

## Usage Rules

- Use teal for action and trust, not as a risk verdict.
- Use `#203238` for navigation and high-information dashboard areas.
- Use white or soft white behind dense charts, tables, and health guidance.
- Keep body text at strong contrast against its background.
- Never communicate risk level through color alone; pair color with labels, icons, or patterns.
- Reserve amber for focus, selected, or time-sensitive states.
- Use deep teal for hover and pressed states, not as default body text.
- Avoid large solid-red or alarm-colored text blocks; they increase stigma and visual fatigue.

## Core Components

### Navigation

- Background: `--charcoal-black`
- Default text: `--pure-white`
- Active indicator: `--awareness-red`
- Hover state: `--deep-crimson`

### Primary Button

- Background: `--awareness-red`
- Text: `--pure-white`
- Hover: `--deep-crimson`
- Focus ring: `--bright-accent-red`

### Outline Button

- Background: transparent
- Border: `--awareness-red`
- Text: `--awareness-red`
- Hover background: `--awareness-red`
- Hover text: `--pure-white`

### Cards

- Background: `--pure-white` or `--soft-white`
- Text: `--charcoal-black`
- Supporting text: `--dark-gray`
- Border/divider: `#E5E5E5`
- Use icons with labels; do not rely on red icon color alone to convey meaning.

### Hero Section

Use a white or soft-white base with awareness-red accents. Pair strong headline text with one clear action. Photography and ribbon imagery should support—not compete with—readability.

### Dashboard Risk States

Risk colors require accessible secondary indicators:

- Low: neutral or green status plus text label
- Moderate: amber status plus text label
- High: awareness red status plus text label
- Critical: deep crimson status plus text label and alert icon

Do not use the brand red as the only indicator of HIV risk.

## Accessibility Baseline

- Follow WCAG 2.2 AA contrast targets.
- Provide visible keyboard focus states.
- Keep interactive targets at least 44 × 44 CSS pixels where practical.
- Support reduced motion for animated maps, charts, and alerts.
- Use plain language for public health content.
- Provide alt text for awareness imagery and meaningful map graphics.
- Pair chart colors with legends, labels, and tooltips.

## Product Tone

- Compassionate, never stigmatizing.
- Clear, never alarmist.
- Professional for health authorities.
- Reassuring and private for public users.
- Evidence-led when presenting AI output.

## Scope Boundary

This document defines the shared UI/UX direction for ARCHIVE. `arcHIVe-main` supplies backend analytics, forecasting, GIS processing, decision-support logic, generated outputs, and API services. Frontend dashboards, public portal screens, chatbot views, authentication screens, and referral workflows consume this design system.
