# Sophia Style Sheet

## Purpose

This document defines the visual language for Sophia-branded pages in the Metatron / Seraph interface. The target aesthetic is a **neon cyber-angel command center**: dark, cinematic, secure, and operational. Every page should feel like a live defense console, not a generic dashboard.

Use this sheet as the source of truth for:
- page layout
- typography
- color palette
- borders and surfaces
- buttons and pills
- telemetry panels
- terminal / HUD styling
- motion and glow effects
- usage rules for when to apply each treatment

---

## 1) Core Identity

### Theme summary
Sophia should look like:
- a **futuristic security interface**
- a **guardian / seraphic control surface**
- a **high-trust, high-alert system**
- a **terminal fused with cinematic neon UI**

The design should combine:
- cyberpunk
- tactical defense UI
- angelic / mythic branding
- clinical operational clarity

### Required emotional tone
- vigilant
- premium
- mysterious
- disciplined
- dangerous but controlled

### Forbidden tone
Do not make Sophia feel:
- playful
- soft
- consumer-grade
- corporate bland
- overly minimalist
- “AI SaaS generic”

---

## 2) Layout Principles

### Overall structure
Prefer a **two-column composition**:
- **Left side**: brand, hero art, narrative, symbolic visual centerpiece
- **Right side**: primary interaction surface, login/access form, operator controls

Secondary content should appear below as:
- telemetry blocks
- status strips
- terminal readouts
- diagnostic modules

### Composition rules
- Use strong asymmetry.
- Leave generous negative space.
- Keep the main interaction focal point obvious.
- Do not center everything into a single bland card.
- Use stacked panels and layered modules rather than one flat container.

### Spacing
- Large outer margins
- Moderate internal padding
- Big vertical rhythm between major regions
- Tight spacing only for micro-labels, status rows, and terminal output

### Page behavior
Pages should feel like they are part of one larger operating system.  
Prefer modular panels and repeated control metaphors over custom one-off layouts.

---

## 3) Color Palette

### Base background
The foundation is an extremely dark navy/near-black shell.

Recommended base tones:
- `#050811`
- `#060e18`
- `#07111d`
- `#081523`
- `#0a1624`

Use these for:
- page background
- shell backgrounds
- panel interiors
- overlay layers

### Primary accents
Use these as the main Sophia accent family:

| Color | Meaning | Use |
|---|---|---|
| Cyan | signal, clarity, live state, connectivity | borders, labels, dots, primary outlines |
| Magenta | mystique, intensity, danger, ritual energy | secondary glow, contrast accents, warnings |
| Purple | depth, power, sophistication | alternate panel accents, title glow |
| Green | online, healthy, active, verified | status indicators, success states |
| Amber | caution, elevated attention | warnings, important notices |
| Orange | hero branding, dramatic emphasis | major title treatments only |

### Recommended accent values
- Cyan: `#00f0ff`
- Magenta: `#ff2bd6`
- Purple: `#bc13fe` or `#7c3aed`
- Green: `#39ff14`
- Amber: `#ffb020`
- Orange: `#ff9a1f`

### Text colors
Use cool, pale text rather than pure white:
- primary text: `#e6fbff`
- secondary text: `#b8d8e6`
- muted text: soft blue-gray
- danger text: red only for explicit critical states

### Palette rules
- Never use neon colors everywhere at full intensity.
- Accent colors should be selective and layered.
- Cyan is the default system color.
- Magenta should feel special.
- Orange should be reserved for the most iconic hero title treatment.

---

## 4) Typography

Sophia uses a **three-tier typography system**.

### A. Display / Hero Font
Use for:
- page titles
- major feature headers
- brand wordmarks
- dramatic hero labels

Recommended style:
- heavy
- stylized
- uppercase or near-uppercase
- glowing
- slightly glitchy / mechanical

Typical use:
- `SDGlitch`
- `Orbitron`

### B. UI / Label Font
Use for:
- buttons
- tabs
- eyebrow labels
- pills
- microcopy
- headers on utility panels

Recommended style:
- compact
- tracked out
- uppercase
- technical
- readable under glow

Typical use:
- `FfMoon`
- `Rajdhani`
- `Orbitron` in smaller contexts

### C. Terminal / Body Mono Font
Use for:
- logs
- commands
- diagnostic panels
- telemetry readouts
- system messages
- code blocks
- status messages

Typical use:
- `TerminalVision`
- `JetBrains Mono`

### Typography hierarchy
- **H1**: large, dramatic, glowing, display-heavy
- **H2 / H3**: techno headers with subtle glitch or glow
- **Labels**: uppercase, tracked, compact
- **Body**: readable but stylized, often mono or terminal-like
- **Diagnostics**: explicit monospace

### Typographic rules
- Use uppercase for system labels and controls.
- Use letter spacing heavily for micro-labels.
- Avoid plain, neutral sans-serif-only layouts.
- Use gradients on text only for large hero headings.
- Do not overuse rainbow text; keep it reserved for the biggest statement pieces.

---

## 5) Surfaces, Panels, and Borders

### Panel philosophy
Everything should be framed as a control surface:
- cards
- consoles
- readouts
- terminals
- status rails
- HUD modules

### Surface characteristics
- very dark fill
- subtle layered gradients
- thin glowing borders
- minimal rounding
- crisp edges or clipped corners
- occasional scanline texture

### Border rules
Use:
- 1px to 3px borders
- cyan by default
- magenta / purple / green accents when needed
- glowing outlines for emphasis

### Recommended panel look
- dark interior
- cyan border
- slight inner glow
- minimal shadow, mostly neon-based
- subtle hover lift

### Corner language
Sophia may use:
- clipped corners
- bracket corners
- HUD-style corner marks
- sharp card geometry

Rounded corners are acceptable only when they are subtle or when a pill/button must remain rounded.

---

## 6) Buttons

### Primary button
The primary CTA should look like a **control activation**.

Use:
- full-width or clearly dominant sizing
- cyan-to-magenta gradient, or cyan-to-purple gradient
- uppercase labels
- bold weight
- high contrast
- glow on hover

When to use:
- login / access / submit
- critical system action
- main conversion point

### Secondary button
Use for:
- secondary actions
- outline controls
- navigation choices
- less important actions

Style:
- dark background
- cyan outline
- restrained glow
- minimal fill

### Tertiary / text links
Use for:
- register
- learn more
- minor navigation

Style:
- compact
- underlined or lightly emphasized
- should not compete with primary action

### Button rules
- Buttons should feel like instruments, not marketing buttons.
- Keep uppercase labels for important controls.
- Use sweep or shine animations sparingly.
- Do not flatten them into standard Tailwind defaults.

---

## 7) Pills, Chips, Badges, and Micro-Labels

### Purpose
Pills and badges in Sophia are system markers, not decoration.

Use them for:
- status
- category
- version
- access level
- environment
- mode
- uptime / online state

### Styling rules
- small
- uppercase
- tracked out
- thin border
- faint glow
- color-coded by meaning

### Color usage
- cyan: default / active / informational
- green: healthy / online / verified
- amber: caution / standby
- magenta: special / advanced / experimental
- purple: alternate system state

### Best practices
- Keep pill text short.
- Avoid wrapping.
- Use pills to break up dense panels and create hierarchy.
- Do not use pills as giant labels.

---

## 8) Terminal / HUD Language

This is one of the most important parts of the Sophia identity.

### Terminal style
Use terminal language for:
- boot sequences
- logs
- diagnostic readouts
- command prompts
- monitored system state
- telemetry summaries

### HUD language
Use HUD language for:
- system labels
- corner brackets
- scanlines
- status strips
- live indicators
- signal bars
- online dots

### Common motifs
- `//`
- `> `
- uppercase micro-tags
- version markers
- online indicators
- pipeline/readout language
- monospaced status rows

### Rules
- Every major page should contain at least one terminal-like module.
- Every major layout should feel “operational.”
- Use live status lights and small counters to imply an active system.
- Diagnostics should look like they’re streaming from an actual machine.

---

## 9) Hero Art and Symbolic Centerpieces

Sophia benefits from a strong symbolic visual anchor.

### Hero art rules
Use a dramatic central image or illustration when possible:
- winged guardian
- cyber-angel
- divine machine
- defense avatar
- lit ceremonial core

### Visual treatment
- neon aura
- layered glow
- transparent energy rings
- subtle haze
- cinematic lighting
- centered symbolism, but not centered layout everywhere else

### Purpose
The hero visual should:
- establish the emotional identity
- reinforce the “guardian” concept
- add mythic weight to the technical interface

---

## 10) Motion and Effects

### Motion style
Motion should feel:
- alive
- technical
- slightly unstable
- controlled

### Recommended effects
- soft breathing glow
- scanline sweep
- subtle flicker
- slight RGB split on large text
- hover lift
- moving diagnostic ticker
- thin beam sweeps
- pulsing status dots

### Use motion sparingly
Avoid:
- excessive bouncing
- playful animations
- gimmicky transitions
- constant large-scale movement

### Best animation usage
- hero title
- page headers
- status lights
- panels on hover
- terminal readouts
- separators and rails

### Reduced motion
Always respect reduced-motion preferences.  
When motion is reduced, preserve the visual identity through static glow and contrast rather than removing all character.

---

## 11) Background Treatment

### Background layers
Sophia pages should usually include:
- deep gradient shell
- subtle grid overlay
- scanlines
- soft radial glows
- optional binary / data-stream texture

### Background goals
The background should:
- support the foreground, not distract from it
- feel alive but restrained
- reinforce the sense of a live machine interface

### Do not
- use flat black alone unless intentionally minimal
- use noisy backgrounds that obscure readability
- use generic stock-image backgrounds without treatment

---

## 12) Component Usage Guide

### Use cyan for:
- default panel borders
- active indicators
- primary labels
- focus states
- system readiness

### Use magenta for:
- dramatic emphasis
- secondary glow
- alerts with emotional weight
- title shimmer
- special states

### Use green for:
- online
- good health
- verified
- successful state
- active process indicators

### Use amber for:
- caution
- partial alert
- monitoring
- warning emphasis

### Use purple for:
- premium accent
- alternate state
- advanced mode
- secondary panels

---

## 13) When to Use What

### Use a hero title when:
- a page is introducing a major section
- the page is an entry point
- you need strong identity immediately

### Use a terminal block when:
- the page needs context or live status
- you want to reinforce technical legitimacy
- you are showing logs, commands, or boot output

### Use a pill when:
- a piece of information can be compressed into a short state marker
- you need quick classification
- you want visual separation without a full card

### Use a bordered panel when:
- content is a distinct unit
- the page needs structure
- you want a command-module feel

### Use a gradient button when:
- this is the primary action
- the UI needs a clear control target
- you want to express “activation” or “entry”

### Use scanlines / glow when:
- the page should feel operational
- you need atmosphere
- you want a subtle futuristic finish

---

## 14) Accessibility and Readability

### Rules
- Keep contrast strong enough for all body text.
- Use neon for accents, not entire paragraphs.
- Do not place bright glow behind long blocks of text.
- Prefer readable mono/terminal fonts for logs.
- Ensure buttons remain legible under glow effects.
- Do not rely on color alone for status.

### Good practice
- Use icons plus color for status.
- Use labels plus color for category.
- Maintain clear spacing around text and controls.

---

## 15) Reusable Style Tokens

### Core surface tokens
- dark shell background
- dark panel background
- glowing cyan border
- magenta secondary glow
- inner panel haze

### Core text tokens
- display title
- techno label
- mono diagnostic
- muted body
- neon status

### Core interaction tokens
- primary neon gradient button
- secondary outline button
- hover lift
- scanline sweep
- pulse dot
- terminal cursor

---

## 16) Recommended Usage Pattern by Page Type

### Login / Access pages
- dark shell
- dramatic hero element
- access form in a glowing panel
- strong button hierarchy
- safety/status note beneath

### Dashboard pages
- bento / modular grid
- multiple panels with varied accents
- stat cards and telemetry blocks
- real-time indicators
- mixed accent colors for hierarchy

### Detail / Ops pages
- panel-heavy layout
- command bar or status strip
- section dividers
- terminal readout zones
- live status chips

### Threat / Incident pages
- higher amber/red presence
- heavier terminal language
- explicit status markers
- strong visual urgency

---

## 17) What Not To Do

Do not:
- use a white or light theme
- use soft pastel branding
- use generic cards with default gray borders
- center everything symmetrically
- rely on one font only
- overuse gradients everywhere
- make the UI playful or cute
- use decorative effects without functional meaning
- ignore the terminal/HUD identity
- make buttons look like ordinary web forms

---

## 18) Style Summary

Sophia is:
- **dark**
- **neon**
- **technical**
- **mythic**
- **glowing**
- **command-oriented**
- **high-security**
- **cinematic**

Every page should feel like it belongs inside a living defense console where:
- cyan means signal
- magenta means intensity
- green means alive
- amber means caution
- purple means power

If a new page does not feel like a guardian terminal, it is not yet Sophia enough.
