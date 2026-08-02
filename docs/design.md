# Design System and Product Experience: Instamart Discovery Engine

## 1. Purpose

This document defines the visual, interaction, motion, component, and responsive design system for the **Instamart Discovery Engine**.

It should be used together with:

- `problemstatement.md` — the original project brief;
- `context.md` — the specific problem definition, research scope, and product surfaces;
- `architecture.md` — application boundaries, frontend architecture, APIs, streaming, and system states;
- `datamodel.md` — entities, statuses, confidence values, lineage, review states, themes, insights, citations, and reports;
- `edgecases.md` — expected UI behaviour for failure, partial, stale, and unusual states;
- `ai_evals.md` — how AI-generated content shown in this design system is evaluated and gated for release.

This file is the source of truth for frontend design decisions.

It intentionally does not redefine backend logic or database schemas. Instead, it specifies how those concepts should be represented to a product manager, researcher, analyst, or reviewer.

---

## 2. Product Experience Definition

The product should feel like an **evidence intelligence workspace** built for serious product research — one that borrows Swiggy's actual visual language (warm orange-led accent, charcoal text, friendly and fast-feeling UI) rather than inventing an independent brand, while remaining functionally a research tool, not a storefront.

It must not feel like:

- a generic admin dashboard;
- a social-listening vanity-metrics tool;
- a chatbot with decorative citations;
- a dense database browser.

It borrows Swiggy's look, not Swiggy's interaction model: no carts, no checkout flows, no storefront browsing metaphors.

The experience should make the following progression visually obvious:

```text
Raw conversations
    → Structured evidence
    → Repeated themes
    → Interpreted insights
    → Product hypotheses
    → Validation actions
```

The defining product promise is:

> Ask difficult discovery questions, understand what the evidence supports, and inspect exactly where every conclusion came from.

---

## 3. Design Direction

### 3.1 Working design concept

The working visual concept is **Signal Lab**.

Signal Lab combines:

- the clarity of a research workspace;
- the confidence of an enterprise analytics product;
- the speed and polish of a modern AI-native application;
- subtle visual references to signals, clusters, threads, and evidence paths.

The design should use movement, layering, and progressive disclosure to show how fragmented public conversations become structured product knowledge.

### 3.2 Emotional qualities

The interface should feel:

- intelligent;
- calm;
- precise;
- transparent;
- responsive;
- premium;
- evidence-led;
- slightly exploratory without becoming playful.

### 3.3 Brand relationship

**Updated 2026-07-27 — explicit brand adoption.** This system now adopts Swiggy's published brand primitives directly, at explicit product request, superseding the earlier "brand-adjacent, independently designed" position below. Background, foreground/charcoal, muted, border, card, and accent colors, the font family, and the shape scale are taken verbatim from Swiggy's own design spec rather than independently designed:

- background `#FFFFFF` / dark `#121212`
- foreground (charcoal) `#282C3F`
- muted `#686B78` / dark `#93959F`
- border `#E9E9EB` / dark `#282C3F`
- card `#FFFFFF` / dark `#1A1A1A`
- accent (brand orange) `#FC8019` — unchanged across light and dark
- font family: Basis Grotesque Pro, falling back to the self-hosted Geist family, then system-ui
- shape: sharp `0px` default radius, `8px` for soft UI rounding, `9999px` full/pill

Discovery green / Evidence blue / Synthesis violet (§7.1) are kept as-is — they're functionally meaningful semantic categories in this research tool, not decorative brand colors, and Swiggy's own spec doesn't define equivalents for them.

Preserve the semantic token names when touching this system further; only primitive values changed here, not component contracts.

---

## 4. Core Design Principles

### 4.1 Evidence before decoration

The visual hierarchy should prioritize:

1. what was found;
2. how strong the evidence is;
3. which sources support it;
4. what contradicts it;
5. what should be validated next.

Charts, motion, gradients, and decorative elements must never obscure these questions.

### 4.2 Traceability should be one interaction away

From every theme, insight, answer finding, or report claim, the user should be able to open:

- supporting evidence;
- contradictory evidence;
- source metadata;
- confidence;
- processing lineage.

Do not hide evidence behind several nested pages.

### 4.3 Distinguish knowledge types visually

The product must consistently differentiate:

- **Observed evidence** — directly stated or deterministically counted;
- **Synthesized insight** — interpretation supported by multiple records;
- **Product hypothesis** — plausible explanation requiring validation.

These states must never rely on color alone.

### 4.4 Confidence is context, not decoration

Confidence should appear close to the object it qualifies.

Do not place one global confidence score at the top while hiding low-confidence subclaims.

### 4.5 Motion explains state

Animation should clarify:

- where an item came from;
- what changed;
- which evidence is connected;
- whether analysis is still running;
- which panel is now in focus;
- how streamed content is being constructed.

Motion should not exist solely to make the interface look expensive.

### 4.6 Progressive disclosure

Default views should be readable in under ten seconds.

Advanced details—model versions, exact score components, lineage, full metadata, prompt and taxonomy versions—should remain accessible through drawers, expandable regions, or dedicated detail views.

### 4.7 Research limitations remain visible

Source concentration, incomplete coverage, low confidence, missing contradictions, and unsupported claims must be represented as first-class product states.

### 4.8 Reuse before invention

Use shadcn/ui primitives, accessible Radix patterns, and selected 21st.dev interaction references where they meet the product need.

Every adopted pattern must be:

- restyled through the project tokens;
- checked for accessibility;
- simplified when it adds unnecessary visual noise;
- implemented as a reusable component;
- documented in the component inventory.

---

## 5. Experience Architecture

## 5.1 Primary navigation

Desktop navigation order:

1. **Overview**
2. **Themes**
3. **Ask**
4. **Evidence**
5. **Validation**
6. **Reports**
7. **Runs**

Secondary utility items:

- dataset and analysis version selector;
- source coverage;
- global command menu;
- help and methodology;
- appearance;
- settings when implemented.

### Navigation labels

Use short, action-oriented labels.

Prefer:

- `Ask`
- `Themes`
- `Evidence`
- `Runs`

Avoid:

- `AI Research Question and Answer Workspace`
- `Theme Analysis Dashboard`
- `Data Ingestion Pipeline Management`

## 5.2 Route structure

Recommended routes:

```text
/
├── /themes
│   └── /themes/[themeId]
├── /ask
│   └── /ask/[sessionId]
├── /evidence
│   └── /evidence/[recordId]
├── /validation
├── /reports
│   └── /reports/[reportId]
├── /runs
│   └── /runs/[runId]
└── /methodology
```

The selected analysis run or dataset version should be represented through URL state or a persistent workspace selector.

## 5.3 Global command menu

Keyboard shortcut:

```text
⌘K / Ctrl+K
```

Command categories:

- navigate to a product surface;
- search themes;
- search evidence;
- open recent research sessions;
- ask a preset question;
- switch dataset version;
- start a permitted ingestion or analysis run;
- create a report.

The command menu should not expose destructive actions without a confirmation step.

---

# Part I — Foundations

## 6. Token Architecture

Use a standard design-system token structure:

```text
Primitives
├── raw color scales
├── raw numeric scales
└── raw font values

Semantic Color
├── light mode
└── dark mode

Spacing
Shape
Typography
Elevation
Motion
Data Visualization
```

Components must use semantic tokens rather than raw primitive values.

### 6.1 Naming convention

Use slash-separated design names and CSS-compatible code aliases.

Figma-style token name:

```text
color/bg/canvas
```

CSS syntax:

```css
var(--color-bg-canvas)
```

Component-specific tokens should only be added when a semantic global token cannot express the intent.

---

## 7. Color System

## 7.1 Color primitives

### Neutral scale (charcoal-anchored)

`neutral/150`, `neutral/600`, and `neutral/800` are exact Swiggy brand values (border, muted, foreground/charcoal — §3.3); the rest are interpolated to match.

```text
neutral/0      #FFFFFF
neutral/25     #FCFCFC
neutral/50     #F7F7F8
neutral/100    #F1F1F3
neutral/150    #E9E9EB   <- Swiggy border
neutral/200    #DCDCDF
neutral/300    #C4C4C9
neutral/400    #9FA0A8
neutral/500    #82838C
neutral/600    #686B78   <- Swiggy muted
neutral/700    #52545F
neutral/800    #282C3F   <- Swiggy foreground/charcoal
neutral/850    #1F2231
neutral/900    #171927
neutral/950    #0F1019
```

### Brand orange

`orange/500` is Swiggy's brand accent `#FC8019` exact, unchanged between light and dark mode; the rest of the ramp is interpolated around it for hover/active/subtle states.

```text
orange/50      #FFF4EC
orange/100     #FFE4CC
orange/200     #FFC898
orange/300     #FFAA63
orange/400     #FD9440
orange/500     #FC8019   <- Swiggy brand accent
orange/600     #E06D0F
orange/700     #B8590D
orange/800     #8F450A
orange/900     #6B3308
```

### Discovery green

```text
green/50       #ECFDF5
green/100      #D1FAE5
green/200      #A7F3D0
green/300      #6EE7B7
green/400      #34D399
green/500      #16A36A
green/600      #0E8254
green/700      #0D6745
green/800      #0D5239
green/900      #0B4330
```

### Evidence blue

```text
blue/50        #EFF6FF
blue/100       #DBEAFE
blue/200       #BFDBFE
blue/300       #93C5FD
blue/400       #60A5FA
blue/500       #3579E8
blue/600       #245FC4
blue/700       #1D4CA0
blue/800       #1E407F
blue/900       #1E3768
```

### Synthesis violet

```text
violet/50      #F5F3FF
violet/100     #EDE9FE
violet/200     #DDD6FE
violet/300     #C4B5FD
violet/400     #A78BFA
violet/500     #8063E8
violet/600     #6947D2
violet/700     #5738AE
violet/800     #49318C
violet/900     #3D2B72
```

### Status colors

```text
amber/50       #FFF8E6
amber/500      #B76A00
amber/700      #854A00

red/50         #FFF0F0
red/500        #D33A3A
red/700        #A52222

cyan/50        #ECFEFF
cyan/500       #0E91A5
cyan/700       #0E6674
```

## 7.2 Semantic color tokens

### Light mode

```text
color/bg/canvas                neutral/0
color/bg/surface               neutral/0
color/bg/surface-subtle        neutral/50
color/bg/surface-muted         neutral/100
color/bg/elevated              neutral/0
color/bg/inverse               neutral/800
color/bg/scrim                 #282C3F at 56%

color/text/primary             neutral/800
color/text/secondary           neutral/600
color/text/tertiary            neutral/500
color/text/disabled            neutral/400
color/text/inverse             neutral/0
color/text/link                blue/700

color/border/subtle            neutral/100
color/border/default           neutral/150
color/border/strong            neutral/300
color/border/focus             blue/500

color/action/primary           orange/500
color/action/primary-hover     orange/600
color/action/primary-active    orange/700
color/action/primary-subtle    orange/50
color/action/on-primary        neutral/0

color/discovery/default        green/600
color/discovery/subtle         green/50
color/discovery/on             neutral/0

color/evidence/default         blue/600
color/evidence/subtle          blue/50
color/evidence/on              neutral/0

color/synthesis/default        violet/600
color/synthesis/subtle         violet/50
color/synthesis/on             neutral/0

color/status/success           green/700
color/status/success-subtle    green/50
color/status/warning           amber/700
color/status/warning-subtle    amber/50
color/status/danger            red/700
color/status/danger-subtle     red/50
color/status/info              blue/700
color/status/info-subtle       blue/50
```

### Dark mode

```text
color/bg/canvas                #121212
color/bg/surface               #1A1A1A
color/bg/surface-subtle        #202020
color/bg/surface-muted         #262626
color/bg/elevated              #1A1A1A
color/bg/inverse               neutral/100
color/bg/scrim                 #000000 at 72%

color/text/primary             #E9E9EB
color/text/secondary           #93959F
color/text/tertiary            #6F7079
color/text/disabled            #4A4B52
color/text/inverse             neutral/800
color/text/link                blue/300

color/border/subtle            #1F1F1F
color/border/default           #282C3F
color/border/strong            #3A3D4D
color/border/focus             blue/400

color/action/primary           orange/500
color/action/primary-hover     orange/400
color/action/primary-active    orange/300
color/action/primary-subtle    #3A2510
color/action/on-primary        neutral/0

color/discovery/default        green/400
color/discovery/subtle         #123326
color/discovery/on             neutral/950

color/evidence/default         blue/400
color/evidence/subtle          #142842
color/evidence/on              neutral/950

color/synthesis/default        violet/400
color/synthesis/subtle         #29203F
color/synthesis/on             neutral/950

color/status/success           green/300
color/status/success-subtle    #123326
color/status/warning           #F2B85B
color/status/warning-subtle    #3B2A0C
color/status/danger            #FF8181
color/status/danger-subtle     #3F1919
color/status/info              blue/300
color/status/info-subtle       #142842
```

## 7.3 Knowledge-type color mapping

Knowledge types must use both a label and a visual marker.

| Knowledge type | Accent | Icon treatment | Label |
|---|---|---|---|
| Observed evidence | Evidence blue | Document or quote | `Observed` |
| Synthesized insight | Synthesis violet | Spark or synthesis nodes | `Synthesized` |
| Product hypothesis | Signal orange | Flask or test icon | `Hypothesis` |
| Contradictory evidence | Amber | Split arrows or alert | `Contradiction` |
| Human accepted | Discovery green | Check | `Reviewed` |

Do not apply full saturated backgrounds to large cards. Use:

- a 3px leading accent;
- subtle icon tile;
- tinted label;
- optional low-opacity background.

## 7.4 Source colors

Source identity should be secondary to research meaning.

Use small neutral source badges with restrained source-specific accents only where useful.

Do not create a rainbow dashboard dominated by source colors.

## 7.5 Color usage rules

- Orange is reserved for primary action, active navigation, and product hypotheses.
- Green represents positive completion, reviewed state, and discovery opportunity.
- Blue represents evidence, links, and inspectable source truth.
- Violet represents AI synthesis and interpreted themes.
- Amber represents uncertainty, contradictions, or partial completion.
- Red is reserved for failure, unsupported claims, destructive actions, or severe warnings.
- Never use red for ordinary negative sentiment alone.

---

## 8. Typography

## 8.1 Font families

Primary UI family (Swiggy brand, §3.3):

```text
Basis Grotesque Pro
```

Self-hosted as five static weights (300/400/500/700/900) from the Arabic-companion cut, which ships full Latin coverage alongside the Arabic script. No italic or variable-font file is available. Falls back to the already-self-hosted Geist family, then system fonts, if the family fails to load.

Monospace family (unchanged — Swiggy's spec doesn't define one):

```text
Geist Mono
```

Fallbacks:

```css
font-family:
  "Basis Grotesque Pro",
  "Geist Variable",
  system-ui,
  -apple-system,
  BlinkMacSystemFont,
  "Segoe UI",
  sans-serif;
```

Use monospace for:

- evidence IDs;
- run IDs;
- prompt or taxonomy versions;
- code and JSON;
- compact numeric comparison labels where alignment matters.

Do not use monospace for long evidence excerpts.

## 8.2 Type scale

Headings use weight 700 with -0.02em letter-spacing per Swiggy's spec (§3.3: "Bold Statements" — heavy weights for headers and numbers); body/label/caption weights are unchanged, since Swiggy's spec doesn't define a full scale for those.

| Token | Size | Line height | Weight | Letter spacing | Primary use |
|---|---:|---:|---:|---:|---|
| `display/lg` | 48px | 54px | 700 | -0.02em | Rare landing or empty-state statement |
| `display/md` | 40px | 46px | 700 | -0.02em | Overview hero |
| `heading/xl` | 32px | 38px | 700 | -0.02em | Page title |
| `heading/lg` | 26px | 32px | 700 | -0.02em | Major section |
| `heading/md` | 21px | 28px | 700 | -0.02em | Card group |
| `heading/sm` | 17px | 24px | 700 | -0.02em | Card title |
| `body/lg` | 16px | 22px | 430 | normal | Main narrative |
| `body/md` | 14px | 20px | 430 | normal | Standard UI |
| `body/sm` | 13px | 18px | 430 | normal | Metadata |
| `label/lg` | 14px | 18px | 560 | normal | Controls |
| `label/md` | 12px | 16px | 560 | normal | Badges and table headers |
| `caption` | 11px | 15px | 520 | normal | Dense metadata |
| `code/sm` | 12px | 18px | 450 | normal | IDs and code |

Base body text (design.md §3.3, applied to `<body>` directly, ahead of any type-scale class) is 14px / line-height 1.4 per Swiggy's spec.

## 8.3 Typography rules

- Use sentence case for headings and controls.
- Use tabular numerals for metrics.
- Keep card titles to two lines.
- Keep table headers short.
- Use maximum line length of approximately 72 characters for narrative text.
- Evidence excerpts may extend to 88 characters per line in detail views.
- Do not use all caps except tiny source or system labels where scanning benefits.
- Avoid gradient text for primary content.

---

## 9. Spacing

Use a 4px base scale.

```text
space/0       0
space/0.5     2
space/1       4
space/1.5     6
space/2       8
space/2.5     10
space/3       12
space/4       16
space/5       20
space/6       24
space/8       32
space/10      40
space/12      48
space/16      64
space/20      80
space/24      96
```

Preferred component spacing:

- icon to label: 8px;
- label to supporting text: 4px;
- metadata items: 8–12px;
- card padding: 16px compact, 20px standard, 24px feature;
- page-section gap: 32–48px;
- dashboard grid gap: 16px;
- large canvas gap: 24px.

---

## 10. Shape

Swiggy's shape scale (§3.3): sharp edges by default, `8px` soft rounding for UI components, `9999px` full/pill — `radius/none` and `radius/full` already matched this; `radius/md` moved `10px → 8px`.

```text
radius/none       0
radius/xs         4
radius/sm         6
radius/md         8
radius/lg         14
radius/xl         18
radius/2xl        24
radius/full       9999
```

Usage:

- small badges: full;
- buttons and inputs: 8px;
- standard cards: 14px;
- major AI composer or insight panel: 18px;
- modal and large drawer: 18px;
- chart tooltip: 8px.

Avoid applying large rounded corners to every container.

---

## 11. Borders

```text
border/width/hairline    1px
border/width/strong      2px
border/width/accent      3px
```

Use borders to express structure before using shadows.

Default cards should have:

- 1px subtle border;
- no visible shadow at rest;
- slight elevation on hover only when clickable.

---

## 12. Elevation

### Light mode

```text
shadow/none
shadow/xs     0 1px 2px rgba(16, 24, 20, 0.05)
shadow/sm     0 6px 18px rgba(16, 24, 20, 0.07)
shadow/md     0 18px 48px rgba(16, 24, 20, 0.12)
shadow/lg     0 28px 80px rgba(16, 24, 20, 0.18)
```

### Dark mode

Use lower-opacity black shadows and stronger borders.

Usage:

- cards: none or `xs`;
- dropdowns: `sm`;
- drawers and dialogs: `md`;
- command menu: `lg`.

Avoid stacked shadows and strong glass blur.

---

## 13. Iconography

Use one consistent outline icon library, preferably **Lucide React**.

Rules:

- 16px for dense metadata;
- 18px for controls;
- 20px for navigation;
- 24px for feature emphasis;
- stroke width 1.75–2px;
- use icons with text for unfamiliar research concepts;
- do not use icons as the only indicator for confidence or review status.

Custom icons may be created for:

- observed evidence;
- synthesis;
- hypothesis;
- contradiction;
- lineage;
- theme cluster.

Custom icons must preserve the same stroke language.

---

## 14. Layout Grid

## 14.1 Desktop

Recommended desktop working range:

```text
1280px–1600px
```

Application shell:

- expanded sidebar: 248px;
- collapsed sidebar: 72px;
- top utility bar: 64px;
- main content max width: 1480px;
- page horizontal padding: 28–40px;
- 12-column content grid;
- grid gap: 16px;
- optional right inspector: 360–440px.

## 14.2 Wide desktop

At widths above 1600px:

- preserve readable content width;
- allow evidence or detail inspectors to remain open;
- increase chart width, not text line length;
- avoid stretching KPI cards indefinitely.

## 14.3 Tablet

At 768–1199px:

- use collapsed rail navigation;
- use 8-column grid;
- transform right inspectors into overlay drawers;
- stack complex comparison panels;
- allow horizontal scrolling only for genuine data tables.

## 14.4 Mobile

At widths below 768px:

- use bottom navigation for top-level destinations where practical;
- move utility navigation into a sheet;
- display one primary column;
- convert tables into record cards;
- use full-screen evidence detail;
- simplify charts;
- keep query composer reachable above the keyboard;
- retain citation and limitation visibility.

The mobile experience should support inspection and lightweight research, even if heavy report construction is desktop-first.

## 14.5 Breakpoints

```text
sm     640px
md     768px
lg     1024px
xl     1280px
2xl    1536px
```

---

# Part II — Application Shell

## 15. Sidebar

### Expanded state

Contains:

- product mark and title;
- primary navigation;
- active dataset selector;
- expandable recent research sessions;
- collapse control;
- methodology and settings at bottom.

### Collapsed state

Contains:

- product symbol;
- icon-only navigation with tooltips;
- compact dataset indicator;
- expand control.

### Active state

Use:

- subtle orange-tinted background;
- orange leading marker;
- primary text;
- filled or emphasized icon.

Do not use a large saturated navigation pill.

### Motion

- width transition: 220ms;
- labels fade and translate 4px;
- content canvas adjusts without a sudden jump;
- respect reduced motion by switching instantly.

---

## 16. Top Utility Bar

Contains:

- breadcrumbs or page context;
- dataset and analysis version;
- global date range when applicable;
- command-menu trigger;
- theme toggle;
- user or environment menu when authentication exists.

The bar should be sticky but visually quiet.

---

## 17. Page Header

Standard structure:

```text
Eyebrow or context
Page title
One-sentence purpose
Primary action
Secondary action
Optional status or coverage warning
```

Do not place four or more primary-looking buttons in a page header.

---

# Part III — Component System

## 18. Component Dependency Order

### Tier 0 — Foundations and atoms

- Icon
- Spinner
- Skeleton
- Progress indicator
- Badge
- Status dot
- Avatar
- Divider
- Tooltip
- Kbd
- Confidence glyph
- Source mark

### Tier 1 — Controls

- Button
- Icon button
- Input
- Textarea
- Search field
- Select
- Combobox
- Multi-select
- Checkbox
- Radio group
- Switch
- Tabs
- Segmented control
- Date-range picker
- Slider
- Pagination

### Tier 2 — Navigation and overlays

- Sidebar item
- Breadcrumb
- Dropdown menu
- Context menu
- Popover
- Sheet
- Drawer
- Dialog
- Command menu
- Toast

### Tier 3 — Product data components

- Metric card
- Coverage card
- Theme card
- Theme row
- Insight card
- Evidence card
- Evidence excerpt
- Citation chip
- Confidence indicator
- Knowledge-type badge
- Source badge
- Taxonomy chip
- Warning banner
- Contradiction block
- Lineage trail
- Score breakdown
- Run status card
- Run stage stepper
- Validation metric card
- Evaluation matrix
- Report selection card

### Tier 4 — Product composites

- Filter toolbar
- Research question composer
- Streamed answer
- Evidence inspector
- Theme inspector
- Insight detail panel
- Validation review panel
- Report outline editor
- Pipeline run monitor
- Empty-state canvas

---

## 19. Buttons

Variants:

```text
Style:
- primary
- secondary
- outline
- ghost
- destructive
- link

Size:
- sm
- md
- lg
- icon-sm
- icon-md

State:
- default
- hover
- active
- focus
- disabled
- loading
```

Guidelines:

- primary button uses signal orange;
- one primary button per local action group;
- loading state preserves button width;
- destructive actions require explicit language;
- icon-only buttons require accessible labels and tooltips;
- minimum target size: 40×40px, preferably 44×44px on touch devices.

---

## 20. Inputs and Query Composer

## 20.1 Standard inputs

Height:

- compact: 36px;
- default: 40px;
- spacious: 44px.

Focus treatment:

- 2px focus ring;
- no layout shift;
- error remains visible after blur until corrected.

## 20.2 Research question composer

The composer is a product-defining component.

Desktop structure:

```text
Question textarea
├── active filter summary
├── optional preset prompt chips
├── evidence scope selector
├── submit action
└── keyboard hint
```

States:

- empty;
- typing;
- ready;
- planning;
- retrieving;
- generating;
- validating;
- completed;
- rate limited;
- failed.

Visual behaviour:

- starts as a compact elevated surface;
- expands vertically as the question grows;
- active filters appear as removable chips;
- submit action transitions to a cancel or stop control during generation;
- streamed stage labels appear beneath the field;
- the composer remains visible while reading the answer.

Do not use an oversized glowing orb or generic AI sparkle as the central interaction.

---

## 21. Badges and Status Indicators

Use badges for categorical information and indicators for dynamic status.

### Badge families

- source;
- taxonomy;
- knowledge type;
- review state;
- confidence;
- sentiment;
- evidence role;
- run stage.

### Confidence treatment

Recommended mapping:

```text
High       0.80–1.00
Medium     0.55–0.79
Low        below 0.55
Unscored   no numeric confidence
```

The API remains authoritative if thresholds are configured differently.

Confidence display should include:

- text label;
- optional numeric score;
- tooltip explaining what confidence refers to.

Do not use a signal-strength icon alone.

---

## 22. Cards

## 22.1 Standard card anatomy

```text
Header
├── title
├── status or type
└── optional action

Primary content

Supporting metadata

Optional footer
```

Clickable cards:

- use hover border and 1–2px lift;
- use pointer cursor;
- provide focus-visible style;
- make the full card clickable only if nested controls do not conflict.

## 22.2 Metric card

Contains:

- metric label;
- value;
- change or comparison;
- timeframe;
- inspect action when underlying records exist.

Avoid giant numbers without context.

## 22.3 Theme card

Required content:

- theme name;
- theme type;
- short summary;
- eligible record count;
- record share;
- confidence;
- opportunity score;
- source breadth;
- trend indicator;
- representative evidence preview;
- review state where applicable.

The card should not show every available metric at once.

## 22.4 Insight card

Required content:

- knowledge-type label;
- title;
- finding or implication;
- confidence;
- evidence count;
- contradiction indicator;
- validation recommendation for hypotheses;
- add-to-report action.

## 22.5 Evidence card

Required content:

- excerpt;
- source;
- date;
- rating when available;
- relevant labels;
- evidence role;
- link to full detail;
- selection or review state where appropriate.

The excerpt must remain readable and should not be visually dominated by metadata.

---

## 23. Tables and Dense Lists

Use tables for:

- evidence records;
- run history;
- validation results;
- metric comparisons;
- review queues.

Requirements:

- sticky header;
- clear row hover;
- keyboard navigation where practical;
- visible selection;
- column visibility control for wide tables;
- density toggle only if genuinely necessary;
- pagination or virtualization for large datasets;
- preserved filters in URL state.

Never hide critical evidence text in a tooltip.

At mobile widths, convert evidence rows into stacked cards.

---

## 24. Filters

## 24.1 Filter toolbar

Common dimensions:

- source;
- date range;
- sentiment;
- category;
- journey stage;
- exploration barrier;
- confidence;
- review status;
- evidence role.

Toolbar behaviour:

- primary filters remain visible;
- advanced filters open a popover or side sheet;
- applied filters appear as removable chips;
- include `Clear all`;
- update results without a full page reload;
- persist filters in URL state;
- announce result count changes to assistive technology.

## 24.2 Facet counts

Facet counts should reflect the active dataset and other applied filters.

Disabled facet values should explain why they are unavailable.

---

## 25. Evidence and Citation Components

## 25.1 Citation chip

Display format:

```text
E12
T04
I07
```

Where:

- `E` = evidence record;
- `T` = theme;
- `I` = insight.

Interaction:

- hover or focus shows a concise preview;
- click opens the evidence inspector;
- selected citation highlights the matching finding and evidence;
- chips remain readable in printed or exported output.

## 25.2 Evidence inspector

Desktop:

- right-side panel, 400px default;
- resizable within a safe range;
- persists while moving between citations.

Contains:

1. redacted evidence text;
2. source and publication metadata;
3. labels;
4. theme memberships;
5. insight relationships;
6. lineage;
7. source link;
8. review actions where permitted.

Mobile:

- full-screen sheet;
- sticky close and next/previous controls.

## 25.3 Lineage trail

Represent lineage as a compact vertical or horizontal path:

```text
Source item
→ Feedback record
→ Classification
→ Theme
→ Insight
→ Answer or report
```

Each step can expand for IDs, versions, and timestamps.

Do not show a complex node graph by default.

---

## 26. Warnings and Limitations

Warning types:

- source concentration;
- low confidence;
- partial processing;
- stale analysis;
- unsupported claim;
- missing contradiction;
- incomplete collection;
- demographic inference risk;
- model rate limit;
- removed evidence.

Treat warnings as structured content, not toast-only messages.

Severity pattern:

- info: blue;
- caution: amber;
- error or unsupported: red;
- resolved or reviewed: green.

Warnings that qualify an insight or answer must appear within the same reading context.

---

# Part IV — Product Surfaces

## 27. Overview

### 27.1 Objective

Answer:

> What is the current state of the dataset, what is emerging, and where should the researcher look next?

### 27.2 Desktop layout

```text
Page header
Coverage and limitation banner
KPI strip
├── analyzed records
├── active sources
├── analysis coverage
└── low-confidence share

Main grid
├── Emerging themes
├── Discovery barriers
├── Source and time coverage
└── Recent research activity

Bottom section
├── Top insights
├── Processing health
└── Suggested questions
```

### 27.3 Hero treatment

Use a restrained overview introduction rather than a marketing landing page.

Optional line:

> Understand what keeps users inside familiar categories—and what gives them confidence to explore.

Include:

- selected dataset;
- publication period;
- last analysis time;
- coverage status.

### 27.4 Signature visualization: Signal field

A compact interactive visualization may represent top themes as nodes sized by record count and positioned by semantic similarity.

Rules:

- maximum 12 visible nodes;
- selected node opens theme detail;
- animation settles quickly;
- list fallback is always available;
- no physics motion that keeps moving indefinitely;
- do not imply exact spatial meaning beyond semantic proximity.

---

## 28. Theme Explorer

### 28.1 Objective

Help the researcher rank, compare, filter, and inspect recurring themes.

### 28.2 Layout

Desktop:

```text
Page header and view controls
Filter toolbar
Summary strip
Theme list or card grid
Persistent optional comparison tray
Evidence inspector
```

Views:

- ranked list;
- visual grid;
- comparison mode.

Default to ranked list because it supports serious analysis.

### 28.3 Theme row

Columns or regions:

- rank;
- theme and summary;
- type;
- count and share;
- severity;
- confidence;
- source breadth;
- trend;
- opportunity score;
- review state.

### 28.4 Theme comparison

Allow up to three themes.

Compare:

- count;
- share;
- source mix;
- sentiment;
- severity;
- date trend;
- journey stages;
- barriers;
- evidence examples;
- contradictions.

Use aligned charts and consistent scales.

---

## 29. Theme Detail

### 29.1 Header

Contains:

- theme name;
- theme type;
- summary;
- status;
- confidence;
- record count and share;
- add-to-report action;
- review action.

### 29.2 Content sections

1. **What users are saying**
2. **Why this theme matters**
3. **Evidence distribution**
4. **Representative evidence**
5. **Contradictory evidence**
6. **Related insights**
7. **Segments and contexts**
8. **Method and lineage**

### 29.3 Sticky local navigation

Use anchored section navigation for long pages.

---

## 30. Ask Workspace

### 30.1 Objective

Provide evidence-grounded research answers with transparent reasoning boundaries.

### 30.2 Initial state

Show:

- concise product explanation;
- preset research questions;
- recent sessions;
- active dataset and filters;
- question composer.

Preset questions should map to the research brief:

- Why do users return to the same categories?
- What prevents exploration of unfamiliar categories?
- How do users discover products today?
- What information reduces risk before trial?
- Which signals indicate willingness to experiment?
- What unmet needs repeat across sources?

### 30.3 Answer structure

```text
Answer summary

Findings
├── observed evidence
├── synthesized insights
└── product hypotheses

Contradictions

Limitations

Suggested validation

Evidence tray
```

### 30.4 Streamed answer behaviour

Stages:

```text
Planning question
Searching structured evidence
Retrieving related themes
Checking contradictions
Writing findings
Validating citations
```

The stage indicator should update without distracting from streamed text.

Use a subtle moving progress line or stage stepper.

Do not fake precise percentages for model generation unless the backend provides them.

### 30.5 Finding block

Each finding includes:

- type;
- atomic statement;
- confidence;
- citations;
- optional supporting metric;
- support warning;
- inspect action.

Unsupported findings should not appear as ordinary successful content.

### 30.6 Follow-up questions

Follow-ups preserve:

- session;
- dataset;
- filters;
- referenced themes;
- evidence scope.

Show inherited context as removable chips.

---

## 31. Evidence Explorer

### 31.1 Objective

Allow fast search, filtering, inspection, and quality review of canonical feedback.

### 31.2 Desktop layout

```text
Search and filter toolbar
Result count and active filters
Evidence table or list
Right-side evidence inspector
```

### 31.3 Evidence row

Contains:

- source;
- excerpt;
- publication date;
- rating;
- sentiment;
- key labels;
- theme count;
- evidence role;
- confidence or quality warning.

### 31.4 Search

Search should:

- highlight matching text;
- support keyword and semantic modes if available;
- explain which mode is active;
- maintain source and taxonomy filters.

---

## 32. Validation Workspace

### 32.1 Objective

Make research quality inspectable and actionable.

### 32.2 Sections

1. **Classification quality**
2. **Retrieval quality**
3. **Theme quality**
4. **Grounding quality**
5. **Human review queue**

### 32.3 Summary cards

Show:

- precision;
- recall;
- F1;
- unsupported-label rate;
- citation support rate;
- source diversity;
- theme coverage;
- outlier rate.

Every metric should include:

- sample size;
- dataset version;
- evaluation date;
- explanation;
- target or reference where defined.

### 32.4 Review queue

Review items should clearly present:

- model output;
- evidence;
- confidence;
- expected action;
- accept, edit, reject, or second review;
- audit history.

Do not place accept and reject actions too close without clear distinction.

---

## 33. Report Builder

### 33.1 Objective

Convert selected themes and insights into an executive-ready, evidence-linked report.

### 33.2 Desktop layout

```text
Left: available themes and insights
Center: report canvas
Right: section settings and evidence
```

### 33.3 Report canvas

Supports:

- executive summary;
- scope and coverage;
- key themes;
- key insights;
- opportunity areas;
- contradictions;
- limitations;
- validation plan;
- methodology;
- appendix.

### 33.4 Interaction

- add via explicit button or drag and drop;
- show exact insertion position;
- preserve keyboard alternative to drag and drop;
- lock manually edited sections;
- show whether content is generated or human edited;
- warn when selected evidence is removed or stale.

### 33.5 Export preview

Provide:

- Markdown preview;
- PDF-ready preview;
- evidence footnotes;
- limitations section;
- page-break hints.

---

## 34. Runs Workspace

### 34.1 Objective

Make collection and analysis progress understandable without exposing raw infrastructure complexity.

### 34.2 Run list

Columns:

- run name;
- type;
- source or dataset;
- status;
- progress;
- record counts;
- cost estimate;
- start time;
- duration;
- warning count.

### 34.3 Run detail

Show:

- stage stepper;
- processed, skipped, failed;
- connector or model warnings;
- retryable failures;
- cost;
- version snapshots;
- child jobs;
- safe logs;
- cancel or retry action where allowed.

### 34.4 Progress motion

Use:

- deterministic progress bar when totals are known;
- looping indeterminate track when totals are unknown;
- stage completion checkmarks;
- subtle number transitions.

Do not animate full cards continuously.

---

# Part V — Data Visualization

## 35. Visualization Principles

### 35.1 Every chart must answer a question

A chart title should communicate meaning.

Prefer:

> Exploration barriers are concentrated around product trust and information gaps

Avoid:

> Barriers by type

### 35.2 Underlying data must be inspectable

Every chart supports at least one:

- hover tooltip;
- click-to-filter;
- open evidence;
- view table;
- download data where appropriate.

### 35.3 Use deterministic scales

- show zero baselines for bar charts unless clearly justified;
- preserve comparable scales in comparison views;
- label sample size;
- show missing data;
- do not interpolate unavailable periods;
- distinguish count from percentage.

### 35.4 Recommended chart library

Recommended first choice:

```text
Recharts
```

Reason:

- strong React compatibility;
- accessible customization;
- adequate for standard analytical charts;
- easy token integration;
- predictable with Framer Motion wrappers.

Use custom SVG or Canvas only for the Signal Field or specialized lineage views.

### 35.5 Chart types

Use:

- horizontal bars for ranked themes;
- line charts for time trends;
- stacked bars for source or sentiment distribution;
- dot plots for score comparison;
- heatmaps for taxonomy intersections;
- scatter plots for frequency versus actionability;
- compact sparklines for trend preview.

Avoid:

- 3D charts;
- gauges for ordinary metrics;
- large donut charts with many segments;
- radar charts for critical decisions;
- animated particle backgrounds.

---

## 36. Data Visualization Tokens

```text
data/categorical/1     blue/500
data/categorical/2     violet/500
data/categorical/3     green/500
data/categorical/4     orange/500
data/categorical/5     cyan/500
data/categorical/6     amber/500
```

Sequential scales should be created separately for:

- count;
- confidence;
- severity;
- opportunity.

Semantic data colors should override category colors:

- low confidence: amber;
- unsupported: red;
- reviewed: green;
- evidence: blue;
- synthesis: violet;
- hypothesis: orange.

Patterns, labels, or symbols must supplement color where categories could be confused.

---

# Part VI — Motion System

## 37. Motion Philosophy

Motion should support three jobs:

1. **Orientation** — where did the content come from?
2. **Continuity** — what changed while the user stayed in context?
3. **Feedback** — did the system receive, process, or complete the action?

The product should feel fluid, not theatrical.

---

## 38. Motion Tokens

### 38.1 Durations

```text
motion/duration/instant     80ms
motion/duration/fast        140ms
motion/duration/standard    220ms
motion/duration/slow        360ms
motion/duration/reveal      520ms
```

### 38.2 Easing

```text
motion/easing/standard
cubic-bezier(0.20, 0.80, 0.20, 1)

motion/easing/enter
cubic-bezier(0.16, 1, 0.30, 1)

motion/easing/exit
cubic-bezier(0.40, 0, 1, 1)

motion/easing/linear
linear
```

### 38.3 Spring presets

```ts
motionSpring.snappy = {
  type: "spring",
  stiffness: 420,
  damping: 34,
  mass: 0.75
}

motionSpring.standard = {
  type: "spring",
  stiffness: 330,
  damping: 30,
  mass: 0.85
}

motionSpring.gentle = {
  type: "spring",
  stiffness: 220,
  damping: 28,
  mass: 1
}
```

---

## 39. Motion Patterns

### 39.1 Page transition

- content fades from 0 to 1;
- translates 6px upward;
- duration 220ms;
- page header enters before data regions;
- do not animate the persistent shell.

### 39.2 List and card reveal

- stagger maximum: 30ms;
- maximum staggered items: 8;
- remaining items appear immediately;
- translate no more than 8px.

### 39.3 Inspector transition

- desktop panel slides 24px from right and fades;
- background content remains stable;
- selected citation receives a temporary highlight;
- close returns focus to originating element.

### 39.4 Filter changes

Use layout animation to reposition result summaries.

Do not animate every row when a large result set updates. Fade the list container or animate only changed top items.

### 39.5 Metric updates

Use number interpolation for short, meaningful updates only.

Do not animate from zero on every page load.

### 39.6 Answer streaming

- text appears as natural token or sentence chunks;
- citations animate in when validated;
- unvalidated partial citations are not shown as final;
- completion changes stage indicator to a resolved state;
- if validation adds a warning, the warning enters beside the affected finding.

### 39.7 Theme-to-evidence transition

When opening evidence from a theme:

- maintain selected theme context;
- animate the evidence inspector from the citation or excerpt region;
- highlight evidence role;
- avoid full-page transition unless the user requests detail view.

### 39.8 Drag and drop

Report builder motion should:

- lift selected item 2–4px;
- show insertion line;
- animate neighbouring sections through layout transitions;
- provide non-drag controls.

### 39.9 Celebration

Do not use confetti.

A completed analysis run may use:

- brief green progress resolution;
- check icon draw;
- subtle success glow under 600ms.

---

## 40. Reduced Motion

Respect:

```css
@media (prefers-reduced-motion: reduce)
```

Reduced-motion behaviour:

- remove transforms and parallax;
- disable animated node physics;
- replace spring transitions with short fades;
- stop looping decorative motion;
- retain deterministic progress updates;
- avoid smooth scrolling that cannot be disabled;
- ensure streamed content remains readable.

Provide an in-product motion preference only if the application later needs more control than the system setting.

---

# Part VII — States and Feedback

## 41. Loading States

### Initial page loading

Use structural skeletons matching the final layout.

Do not show a centered spinner for full-page data views.

### Incremental loading

- preserve existing data;
- show loading indicator near the region being refreshed;
- use optimistic state only for safe, reversible actions.

### AI processing

Display the current known stage.

Do not claim:

- exact completion percentage without backend support;
- that a model is “thinking” in a human sense;
- that evidence is validated before validation completes.

---

## 42. Empty States

### Empty dataset

Explain:

- no source data has been loaded;
- which connectors are supported;
- what the first action does;
- expected record scope where appropriate.

Primary action:

```text
Start first ingestion
```

### Empty filtered results

Show:

- active filters;
- clear-filter action;
- optional suggested broader filters.

Do not use the same illustration as the empty dataset state.

### Empty research session

Show preset questions and a focused composer.

### Empty report

Show report structure suggestions and available insights.

---

## 43. Partial and Degraded States

Examples:

- some sources unavailable;
- classification incomplete;
- embeddings complete but themes pending;
- answer generated with citation warnings;
- report includes stale evidence;
- evaluation sample too small.

Use an inline status banner and affected-region markers.

The rest of the product should remain usable when safe.

---

## 44. Error States

Error content should answer:

1. What failed?
2. What remains available?
3. Is retry safe?
4. Will retry cost money?
5. Where can details be inspected?

Example:

```text
Reddit collection paused

The connector was rate limited after collecting 684 records.
Existing records are available for analysis.

[Retry later] [View run details]
```

Avoid:

```text
Something went wrong.
```

---

## 45. Rate-Limited AI State

Show:

- affected task;
- whether partial results were saved;
- safe retry state;
- expected next action without inventing time estimates;
- alternative access to existing evidence.

Do not automatically repeat expensive requests indefinitely.

---

## 46. Toasts

Use toasts only for transient confirmation:

- copied citation;
- filter saved;
- insight added to report;
- export started;
- review saved.

Use inline surfaces for errors or warnings that affect interpretation.

---

# Part VIII — Accessibility

## 47. Accessibility Standard

Target:

```text
WCAG 2.2 AA
```

## 47.1 Contrast

- normal text: at least 4.5:1;
- large text: at least 3:1;
- interactive boundaries and focus indicators: at least 3:1;
- chart series must remain distinguishable in color-vision-deficiency simulations.

## 47.2 Keyboard

All functionality must support keyboard operation.

Required patterns:

- visible focus;
- logical tab order;
- escape closes overlays;
- arrow navigation in menus, tabs, and command menu;
- focus restoration after closing a drawer or dialog;
- skip link to main content;
- no drag-only report interaction.

## 47.3 Screen readers

- use semantic headings;
- label icon-only controls;
- announce loading and result-count changes;
- provide text summaries for charts;
- make citation chips descriptive;
- label confidence and evidence roles explicitly;
- expose answer streaming through polite live regions without announcing every token.

## 47.4 Touch

Minimum target:

```text
44×44px
```

Dense desktop controls may visually appear smaller while retaining adequate clickable area.

## 47.5 Text resizing

The interface must remain usable at 200% browser zoom.

Avoid fixed-height evidence cards that clip content.

## 47.6 Color independence

No status may depend on color alone.

Use:

- icon;
- label;
- border or pattern;
- text.

## 47.7 Motion and cognition

- respect reduced motion;
- avoid flashing;
- avoid continuously moving data;
- keep animation under five seconds unless user controlled;
- use plain language for methodology warnings;
- allow dense metadata to be collapsed.

---

# Part IX — Content Design

## 48. Voice and Tone

The product voice should be:

- precise;
- neutral;
- direct;
- transparent;
- non-judgmental;
- product-oriented.

Avoid anthropomorphizing the AI.

Prefer:

> The available evidence suggests…

Avoid:

> I strongly believe users feel…

Prefer:

> This hypothesis requires behavioural validation.

Avoid:

> This proves users do not trust the category.

---

## 49. Terminology

Use these canonical terms:

| Use | Avoid |
|---|---|
| Evidence record | Comment data point |
| Theme | Topic bucket |
| Insight | AI conclusion |
| Product hypothesis | Fact |
| Supporting evidence | Proof |
| Contradictory evidence | Negative proof |
| Source coverage | Data completeness |
| Analysis run | AI job |
| Human reviewed | Verified by AI |
| Low confidence | Weak AI |

## 49.1 Confidence language

Use:

- high confidence;
- medium confidence;
- low confidence;
- not scored.

Do not use:

- 92% true;
- almost certain;
- guaranteed.

## 49.2 Metric labels

Every metric should identify:

- unit;
- denominator where relevant;
- timeframe;
- filter scope.

---

# Part X — Implementation Guidance

## 50. Frontend Stack

Required:

- Vite;
- React;
- React Router;
- TypeScript strict mode;
- Tailwind CSS;
- shadcn/ui-style components;
- Radix accessibility patterns;
- Framer Motion;
- Lucide React;
- Recharts;
- typed API client;
- query caching layer compatible with the architecture.

Recommended:

```text
TanStack Query
```

Use server rendering for stable initial summaries and client components for:

- filters;
- drawers;
- streaming;
- motion;
- query composer;
- live run progress;
- report editing.

---

## 51. shadcn/ui Usage Rules

Use shadcn/ui as a component foundation, not as the final visual identity.

Required adaptations:

- map all colors to semantic CSS variables;
- update radius and elevation;
- define density variants;
- add product-specific states;
- standardize icon sizes;
- preserve Radix keyboard behaviours;
- avoid copying demo page styling directly.

Components likely reusable with adaptation:

- Button;
- Badge;
- Card;
- Dialog;
- Sheet;
- Tabs;
- Select;
- Dropdown Menu;
- Command;
- Tooltip;
- Popover;
- Accordion;
- Scroll Area;
- Table;
- Skeleton;
- Alert;
- Toast.

---

## 52. 21st.dev Usage Rules

21st.dev may be used for:

- inspiration;
- advanced interaction patterns;
- polished compositional examples;
- motion references;
- command palettes;
- animated list transitions;
- empty-state composition;
- AI composer patterns.

Before adoption, every component must pass:

1. Does it solve a defined product need?
2. Can it use the project tokens?
3. Does it meet accessibility requirements?
4. Does it avoid unnecessary dependency weight?
5. Can it be maintained by the project?
6. Is it visually consistent with existing components?
7. Does it work with reduced motion?
8. Is there already a shadcn or internal equivalent?

Do not paste several unrelated 21st.dev components into the same product.

---

## 53. Framer Motion Architecture

Create shared motion utilities:

```text
frontend/components/motion/
├── motion-tokens.ts
├── fade-in.tsx
├── stagger-list.tsx
├── layout-group.tsx
├── animated-number.tsx
├── presence-panel.tsx
├── streaming-reveal.tsx
└── reduced-motion.ts
```

Use central variants.

Avoid defining arbitrary easing and durations inside individual feature components.

Example:

```ts
export const motionTokens = {
  duration: {
    instant: 0.08,
    fast: 0.14,
    standard: 0.22,
    slow: 0.36,
    reveal: 0.52,
  },
  ease: {
    standard: [0.2, 0.8, 0.2, 1],
    enter: [0.16, 1, 0.3, 1],
    exit: [0.4, 0, 1, 1],
  },
}
```

---

## 54. CSS Token Skeleton

Recommended semantic variable shape:

```css
:root {
  --color-bg-canvas: #ffffff;
  --color-bg-surface: #ffffff;
  --color-bg-surface-subtle: #f7f7f8;
  --color-text-primary: #282c3f;
  --color-text-secondary: #686b78;
  --color-border-default: #e9e9eb;

  --color-action-primary: #fc8019;
  --color-action-primary-hover: #e06d0f;
  --color-action-on-primary: #ffffff;

  --color-evidence: #245fc4;
  --color-synthesis: #6947d2;
  --color-discovery: #0e8254;
  --color-warning: #854a00;
  --color-danger: #a52222;

  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 14px;
  --radius-xl: 18px;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;

  --shadow-xs: 0 1px 2px rgb(16 24 20 / 0.05);
  --shadow-sm: 0 6px 18px rgb(16 24 20 / 0.07);
  --shadow-md: 0 18px 48px rgb(16 24 20 / 0.12);
}

.dark {
  --color-bg-canvas: #121212;
  --color-bg-surface: #1a1a1a;
  --color-bg-surface-subtle: #202020;
  --color-text-primary: #e9e9eb;
  --color-text-secondary: #93959f;
  --color-border-default: #282c3f;

  --color-action-primary: #fc8019;
  --color-action-primary-hover: #fd9440;
  --color-action-on-primary: #ffffff;

  --color-evidence: #60a5fa;
  --color-synthesis: #a78bfa;
  --color-discovery: #34d399;
  --color-warning: #f2b85b;
  --color-danger: #ff8181;
}
```

The production token file should include all semantic states, not only this abbreviated example.

---

## 55. Component Folder Structure

```text
frontend/
├── components/
│   ├── ui/
│   ├── layout/
│   ├── motion/
│   ├── data-viz/
│   └── feedback/
├── features/
│   ├── overview/
│   ├── themes/
│   ├── research-query/
│   ├── evidence/
│   ├── validation/
│   ├── reports/
│   └── pipeline-runs/
└── styles/
    ├── tokens.css
    ├── typography.css
    ├── globals.css
    └── print.css
```

Product-specific components should not be placed in `components/ui`.

---

## 56. Component Contracts and Variants

Every reusable component should document:

- purpose;
- anatomy;
- variants;
- states;
- accessibility;
- data contract;
- motion;
- responsive behaviour;
- examples;
- anti-patterns.

Avoid variant explosion.

If:

```text
Size × Style × State × Density
```

creates an unmanageable matrix, split internal building blocks from the parent composition.

Examples:

- `EvidenceCard` should compose `SourceBadge`, `EvidenceRole`, and `ConfidenceIndicator`.
- `RunStageStepper` should compose reusable `RunStageItem`.
- `StreamedAnswer` should compose `AnswerFinding`, `CitationChip`, and `AnswerWarning`.
- `ThemeRow` and `ThemeCard` should share a `ThemeSummary` data presentation primitive.

---

# Part XI — Figma Design-System Structure

## 57. Recommended Figma Pages

```text
00 Cover
01 Getting Started
02 Foundations
   ├── Color
   ├── Typography
   ├── Spacing
   ├── Shape
   ├── Elevation
   ├── Motion
   └── Data visualization
---
10 Components — Foundations
11 Components — Inputs
12 Components — Navigation
13 Components — Data display
14 Components — Evidence
15 Components — AI and research
16 Components — Feedback and states
---
20 Patterns
   ├── Filtering
   ├── Evidence inspection
   ├── Streamed answer
   ├── Human review
   ├── Run progress
   └── Report building
---
30 Screens — Desktop
31 Screens — Tablet
32 Screens — Mobile
---
90 Playground
99 Archive
```

## 57.1 Variable collections

Recommended:

```text
Primitives
Semantic Color
Spacing
Shape
Typography Primitives
Typography
Elevation
Motion
Data Visualization
```

Modes:

- Semantic Color: Light, Dark;
- other collections: Value;
- optional future mode: High Contrast.

## 57.2 Component naming

```text
Button
Input
Badge
Card
Theme Card
Insight Card
Evidence Card
Citation Chip
Confidence Indicator
Answer Finding
Run Stage
Warning Banner
```

Variant format:

```text
Size=Medium, Style=Primary, State=Default
```

Internal helper components:

```text
__EvidenceMetadata
__ThemeMetric
__RunStageConnector
```

## 57.3 Documentation requirements

Each component page should include:

- description;
- anatomy;
- when to use;
- when not to use;
- variants;
- states;
- accessibility;
- content rules;
- responsive behaviour;
- code component name;
- token bindings.

---

# Part XII — Design QA

## 58. Visual QA Checklist

For every screen:

- [ ] Page purpose is clear in five seconds.
- [ ] Primary action is visually dominant.
- [ ] Evidence and limitations are not hidden.
- [ ] Knowledge types are distinguishable without color.
- [ ] Confidence appears beside the qualified object.
- [ ] No data card contains an unexplained number.
- [ ] Loading, empty, partial, and error states exist.
- [ ] Text line lengths remain readable.
- [ ] Tables do not become unusable on smaller widths.
- [ ] Motion clarifies state.
- [ ] Reduced-motion behaviour is defined.
- [ ] Dark mode remains legible.
- [ ] Focus states are visible.
- [ ] Chart data can be inspected.
- [ ] Source and date context is visible.

---

## 59. Component QA Checklist

- [ ] Uses semantic tokens.
- [ ] Supports keyboard interaction.
- [ ] Has accessible name.
- [ ] Meets target size.
- [ ] Has default, hover, active, focus, disabled, loading, and error states where relevant.
- [ ] Does not hardcode feature-specific color.
- [ ] Documents responsive behaviour.
- [ ] Uses shared motion tokens.
- [ ] Works with reduced motion.
- [ ] Has unit or component tests.
- [ ] Avoids duplicated shadcn or internal primitives.
- [ ] Supports long content and localization expansion.
- [ ] Preserves evidence and status semantics.

---

## 60. Screen Acceptance Criteria

### Overview

- dataset and timeframe are visible;
- limitations are visible;
- top themes and insights link to detail;
- metrics link to underlying evidence where applicable.

### Themes

- ranking can be understood without opening each theme;
- filters persist in URL state;
- representative and contradictory evidence are accessible;
- comparison uses consistent scales.

### Ask

- active evidence scope is visible;
- streamed stages are honest;
- every displayed finding has citations or a visible warning;
- observed, synthesized, and hypothetical content are separated.

### Evidence

- original research meaning is readable;
- source metadata does not overpower text;
- labels and lineage are inspectable;
- source links are clearly external.

### Validation

- metrics show sample size and version;
- low-confidence items can enter review;
- human decisions preserve the original output.

### Reports

- generated and human-edited content are distinguishable;
- evidence links remain intact;
- limitations are included before export.

### Runs

- stage, progress, partial completion, failure, cost, and retry safety are understandable.

---

# Part XIII — Deferred Design Decisions

## 61. Decisions intentionally deferred

The following may be finalized after the first interactive prototype:

1. final product name and logo;
2. official Swiggy or Instamart brand-kit integration;
3. exact illustration style;
4. whether the Signal Field is retained after usability testing;
5. report PDF visual template;
6. high-contrast theme;
7. chart-library replacement if advanced use cases emerge;
8. collaborative cursors or multi-user report editing;
9. mobile report editing;
10. internationalization and non-Latin type testing.

These decisions must not block implementation of the token system or core components.

---

# Part XIV — Guidance for Claude Code

## 62. Implementation rules

Claude Code should treat this document as the frontend design source of truth and should:

- create tokens before product-specific components;
- place primitives and semantic tokens in separate layers;
- support light and dark modes from the beginning;
- use shadcn/ui and Radix behaviours rather than rebuilding accessibility primitives;
- adapt 21st.dev patterns instead of copying incompatible styles;
- centralize Framer Motion tokens and variants;
- preserve reduced-motion behaviour;
- create product-specific components for evidence, themes, insights, citations, confidence, warnings, and review states;
- keep feature components out of the generic `ui` folder;
- use URL state for shareable filters;
- keep citations and evidence inspection one interaction away;
- distinguish observed evidence, synthesized insight, and product hypothesis in every relevant view;
- show limitations and contradictory evidence in context;
- never show model-generated counts when deterministic data is available;
- implement all required loading, empty, partial, stale, error, rate-limited, unavailable-source, and low-confidence states;
- use semantic HTML and accessible Radix patterns;
- add keyboard and screen-reader tests for critical interactions;
- test at desktop, tablet, mobile, dark mode, 200% zoom, and reduced motion;
- create Storybook or an equivalent component showcase if the project timeline allows;
- update `design.md` whenever tokens, component contracts, or major interaction patterns change.

---

## 63. Design Definition of Done

The design system is ready for the first demonstrable version when:

1. primitive and semantic tokens are implemented;
2. light and dark modes work across all core components;
3. typography, spacing, shape, border, elevation, and motion tokens are centralized;
4. the app shell is responsive;
5. all seven primary product surfaces are designed;
6. evidence, synthesis, hypothesis, contradiction, confidence, review, and run states have reusable components;
7. the Ask workspace streams answers without obscuring citation validation;
8. evidence inspection works through keyboard and pointer interaction;
9. charts expose underlying data;
10. filters persist and remain understandable;
11. all required loading, empty, partial, stale, error, and rate-limited states exist;
12. reduced-motion behaviour is verified;
13. WCAG 2.2 AA contrast and focus requirements are met;
14. the component system avoids uncontrolled variant explosion;
15. shadcn and 21st.dev patterns have been normalized to the project system;
16. desktop, tablet, and mobile layouts are documented;
17. report exports retain knowledge-type labels, citations, contradictions, and limitations;
18. design QA is incorporated into frontend tests;
19. no major screen relies on decorative motion or color alone;
20. implementation can proceed without inventing local styling decisions.
