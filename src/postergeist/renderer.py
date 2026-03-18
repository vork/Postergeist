"""Render a Poster to HTML."""

import io
import re
from pathlib import Path

import mistune
import qrcode
import qrcode.image.svg

from .formats import get_size, size_to_css
from .templates import get_template, merge_config
from .parser import Poster, Cell


def _render_qr_svg(url: str) -> str:
    """Generate an inline SVG QR code."""
    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(url, image_factory=factory, box_size=10)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")


def _google_fonts_url(fonts: dict) -> str:
    """Build Google Fonts import URL."""
    families = set()
    for k, f in fonts.items():
        if isinstance(f, str) and k in ("heading", "body"):
            families.add(f.replace(" ", "+") + ":wght@300;400;500;600;700;800;900")
    if not families:
        return ""
    return f"https://fonts.googleapis.com/css2?{'&'.join('family=' + f for f in sorted(families))}&display=swap"


def _render_markdown(text: str) -> str:
    """Render markdown to HTML, handling images, tables, math placeholders, mermaid."""
    # Protect math from markdown parser
    math_blocks = {}
    counter = [0]

    def protect_display_math(m):
        key = f"MATH_DISPLAY_{counter[0]}"
        math_blocks[key] = f'<div class="math-display">$${m.group(1)}$$</div>'
        counter[0] += 1
        return key

    def protect_inline_math(m):
        key = f"MATH_INLINE_{counter[0]}"
        math_blocks[key] = f'<span class="math-inline">${m.group(1)}$</span>'
        counter[0] += 1
        return key

    # Protect display math first ($$...$$)
    text = re.sub(r"\$\$(.+?)\$\$", protect_display_math, text, flags=re.DOTALL)
    # Protect inline math ($...$) - but not in code
    text = re.sub(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", protect_inline_math, text)

    # Protect ALL image captions from markdown stripping formatting in alt text
    # Store the raw alt text (with markdown) before mistune processes it
    all_images = {}
    grid_images = {}  # Subset: images inside grid blocks

    def protect_any_image(m):
        alt = m.group(1)
        # Skip images already protected by grid block protection
        if re.match(r'^IMG_\d+$', alt):
            return m.group(0)
        key = f"IMG_{counter[0]}"
        src = m.group(2)
        all_images[key] = (alt, src)
        counter[0] += 1
        return f"![{key}]({src})"

    # Track which images are inside grid blocks
    def protect_grid_block(m):
        prefix = m.group(1)  # The {grid:...} line
        rest = m.group(2)
        # Replace image syntax in the rest with placeholders
        def protect_grid_image(im):
            key = f"IMG_{counter[0]}"
            alt = im.group(1)
            src = im.group(2)
            all_images[key] = (alt, src)
            grid_images[key] = (alt, src)
            counter[0] += 1
            return f"![{key}]({src})"
        protected = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', protect_grid_image, rest)
        return prefix + protected

    # First protect grid images (so we can tag them)
    text = re.sub(r'(\{grid:\d+(?::\w+)?\}[ \t]*\n)(.*?)(?=\n##|\n\{grid:|\Z)', protect_grid_block, text, flags=re.DOTALL)
    # Then protect all remaining images
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', protect_any_image, text)

    md = mistune.create_markdown(
        plugins=["table", "strikethrough", "footnotes", "task_lists"],
    )
    html = md(text)

    # Restore math
    for key, val in math_blocks.items():
        html = html.replace(key, val)
        html = html.replace(f"<p>{key}</p>", val)

    # Mermaid code blocks
    html = re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        lambda m: f'<div class="mermaid">{m.group(1)}</div>',
        html,
        flags=re.DOTALL,
    )

    # Image grid: convert {grid:N} blocks into side-by-side image grids
    # Syntax in markdown: {grid:3} followed by images with ![caption](url)
    # The grid collects the next N images and displays them side by side
    def _render_caption(alt_text):
        """Render markdown formatting in image alt text for captions."""
        if not alt_text:
            return ""
        # Process bold and italic in alt text
        rendered = alt_text
        rendered = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', rendered)
        rendered = re.sub(r'\*(.+?)\*', r'<em>\1</em>', rendered)
        rendered = re.sub(r'__(.+?)__', r'<strong>\1</strong>', rendered)
        rendered = re.sub(r'_(.+?)_', r'<em>\1</em>', rendered)
        rendered = re.sub(r'`(.+?)`', r'<code>\1</code>', rendered)
        return rendered

    def _build_figure(alt, src, is_grid=True):
        """Build a figure element from alt text and src, with optional weight."""
        weight = 1
        alt_clean = alt
        weight_match = re.match(r'\{w:(\d+(?:\.\d+)?)\}\s*', alt)
        if weight_match:
            weight = float(weight_match.group(1))
            alt_clean = alt[weight_match.end():]
        caption_rendered = _render_caption(alt_clean)
        caption_html = f'<figcaption>{caption_rendered}</figcaption>' if alt_clean else ''
        if is_grid:
            flex_style = f' style="flex: {weight};"' if weight != 1 else ''
            return f'<figure{flex_style}><div class="grid-img-wrap"><img src="{src}" alt="{alt_clean}"></div>{caption_html}</figure>'
        else:
            return f'<figure class="img-figure"><img src="{src}" alt="{alt_clean}">{caption_html}</figure>'

    def convert_grid(m):
        cols = int(m.group(1))
        align = m.group(2) or "bottom"
        rest = m.group(3)
        # Find image placeholders (IMG_N) in alt text
        placeholder_pattern = r'<img\s+src="([^"]+)"\s+alt="(IMG_\d+)"[^>]*/?\s*>'
        placeholders = list(re.finditer(placeholder_pattern, rest))[:cols]
        if not placeholders:
            return m.group(0)
        figures = []
        for ph in placeholders:
            key = ph.group(2)
            src = ph.group(1)
            if key in grid_images:
                alt, _ = grid_images[key]
            else:
                alt = ""
            figures.append(_build_figure(alt, src, is_grid=True))
        consumed_end = placeholders[-1].end()
        remaining = rest[consumed_end:]
        align_class = f' align-{align}' if align != "bottom" else ''
        grid_html = f'<div class="image-grid{align_class}">{"".join(figures)}</div>'
        return grid_html + remaining

    # Syntax: {grid:N} or {grid:N:align} where align is top/center/bottom
    # Match both: <p>{grid:N}</p> followed by images, AND <p>{grid:N}\n<img...></p> (same paragraph)
    html = re.sub(r'<p>\{grid:(\d+)(?::(\w+))?\}\s*\n(.*?)</p>', convert_grid, html, flags=re.DOTALL)
    html = re.sub(r'<p>\{grid:(\d+)(?::(\w+))?\}</p>(.*?)(?=<h[234]|<div class="image-grid"|$)', convert_grid, html, flags=re.DOTALL)

    # Convert remaining standalone images (non-grid) with protected alt text into figures
    def _restore_img(m):
        src = m.group(1)
        key = m.group(2)
        if key in all_images and key not in grid_images:
            alt, _ = all_images[key]
            if alt and alt.strip():
                return _build_figure(alt, src, is_grid=False)
        # No caption or grid image leftover — return plain img
        return f'<img src="{src}" alt="">'

    # Match images with IMG_N placeholder as alt text
    html = re.sub(
        r'<img\s+src="([^"]+)"\s+alt="(IMG_\d+)"[^>]*/?\s*>',
        _restore_img,
        html,
    )
    # Also handle wrapped in <p> tags
    html = re.sub(
        r'<p>(<figure class="img-figure">.*?</figure>)</p>',
        r'\1',
        html,
        flags=re.DOTALL,
    )

    return html


def _render_cell_html(cell: Cell, template: dict) -> str:
    """Render a single cell to HTML."""
    height_style = f"flex: {cell.height};"
    data_attrs = f'data-id="{cell.id}" data-height="{cell.height}" data-col="{cell.column}"'

    if cell.split and cell.subcells:
        subcell_html = ""
        for sub in cell.subcells:
            sub_title_html = f'<div class="cell-header subcell-header">{sub.title}</div>' if sub.title else ""
            sub_content = _render_markdown(sub.content)
            subcell_html += f'''
            <div class="subcell" data-id="{sub.id}">
                {sub_title_html}
                <div class="cell-content-wrapper">
                    <div class="cell-content">{sub_content}</div>
                </div>
            </div>'''
        title_html = f'<div class="cell-header">{cell.title}</div>' if cell.title else ""
        return f'''
        <div class="cell split-cell" {data_attrs} style="{height_style}">
            {title_html}
            <div class="split-container">{subcell_html}</div>
        </div>'''

    title_html = f'<div class="cell-header">{cell.title}</div>' if cell.title else ""
    content_html = _render_markdown(cell.content)
    return f'''
    <div class="cell" {data_attrs} style="{height_style}">
        {title_html}
        <div class="cell-content-wrapper">
            <div class="cell-content">{content_html}</div>
        </div>
    </div>'''


def _render_authors_html(poster: Poster) -> str:
    """Render author and affiliation block."""
    authors = poster.authors
    affiliations = poster.affiliations
    if not authors:
        return ""

    aff_map = {str(a.get("key", a.get("id", i + 1))): a.get("name", "") for i, a in enumerate(affiliations)} if affiliations else {}

    author_spans = []
    for a in authors:
        if isinstance(a, str):
            author_spans.append(f'<span class="author">{a}</span>')
        else:
            name = a.get("name", "")
            aff = a.get("affiliation", "")
            sup = f'<sup>{aff}</sup>' if aff else ""
            author_spans.append(f'<span class="author">{name}{sup}</span>')

    author_html = '<span class="author-sep">&nbsp;&nbsp;&nbsp;&nbsp;</span>'.join(author_spans)

    aff_spans = []
    for key, name in sorted(aff_map.items()):
        aff_spans.append(f'<span class="affiliation"><sup>{key}</sup>{name}</span>')
    aff_html = '<span class="aff-sep">&nbsp;&nbsp;&nbsp;&nbsp;</span>'.join(aff_spans)

    return f'''
    <div class="authors-block">
        <div class="authors">{author_html}</div>
        <div class="affiliations">{aff_html}</div>
    </div>'''


def _render_logos_html(poster: Poster, base_url: str) -> str:
    """Render logo area with all affiliation/company logos."""
    config = poster.poster_config
    logos = config.get("logos", [])
    if not logos:
        # Single logo fallback
        logo_path = config.get("logo", "")
        if logo_path:
            logos = [logo_path]
    if not logos:
        return ""

    imgs = []
    for logo in logos:
        if isinstance(logo, dict):
            src = logo.get("src", logo.get("path", ""))
            alt = logo.get("alt", "Logo")
        else:
            src = str(logo)
            alt = "Logo"
        imgs.append(f'<img src="{base_url}/{src}" alt="{alt}">')

    return f'<div class="logos">{"".join(imgs)}</div>'


def render_poster(poster: Poster, edit_mode: bool = False, base_url: str = "") -> str:
    """Render a Poster to a complete HTML document."""
    config = poster.poster_config
    template_name = config.get("template", "classic")
    search_dir = poster.source_path.parent if poster.source_path else None
    template = get_template(template_name, search_dir=search_dir)

    # Merge user overrides
    overrides = {}
    if "colors" in config:
        overrides["colors"] = config["colors"]
    if "fonts" in config:
        overrides["fonts"] = config["fonts"]
    if "style" in config:
        overrides["style"] = config["style"]
    template = merge_config(template, overrides)

    colors = template["colors"]
    fonts = template["fonts"]
    style = template["style"]

    # Auto-generate gradients from primary/secondary if the template uses gradients
    # and the user overrode primary or secondary colors
    if "colors" in config and ("primary" in config["colors"] or "secondary" in config["colors"]):
        p = colors["primary"]
        s = colors["secondary"]
        orig_template = get_template(template_name, search_dir=search_dir)
        orig_header = orig_template["colors"].get("header_bg", "")
        orig_table = orig_template["colors"].get("table_header_bg", "")
        # If template originally used a gradient and user didn't explicitly override header_bg
        if "gradient" in orig_header and "header_bg" not in config.get("colors", {}):
            colors["header_bg"] = f"linear-gradient(135deg, {p} 0%, {s} 100%)"
        if "gradient" in orig_table and "table_header_bg" not in config.get("colors", {}):
            colors["table_header_bg"] = f"linear-gradient(135deg, {p} 0%, {s} 100%)"

    # Paper size
    size = get_size(config.get("size", "A0-landscape"))
    css_w, css_h = size_to_css(size)

    # Column widths
    columns = config.get("columns", [1])

    # Fonts
    fonts_url = _google_fonts_url(fonts)

    # Logos
    logos_html = _render_logos_html(poster, base_url)

    # QR Code
    qr_html = ""
    qr_url = config.get("qr_code", "")
    if qr_url:
        qr_label = config.get("qr_label", "")
        qr_svg = _render_qr_svg(qr_url)
        label_html = f'<div class="qr-label">{qr_label}</div>' if qr_label else ""
        qr_html = f'<div class="qr-code">{label_html}<div class="qr-svg">{qr_svg}</div></div>'

    # Authors
    authors_html = _render_authors_html(poster)

    # Header background style
    header_bg = colors["header_bg"]
    if header_bg.startswith("linear-gradient") or header_bg.startswith("radial-gradient"):
        header_bg_css = f"background: {header_bg};"
    else:
        header_bg_css = f"background-color: {header_bg};"

    # Table header background
    table_hdr_bg = colors.get("table_header_bg", colors["primary"])
    table_hdr_text = colors.get("table_header_text", colors.get("text_light", "#fff"))
    if table_hdr_bg.startswith("linear-gradient") or table_hdr_bg.startswith("radial-gradient"):
        table_hdr_bg_css = f"background: {table_hdr_bg};"
    else:
        table_hdr_bg_css = f"background-color: {table_hdr_bg};"

    # Body background (area between cells/columns, defaults to background color)
    body_bg = colors.get("body_bg", colors["background"])

    # Style config with defaults
    cell_padding = style.get("cell_padding", "5mm")
    cell_gap = style.get("cell_gap", "3mm")
    column_gap = style.get("column_gap", "5mm")
    poster_margin = style.get("poster_margin", "10mm")
    header_padding = style.get("header_padding", "6mm " + poster_margin)

    # Render columns (staggered layout)
    poster_columns = poster.get_columns()
    body_html = ""
    for col_idx, col_cells in enumerate(poster_columns):
        col_flex = columns[col_idx] if col_idx < len(columns) else 1
        cells_html = "".join(_render_cell_html(c, template) for c in col_cells)
        body_html += f'<div class="poster-column" data-col="{col_idx}" style="flex: {col_flex};">{cells_html}</div>'

    # Font config
    font_scale = config.get("font_scale", 1.0)
    heading_size = fonts.get("heading_size", "10mm")
    heading_weight = fonts.get("heading_weight", "800")

    # Mermaid theme based on template
    mermaid_theme = "dark" if template_name == "modern-dark" else "neutral"
    mermaid_bg = "transparent"

    # Edit mode extras
    edit_class = "edit-mode" if edit_mode else ""
    edit_scripts = ""
    if edit_mode:
        edit_scripts = f"""
        <script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js"></script>
        <script>
        window.POSTER_CONFIG = {{
            sourceFile: "{poster.source_path or ''}",
            baseUrl: "{base_url}"
        }};
        </script>
        <script src="{base_url}/static/editor.js"></script>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{poster.title}</title>
<link rel="stylesheet" href="{fonts_url}">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
:root {{
    --primary: {colors['primary']};
    --secondary: {colors['secondary']};
    --accent: {colors['accent']};
    --background: {colors['background']};
    --surface: {colors['surface']};
    --text: {colors['text']};
    --text-light: {colors['text_light']};
    --cell-border: {colors['cell_border']};
    --poster-bg: {colors['poster_bg']};
    --cell-radius: {style['cell_radius']};
    --cell-shadow: {style['cell_shadow']};
    --cell-border-width: {style['cell_border_width']};
    --cell-padding: {cell_padding};
    --cell-gap: {cell_gap};
    --column-gap: {column_gap};
    --poster-margin: {poster_margin};
    --header-padding: {header_padding};
    --body-bg: {body_bg};
    --img-border: {style.get('image_border', 'none')};
    --img-radius: {style.get('image_radius', '1mm')};
    --font-heading: '{fonts['heading']}', serif;
    --font-body: '{fonts['body']}', sans-serif;
    --font-scale: {font_scale};
    --cell-heading-size: calc({heading_size} * var(--font-scale));
    --cell-heading-weight: {heading_weight};
    --poster-width: {css_w};
    --poster-height: {css_h};
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    background: #888;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    min-height: 100vh;
    padding: 70px 20px 20px;
    overflow: auto;
}}

.poster-viewport {{
    transform-origin: top center;
}}

.poster {{
    width: var(--poster-width);
    height: var(--poster-height);
    background: var(--poster-bg);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
}}

/* Header */
.poster-header {{
    {header_bg_css}
    color: var(--text-light);
    display: flex;
    align-items: center;
    padding: var(--header-padding);
    gap: 8mm;
    flex-shrink: 0;
}}
.logos {{
    display: flex;
    flex-direction: column;
    gap: 3mm;
    flex-shrink: 0;
    align-items: center;
}}
.logos img {{
    height: 55mm;
    width: auto;
    max-width: 90mm;
    object-fit: contain;
}}
.poster-header .title-block {{
    flex: 1;
    text-align: center;
}}
.poster-header .title-block h1 {{
    font-family: var(--font-heading);
    font-size: calc(16mm * var(--font-scale));
    font-weight: 800;
    line-height: 1.2;
    margin-bottom: 2mm;
}}
.poster-header .title-block .subtitle {{
    font-family: var(--font-body);
    font-size: calc(9mm * var(--font-scale));
    opacity: 0.9;
    margin-bottom: 2mm;
}}
.authors-block {{
    font-family: var(--font-body);
    font-size: calc(7mm * var(--font-scale));
}}
.authors {{ margin-bottom: 1mm; }}
.author {{ font-weight: 600; }}
.affiliations {{ font-size: calc(6mm * var(--font-scale)); opacity: 0.85; }}
.qr-code {{
    flex-shrink: 0;
    background: white;
    padding: 4mm;
    border-radius: 4mm;
    display: flex;
    align-items: center;
    gap: 4mm;
}}
.qr-svg svg {{
    width: 55mm;
    height: 55mm;
    display: block;
}}
.qr-label {{
    font-size: 7mm;
    color: #333;
    font-family: var(--font-heading);
    font-weight: 700;
    max-width: 40mm;
    line-height: 1.3;
}}

/* Body - column layout */
.poster-body {{
    flex: 1;
    display: flex;
    flex-direction: row;
    padding: var(--poster-margin);
    gap: var(--column-gap);
    overflow: hidden;
    min-height: 0;
    background: var(--body-bg, var(--background));
    position: relative;
}}
.poster-column {{
    display: flex;
    flex-direction: column;
    gap: var(--cell-gap);
    min-width: 0;
    min-height: 0;
}}

/* Cells */
.cell {{
    background: var(--surface);
    border-radius: var(--cell-radius);
    box-shadow: var(--cell-shadow);
    border: var(--cell-border-width) solid var(--cell-border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
    min-height: 0;
}}
.cell-header {{
    color: var(--primary);
    font-family: var(--font-heading);
    font-size: var(--cell-heading-size);
    font-weight: var(--cell-heading-weight);
    padding: 4mm var(--cell-padding) 2mm;
    flex-shrink: 0;
    border-bottom: none;
}}
.cell-content-wrapper {{
    flex: 1;
    overflow: hidden;
    position: relative;
}}
.cell-content {{
    transform-origin: top left;
    padding: 2mm var(--cell-padding) 3mm;
    font-family: var(--font-body);
    font-size: calc(6mm * var(--font-scale));
    color: var(--text);
    line-height: 1.5;
}}
.cell-content h3 {{
    font-family: var(--font-heading);
    font-size: calc(5.5mm * var(--font-scale));
    font-weight: 700;
    margin: 3mm 0 2mm;
    color: var(--primary);
}}
.cell-content h4 {{
    font-family: var(--font-heading);
    font-size: calc(5mm * var(--font-scale));
    font-weight: 600;
    margin: 2mm 0 1.5mm;
}}
.cell-content p {{
    margin: 2mm 0;
}}
.cell-content ul, .cell-content ol {{
    margin: 2mm 0;
    padding-left: 10mm;
}}
.cell-content ol {{
    padding-left: 12mm;
}}
.cell-content li {{
    margin: 1mm 0;
}}
.cell-content img {{
    max-width: 100%;
    height: auto;
    display: block;
    margin: 3mm auto;
    border-radius: var(--img-radius);
    border: var(--img-border);
}}

/* Image grid - side by side images with captions below */
.image-grid {{
    display: flex;
    gap: 2mm;
    margin: 1.5mm 0;
    align-items: stretch;
    position: relative;
}}
.image-grid figure {{
    flex: 1;
    text-align: center;
    min-width: 0;
    display: flex;
    flex-direction: column;
}}
.image-grid figure .grid-img-wrap {{
    flex: 1;
    display: flex;
    align-items: flex-end;
    min-height: 0;
}}
.image-grid.align-top figure .grid-img-wrap {{ align-items: flex-start; }}
.image-grid.align-center figure .grid-img-wrap {{ align-items: center; }}
.image-grid figure .grid-img-wrap img {{
    width: 100%;
    height: auto;
    margin: 0;
    display: block;
    border-radius: var(--img-radius);
    border: var(--img-border);
}}
.image-grid figure figcaption {{
    font-size: calc(4mm * var(--font-scale));
    color: var(--text);
    padding-top: 1mm;
    font-weight: 600;
    text-align: center;
    flex-shrink: 0;
}}
.image-grid figure figcaption strong {{
    color: var(--primary);
}}

/* Standalone image with caption */
.img-figure {{
    text-align: center;
    margin: 3mm 0;
}}
.img-figure img {{
    max-width: 100%;
    height: auto;
    display: block;
    margin: 0 auto;
    border-radius: var(--img-radius);
    border: var(--img-border);
}}
.img-figure figcaption {{
    font-size: calc(4.5mm * var(--font-scale));
    color: var(--text);
    padding-top: 1.5mm;
    font-weight: 600;
    text-align: center;
}}
.img-figure figcaption strong {{
    color: var(--primary);
}}

/* Tables - contained within cells */
.cell-content .table-wrapper {{
    width: 100%;
    overflow-x: auto;
    margin: 3mm 0;
}}
.cell-content table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: calc(5mm * var(--font-scale));
    table-layout: fixed;
}}
.cell-content thead tr {{
    {table_hdr_bg_css}
}}
.cell-content th {{
    background: transparent;
    color: {table_hdr_text};
    padding: 2mm 2mm;
    text-align: left;
    font-weight: 600;
    font-size: calc(4.5mm * var(--font-scale));
    overflow: hidden;
    text-overflow: ellipsis;
    border: none;
}}
.cell-content td {{
    padding: 1.5mm 3mm;
    border-bottom: 0.3mm solid rgba(0,0,0,0.1);
}}
.cell-content tr:nth-child(even) td {{
    background: rgba(0,0,0,0.02);
}}
.cell-content strong {{
    color: var(--primary);
}}
.cell-content code {{
    background: rgba(0,0,0,0.06);
    padding: 0.5mm 1.5mm;
    border-radius: 1mm;
    font-size: 0.9em;
}}
.cell-content pre {{
    background: rgba(0,0,0,0.06);
    padding: 3mm;
    border-radius: 1.5mm;
    overflow-x: auto;
}}
.cell-content blockquote {{
    border-left: 1mm solid var(--secondary);
    padding-left: 4mm;
    margin: 3mm 0;
    color: #666;
    font-style: italic;
}}

/* Split cells */
.split-cell .split-container {{
    display: flex;
    gap: 3mm;
    flex: 1;
    min-height: 0;
    overflow: hidden;
}}
.subcell {{
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 0;
}}
.subcell-header {{
    color: var(--primary);
    background: none;
    font-size: calc(6mm * var(--font-scale));
    font-weight: var(--cell-heading-weight);
    padding: 2mm var(--cell-padding) 1mm;
}}

/* Split cell divider drag handle — absolutely positioned overlay to avoid layout shift */
.split-container {{
    position: relative;
}}
.split-divider {{
    display: none;
    position: absolute;
    top: 0;
    bottom: 0;
    width: 10mm;
    margin-left: -5mm;
    cursor: col-resize;
    z-index: 60;
}}
.edit-mode .split-divider {{
    display: block;
}}
.split-divider::after {{
    content: '';
    position: absolute;
    top: 5%;
    left: 50%;
    transform: translateX(-50%);
    width: 1.5mm;
    height: 90%;
    background: var(--secondary);
    border-radius: 1mm;
    opacity: 0.3;
    transition: opacity 0.2s, width 0.2s;
}}
.split-divider:hover::after,
.split-divider.active::after {{
    opacity: 0.9;
    width: 3mm;
}}

/* Mermaid */
.mermaid {{
    display: flex;
    justify-content: center;
    margin: 3mm 0;
}}
.mermaid svg {{
    max-width: 100%;
    height: auto;
}}

/* Math */
.math-display {{
    margin: 3mm 0;
    text-align: center;
    font-size: calc(7mm * var(--font-scale));
}}

/* Edit mode - hide editor elements by default */
.resize-handle, .cell-actions {{
    display: none;
}}
.edit-mode .cell {{
    cursor: grab;
}}
.edit-mode .cell:active {{
    cursor: grabbing;
}}
.edit-mode .cell.sortable-ghost {{
    opacity: 0.4;
}}
.edit-mode .cell.sortable-chosen {{
    box-shadow: 0 0 0 3px var(--secondary);
}}
.edit-mode .cell-actions {{
    display: flex;
    position: absolute;
    top: 4px;
    right: 4px;
    gap: 4px;
    z-index: 100;
    opacity: 0;
    transition: opacity 0.2s;
}}
.edit-mode .cell:hover .cell-actions {{
    opacity: 1;
}}
.cell-action-btn {{
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 4px;
    background: rgba(0,0,0,0.6);
    color: white;
    cursor: pointer;
    font-size: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
}}
.cell-action-btn:hover {{
    background: rgba(0,0,0,0.8);
}}

/* Resize handle (bottom of cell for height) */
.edit-mode .resize-handle {{
    display: block;
    position: absolute;
    bottom: 0;
    left: 10%;
    width: 80%;
    height: 6px;
    background: var(--secondary);
    border-radius: 3px;
    cursor: ns-resize;
    opacity: 0;
    transition: opacity 0.2s;
    z-index: 50;
}}
.edit-mode .cell:hover .resize-handle {{
    opacity: 0.7;
}}
.edit-mode .resize-handle:hover {{
    opacity: 1;
}}

/* Column divider (drag to resize columns) - absolutely positioned overlay */
.column-divider {{
    display: none;
    position: absolute;
    top: 0;
    bottom: 0;
    width: 10mm;
    margin-left: -5mm;
    cursor: col-resize;
    z-index: 60;
}}
.edit-mode .column-divider {{
    display: block;
}}
.edit-mode .column-divider::after {{
    content: '';
    position: absolute;
    top: 5%;
    left: 50%;
    transform: translateX(-50%);
    width: 1.5mm;
    height: 90%;
    background: var(--secondary);
    border-radius: 1mm;
    opacity: 0.3;
    transition: opacity 0.2s, width 0.2s;
}}
.edit-mode .column-divider:hover::after,
.edit-mode .column-divider.active::after {{
    opacity: 0.9;
    width: 3mm;
}}

/* Column width editor / toolbar */
.column-width-editor {{
    position: fixed;
    top: 10px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0,0,0,0.85);
    color: white;
    padding: 10px 20px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 15px;
    z-index: 1000;
    font-family: sans-serif;
    font-size: 14px;
    backdrop-filter: blur(10px);
}}
.save-btn {{
    padding: 6px 16px;
    background: var(--secondary);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 600;
}}
.save-btn:hover {{
    filter: brightness(1.1);
}}

/* Print */
@media print {{
    @page {{
        size: {css_w} {css_h};
        margin: 0;
    }}
    body {{
        background: white;
        padding: 0;
        margin: 0;
        width: {css_w};
        height: {css_h};
    }}
    .poster-viewport {{
        transform: none !important;
        margin: 0 !important;
    }}
    .poster {{
        box-shadow: none;
        width: {css_w} !important;
        height: {css_h} !important;
    }}
    /* Disable effects that render inconsistently across PDF viewers */
    .cell {{
        box-shadow: none !important;
    }}
    .column-width-editor,
    .cell-actions,
    .resize-handle,
    .column-divider {{
        display: none !important;
    }}
}}
</style>
</head>
<body>
<div class="poster-viewport {edit_class}">
    <div class="poster" id="poster">
        <div class="poster-header">
            {logos_html}
            <div class="title-block">
                <h1>{poster.title}</h1>
                {'<p class="subtitle">' + poster.subtitle + '</p>' if poster.subtitle else ''}
                {authors_html}
            </div>
            {qr_html}
        </div>
        <div class="poster-body" id="poster-body" data-columns="{','.join(str(c) for c in columns)}">
            {body_html}
        </div>
    </div>
</div>

<script>
// Initialize Mermaid
mermaid.initialize({{
    startOnLoad: true,
    theme: '{mermaid_theme}',
    themeVariables: {{
        primaryColor: '{colors["secondary"]}',
        primaryTextColor: '{colors.get("text", "#333")}',
        primaryBorderColor: '{colors["primary"]}',
        lineColor: '{colors["primary"]}',
        secondaryColor: '{colors["accent"]}',
        tertiaryColor: '{colors["background"]}',
        fontFamily: "'{fonts['body']}', sans-serif",
        background: '{mermaid_bg}',
        mainBkg: '{colors["surface"]}',
        nodeBorder: '{colors["primary"]}',
        clusterBkg: '{colors["background"]}',
    }}
}});

// Wrap tables in a scrollable container to prevent overflow
document.addEventListener('DOMContentLoaded', () => {{
    document.querySelectorAll('.cell-content table').forEach(table => {{
        if (!table.parentElement.classList.contains('table-wrapper')) {{
            const wrapper = document.createElement('div');
            wrapper.className = 'table-wrapper';
            table.parentNode.insertBefore(wrapper, table);
            wrapper.appendChild(table);
        }}
    }});
}});

// Compute the scale needed for a single cell's content to fit its wrapper
function computeCellScale(wrapper) {{
    const content = wrapper.querySelector('.cell-content');
    if (!content) return null;

    // Reset transform so we measure unscaled content
    content.style.transform = 'none';
    content.style.width = '';

    const availW = wrapper.clientWidth;
    const availH = wrapper.clientHeight;
    if (availW <= 0 || availH <= 0) return null;

    // Measure full content height
    const contentH = content.scrollHeight;
    let scale = 1.0;
    if (contentH > 0) {{
        scale = availH / contentH;
    }}

    return {{ wrapper, content, scale, availW }};
}}

function applyCellScale(info) {{
    if (!info) return;
    const {{ content, scale, availW }} = info;
    content.style.width = (availW / scale) + 'px';
    content.style.transform = 'scale(' + scale + ')';
    content.style.transformOrigin = 'top left';
}}

function scaleAllCells() {{
    // First, compute scales for all wrappers
    const allInfos = [];
    document.querySelectorAll('.cell-content-wrapper').forEach(w => {{
        allInfos.push(computeCellScale(w));
    }});

    // Collect all scales that need to shrink (< 1.0) to find the tightest cell
    const shrinkScales = allInfos.filter(i => i && i.scale < 1.0).map(i => i.scale);
    // The global floor: no cell shrinks more than 0.5
    const globalFloor = 0.5;
    // The cap for scaling up: don't let fonts get more than 1.3x
    const maxScale = 1.3;

    allInfos.forEach(info => {{
        if (info) {{
            info.scale = Math.max(globalFloor, Math.min(info.scale, maxScale));
        }}
    }});

    // For split cells, enforce uniform scale across subcells
    document.querySelectorAll('.split-cell').forEach(splitCell => {{
        const wrappers = splitCell.querySelectorAll('.subcell .cell-content-wrapper');
        let minScale = Infinity;
        const subcellInfos = [];
        wrappers.forEach(w => {{
            const info = allInfos.find(i => i && i.wrapper === w);
            if (info) {{
                subcellInfos.push(info);
                if (info.scale < minScale) minScale = info.scale;
            }}
        }});
        subcellInfos.forEach(info => {{ info.scale = minScale; }});
    }});

    // Apply all scales
    allInfos.forEach(applyCellScale);
    // Notify divider handles to reposition after scale change
    window.dispatchEvent(new Event('cellsscaled'));
}}

// Auto-scale poster to viewport
function fitToViewport() {{
    const viewport = document.querySelector('.poster-viewport');
    const poster = document.getElementById('poster');
    const toolbarH = document.querySelector('.column-width-editor') ? 60 : 0;
    const vw = window.innerWidth - 40;
    const vh = window.innerHeight - 40 - toolbarH;
    const pw = poster.offsetWidth;
    const ph = poster.offsetHeight;
    const scale = Math.min(vw / pw, vh / ph, 1);
    viewport.style.transform = 'scale(' + scale + ')';
    viewport.style.marginBottom = (ph * scale - ph) + 'px';
}}

// Init KaTeX after load
function initMath() {{
    if (typeof renderMathInElement !== 'undefined') {{
        renderMathInElement(document.body, {{
            delimiters: [
                {{left: '\\\\[', right: '\\\\]', display: true}},
                {{left: '\\\\(', right: '\\\\)', display: false}},
                {{left: '$$', right: '$$', display: true}},
                {{left: '$', right: '$', display: false}},
            ],
            throwOnError: false,
        }});
    }} else {{
        setTimeout(initMath, 200);
    }}
}}

window.addEventListener('load', () => {{
    initMath();
    fitToViewport();
    setTimeout(() => {{
        scaleAllCells();
        fitToViewport();
    }}, 1000);
}});
window.addEventListener('resize', () => {{
    fitToViewport();
}});
</script>
{edit_scripts}
</body>
</html>"""
    return html
