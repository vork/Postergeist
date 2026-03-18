"""Built-in poster templates with configurable colors and fonts."""

TEMPLATES = {
    "classic": {
        "name": "Classic Academic",
        "description": "Traditional academic poster with bold header and warm accents",
        "colors": {
            "primary": "#2d1b69",
            "secondary": "#e87f24",
            "accent": "#f5a623",
            "background": "#ffffff",
            "surface": "#ffffff",
            "text": "#333333",
            "text_light": "#ffffff",
            "header_bg": "#2d1b69",
            "cell_border": "#2d1b69",
            "poster_bg": "#2d1b69",
            "table_header_bg": "#2d1b69",
            "table_header_text": "#ffffff",
        },
        "fonts": {
            "heading": "DM Sans",
            "body": "Source Serif 4",
        },
        "style": {
            "cell_radius": "0px",
            "cell_shadow": "none",
            "cell_border_width": "0px",
            "cell_padding": "5mm",
            "cell_gap": "0mm",
            "column_gap": "5mm",
            "poster_margin": "10mm",
            "header_padding": "6mm 10mm",
            "header_layout": "banner",
        },
    },
    "modern-dark": {
        "name": "Modern Dark",
        "description": "Sleek dark theme with neon accents and glassmorphism",
        "colors": {
            "primary": "#00d4ff",
            "secondary": "#00d4ff",
            "accent": "#ff6b9d",
            "background": "#1a1a2e",
            "surface": "rgba(255,255,255,0.06)",
            "text": "#e0e0e0",
            "text_light": "#ffffff",
            "header_bg": "#0f0f1a",
            "cell_border": "rgba(0,212,255,0.2)",
            "poster_bg": "#0f0f1a",
            "table_header_bg": "#00d4ff",
            "table_header_text": "#0f0f1a",
        },
        "fonts": {
            "heading": "Oswald",
            "body": "Montserrat",
        },
        "style": {
            "cell_radius": "4mm",
            "cell_shadow": "0 2mm 8mm rgba(0,0,0,0.3)",
            "cell_border_width": "0.3mm",
            "cell_padding": "5mm",
            "cell_gap": "4mm",
            "column_gap": "5mm",
            "poster_margin": "10mm",
            "header_padding": "6mm 10mm",
            "header_layout": "banner",
            "image_border": "0.3mm solid rgba(255,255,255,0.12)",
            "image_radius": "2mm",
        },
    },
    "minimal": {
        "name": "Minimal Clean",
        "description": "Clean white design with subtle borders and elegant typography",
        "colors": {
            "primary": "#1a1a1a",
            "secondary": "#0066cc",
            "accent": "#0066cc",
            "background": "#fafafa",
            "surface": "#ffffff",
            "text": "#1a1a1a",
            "text_light": "#ffffff",
            "header_bg": "#1a1a1a",
            "cell_border": "#e0e0e0",
            "poster_bg": "#f0f0f0",
            "table_header_bg": "#1a1a1a",
            "table_header_text": "#ffffff",
        },
        "fonts": {
            "heading": "Averia Serif Libre",
            "body": "Geist",
        },
        "style": {
            "cell_radius": "1mm",
            "cell_shadow": "0 0.3mm 1mm rgba(0,0,0,0.08)",
            "cell_border_width": "0.3mm",
            "cell_padding": "5mm",
            "cell_gap": "3mm",
            "column_gap": "5mm",
            "poster_margin": "10mm",
            "header_padding": "6mm 10mm",
            "header_layout": "banner",
        },
    },
    "gradient": {
        "name": "Modern Gradient",
        "description": "Vibrant gradient header with rounded cards and soft shadows",
        "colors": {
            "primary": "#667eea",
            "secondary": "#764ba2",
            "accent": "#f093fb",
            "background": "#f5f7fa",
            "surface": "#ffffff",
            "text": "#2d3748",
            "text_light": "#ffffff",
            "header_bg": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            "cell_border": "rgba(102,126,234,0.2)",
            "poster_bg": "#f5f7fa",
            "table_header_bg": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            "table_header_text": "#ffffff",
        },
        "fonts": {
            "heading": "Poppins",
            "body": "Lora",
        },
        "style": {
            "cell_radius": "4mm",
            "cell_shadow": "0 1mm 5mm rgba(0,0,0,0.08)",
            "cell_border_width": "0px",
            "cell_padding": "6mm",
            "cell_gap": "4mm",
            "column_gap": "5mm",
            "poster_margin": "10mm",
            "header_padding": "6mm 10mm",
            "header_layout": "banner",
        },
    },
    "modern-light": {
        "name": "Modern Light",
        "description": "Light counterpart to Modern Dark with the same fonts and layout",
        "colors": {
            "primary": "#00a8cc",
            "secondary": "#00d4ff",
            "accent": "#ff6b9d",
            "background": "#f0f2f5",
            "surface": "#ffffff",
            "text": "#1a1a2e",
            "text_light": "#ffffff",
            "header_bg": "#1a1a2e",
            "cell_border": "rgba(0,168,204,0.15)",
            "poster_bg": "#e8eaed",
            "table_header_bg": "#00d4ff",
            "table_header_text": "#0f0f1a",
        },
        "fonts": {
            "heading": "Oswald",
            "body": "Montserrat",
        },
        "style": {
            "cell_radius": "4mm",
            "cell_shadow": "0 2mm 8mm rgba(0,0,0,0.08)",
            "cell_border_width": "0.3mm",
            "cell_padding": "5mm",
            "cell_gap": "4mm",
            "column_gap": "5mm",
            "poster_margin": "10mm",
            "header_padding": "6mm 10mm",
            "header_layout": "banner",
        },
    },
}


def get_template(name: str, search_dir: "Path | None" = None) -> dict:
    """Get a template by name. Searches built-in templates first, then YAML files in search_dir."""
    if name in TEMPLATES:
        return TEMPLATES[name]

    # Try loading from a YAML file next to the poster
    if search_dir:
        import yaml
        from pathlib import Path
        for ext in (".yaml", ".yml"):
            theme_path = Path(search_dir) / f"{name}{ext}"
            if theme_path.exists():
                data = yaml.safe_load(theme_path.read_text(encoding="utf-8"))
                if data:
                    # Ensure all required keys exist with defaults
                    base = {
                        "name": data.get("name", name),
                        "description": data.get("description", ""),
                        "colors": {**TEMPLATES["classic"]["colors"], **data.get("colors", {})},
                        "fonts": {**TEMPLATES["classic"]["fonts"], **data.get("fonts", {})},
                        "style": {**TEMPLATES["classic"]["style"], **data.get("style", {})},
                    }
                    return base

    available = list(TEMPLATES.keys())
    if search_dir:
        from pathlib import Path
        for f in Path(search_dir).glob("*.yaml"):
            available.append(f.stem)
        for f in Path(search_dir).glob("*.yml"):
            available.append(f.stem)
    raise ValueError(
        f"Unknown template: {name}. Available: {', '.join(sorted(set(available)))}"
    )


def merge_config(template: dict, overrides: dict) -> dict:
    """Merge user overrides into template defaults."""
    import copy
    result = copy.deepcopy(template)
    for key in ("colors", "fonts", "style"):
        if key in overrides:
            result[key].update(overrides[key])
    return result
