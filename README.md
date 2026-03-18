# Postergeist

Academic poster generator that converts Markdown files to beautiful HTML posters with live preview, drag-and-drop editing, and PDF export.

## Installation

```bash
uv pip install -e .
playwright install chromium  # Required for PDF export
```

## Quick Start

```bash
# Create a new poster from a template
postergeist new my-poster --template gradient

# Start the live editor
postergeist serve my-poster/poster.md

# Export to HTML
postergeist export my-poster/poster.md -o poster.html
```

## Poster Format

Posters are written in Markdown with YAML frontmatter for configuration. Each `## Heading` creates a new cell on the poster.

### Frontmatter

```yaml
---
title: "My Research Poster"
subtitle: "Optional subtitle"
authors:
  - name: Alice Smith
    affiliation: "1"
  - name: Bob Jones
    affiliation: "1,2"
affiliations:
  - key: "1"
    name: University of Example
  - key: "2"
    name: Institute of Science
poster:
  size: A0-landscape           # Paper size (see below)
  template: gradient            # Built-in or custom theme
  columns: [1, 2, 1]           # Relative column widths
  logos:                        # One or more logos (top-left)
    - images/logo1.png
    - images/logo2.png
  qr_code: https://example.com # QR code URL (top-right)
  qr_label: "Project Page"     # Label next to QR code
  colors:                      # Override template colors
    primary: "#2d1b69"
    secondary: "#e87f24"
  fonts:                       # Override template fonts
    heading: Roboto Slab
    body: Open Sans
  font_scale: 1.0              # Global font scale factor
  style:                       # Override template layout
    column_gap: "8mm"          # Gap between columns
    cell_gap: "3mm"            # Gap between cells
    cell_padding: "6mm"        # Padding inside cells
    poster_margin: "12mm"      # Outer margin around poster body
    header_padding: "8mm 12mm" # Padding inside the header
---
```

### Cells

Each `## Heading` starts a new cell. Use HTML comments to control placement:

```markdown
## Introduction

<!-- col: 0 -->

Your content here with **bold**, *italic*, and other markdown.

## Results

<!-- col: 1, h: 1.5 -->

This cell is in column 1 with 1.5x height.

## Analysis

<!-- col: 2 -->

Content for the third column.
```

**Cell options** (in `<!-- ... -->` comments):
- `col: N` — Place cell in column N (0-indexed)
- `h: N` — Relative height (default: 1.0, higher = taller)
- `split: true` — Split cell horizontally (use `|||` to separate halves)

Cells without a title (no `## Heading` text) render as content-only, without a header bar.

### Split Cells

Create side-by-side content within a single cell:

```markdown
## Comparison

<!-- col: 0, split: true -->

### Left Side

Content for the left half.

|||

### Right Side

Content for the right half.
```

## Content Features

### Tables

Standard markdown tables are supported and automatically contained within cells:

```markdown
| Method | Score | Time |
|--------|-------|------|
| Baseline | 0.75 | 10s |
| **Ours** | **0.95** | **3s** |
```

### Math (LaTeX)

Inline math with `$E = mc^2$` and display math with:

```markdown
$$\text{Quality} = \frac{\text{PSNR} \times \text{SSIM}}{\text{Time}}$$
```

Rendered via KaTeX.

### Mermaid Diagrams

```markdown
```mermaid
graph LR
    A[Input] --> B[Process]
    B --> C[Output]
```⁠
```

Diagrams automatically adapt to the active template's color scheme.

### Images

Standard markdown images with automatic captions from alt text:

```markdown
![**Method overview:** our pipeline](images/figure.png)
```

Alt text is rendered as a caption below the image. Markdown formatting (bold, italic, code) is supported in captions — bold text is highlighted in the primary color.

### Image Grids

Display images side by side with captions:

```markdown
{grid:2:center}

![**Bold caption:** description text](images/fig1.png)

![**Another caption:** more details](images/fig2.png)
```

**Syntax:** `{grid:N}` or `{grid:N:align}`
- `N` — Number of images in the grid (2, 3, 4, etc.)
- `align` — Vertical image alignment: `top`, `center`, or `bottom` (default: `bottom`)

**Caption formatting:** Markdown bold (`**text**`), italic (`*text*`), and inline code are rendered in captions. Bold text is highlighted in the primary color.

**Image weights:** Control relative widths of grid items with `{w:N}` at the start of the alt text:

```markdown
{grid:2}

![{w:2} Large image gets 2/3 width](images/wide.png)

![{w:1} Smaller image gets 1/3 width](images/narrow.png)
```

Captions are automatically aligned horizontally across all grid items, regardless of image heights.

## Paper Sizes

### Built-in Sizes

| Name | Dimensions |
|------|-----------|
| `A0-landscape` | 1189 × 841 mm |
| `A0-portrait` | 841 × 1189 mm |
| `A1-landscape` | 841 × 594 mm |
| `A1-portrait` | 594 × 841 mm |
| `A2-landscape` | 594 × 420 mm |
| `A2-portrait` | 420 × 594 mm |
| `A3-landscape` | 420 × 297 mm |
| `A3-portrait` | 297 × 420 mm |
| `48x36` | 48 × 36 in |
| `36x24` | 36 × 24 in |
| `36x48` | 36 × 48 in |
| `42x30` | 42 × 30 in |
| `56x36` | 56 × 36 in |

### Custom Sizes

Specify any size with units:

```yaml
size: 40x30in     # inches
size: 1200x800mm  # millimeters
size: 100x70cm    # centimeters
```

## Templates

### Built-in Templates

| Name | Description | Fonts |
|------|-------------|-------|
| `classic` | Traditional academic poster with bold header | DM Sans / Source Serif 4 |
| `modern-dark` | Sleek dark theme with neon accents and glassmorphism | Oswald / Montserrat |
| `modern-light` | Light counterpart to Modern Dark with the same fonts and layout | Oswald / Montserrat |
| `minimal` | Clean white design with subtle borders and elegant typography | Averia Serif Libre / Geist |
| `gradient` | Vibrant gradient header with rounded cards and soft shadows | Poppins / Lora |

List templates: `postergeist templates`

Preview any template by adding `?template=NAME` to the URL in the browser (e.g., `http://localhost:8765/?template=modern-dark`).

### Custom Templates

Create a YAML file next to your poster markdown (e.g., `my-theme.yaml`) and reference it in frontmatter:

```yaml
# poster.md frontmatter
poster:
  template: my-theme
```

**Example `my-theme.yaml`:**

```yaml
name: "My Custom Theme"
description: "A personalized poster theme"

colors:
  primary: "#1a5276"
  secondary: "#2ecc71"
  accent: "#e74c3c"
  background: "#ecf0f1"
  surface: "#ffffff"
  text: "#2c3e50"
  text_light: "#ffffff"
  header_bg: "linear-gradient(135deg, #1a5276 0%, #2ecc71 100%)"
  cell_border: "rgba(26,82,118,0.2)"
  poster_bg: "#ecf0f1"
  table_header_bg: "#1a5276"
  table_header_text: "#ffffff"

fonts:
  heading: "Merriweather"
  body: "Lato"

style:
  cell_radius: "3mm"
  cell_shadow: "0 1mm 4mm rgba(0,0,0,0.1)"
  cell_border_width: "0px"
  cell_padding: "6mm"
  cell_gap: "3mm"
  column_gap: "5mm"
```

Any omitted keys fall back to the `classic` template defaults. Fonts are loaded from Google Fonts automatically.

### Template Color Reference

| Key | Description |
|-----|-------------|
| `primary` | Cell headings, bold text, key accents |
| `secondary` | Chart accents, links, active elements |
| `accent` | Highlights, callouts |
| `background` | Page background behind cells |
| `surface` | Cell background color |
| `text` | Body text color |
| `text_light` | Header text color (on dark backgrounds) |
| `header_bg` | Poster header background (supports gradients) |
| `cell_border` | Cell border color |
| `poster_bg` | Outer poster frame/border color |
| `body_bg` | Background between cells and columns (defaults to `background`) |
| `table_header_bg` | Table header row background (supports gradients) |
| `table_header_text` | Table header text color |

### Template Style Reference

| Key | Default | Description |
|-----|---------|-------------|
| `cell_radius` | `0px` | Cell corner radius |
| `cell_shadow` | `none` | Cell box shadow |
| `cell_border_width` | `0px` | Cell border width |
| `cell_padding` | `5mm` | Padding inside cells |
| `cell_gap` | `3mm` | Gap between cells in a column |
| `column_gap` | `5mm` | Gap between columns |
| `poster_margin` | `10mm` | Outer margin around the poster body (all sides) |
| `header_padding` | `6mm 10mm` | Padding inside the header (CSS shorthand) |
| `image_border` | `none` | Border around images (useful for dark themes, e.g. `0.3mm solid rgba(255,255,255,0.12)`) |
| `image_radius` | `1mm` | Image corner radius |

## Editor

The development server (`postergeist serve`) provides a live editor with:

- **Drag-and-drop** — Reorder cells by dragging their headers
- **Cell resize** — Drag the bottom edge of cells to adjust height
- **Column resize** — Drag between columns to adjust widths
- **Split cell resize** — Drag the divider between split cell halves to adjust proportions
- **Split/merge** — Split cells into side-by-side halves or merge them back
- **Live reload** — Edits to the markdown file are instantly reflected
- **Preview/Edit toggle** — Switch between editing and clean preview modes

All layout changes (reorder, resize, column widths) are saved back to the markdown file automatically.

## PDF Export

Click **Export PDF** in the toolbar to generate a high-quality PDF using Playwright's headless Chromium. The PDF matches the exact poster dimensions with full color fidelity.

Requires Playwright:
```bash
playwright install chromium
```

## CLI Reference

```
postergeist new <directory> [-t template] [--example]
    Create a new poster project

postergeist serve <file.md> [--host HOST] [--port PORT] [--preview] [--no-browser]
    Start the development server with live editing

postergeist export <file.md> [-o output.html]
    Export poster to standalone HTML

postergeist templates
    List available built-in templates
```

## Paper-to-Poster Skill (Claude Code)

Postergeist includes a Claude Code skill that automatically converts academic paper PDFs into posters.

### Setup

The skill is located at `.claude/skills/paper-to-poster/SKILL.md`. It's automatically available when using Claude Code in this project.

### Usage

```
/paper-to-poster path/to/paper.pdf
/paper-to-poster https://arxiv.org/abs/2408.00653
/paper-to-poster paper.pdf CVPR 2026
```

The skill accepts:
- **Local PDF paths** — extracts content and figures directly
- **URLs** — downloads the PDF first (supports ArXiv abs/pdf links, direct PDF URLs)
- **Optional conference name** — used as subtitle and to inform style choices

### What it does

1. **Extracts** text and figures from the PDF using PyMuPDF (handles raster images, vector drawings, and complex LaTeX figures)
2. **Generates** a 3-column poster markdown:
   - Column 1 (narrow): Motivation, problem statement, approach overview
   - Column 2 (wide): Key results, main figures, visual comparisons
   - Column 3 (narrow): Supporting tables, ablations, references
3. **Reviews** the poster against the original paper for accuracy and completeness
4. **Optimizes** whitespace by adjusting cell heights

The generated poster uses all available Postergeist features: split cells, image grids, mermaid diagrams, math equations, blockquotes, and tables.

## Project Structure

```
my-poster/
├── poster.md          # Your poster content
├── my-theme.yaml      # Optional custom theme
└── images/
    ├── logo.png
    ├── figure1.png
    └── figure2.png
```
