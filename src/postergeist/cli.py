"""CLI for Postergeist."""

import argparse
import sys
from pathlib import Path

from .templates import TEMPLATES


EXAMPLE_POSTER = '''---
title: "SF3D: Stable Fast 3D Mesh Reconstruction with UV-unwrapping and Illumination Disentanglement"
subtitle: ""
authors:
  - name: Mark Boss
    affiliation: "1"
  - name: Zixuan Huang
    affiliation: "1,2"
  - name: Aaryaman Vasishta
    affiliation: "1"
  - name: Varun Jampani
    affiliation: "1"
affiliations:
  - key: "1"
    name: Stability AI
  - key: "2"
    name: UIUC
poster:
  size: A0-landscape
  template: classic
  columns: [1, 2, 1]
  logo: images/logo.png
  qr_code: https://stable-fast-3d.github.io
  qr_label: "Project Page with Code and Video"
  colors:
    primary: "#2d1b69"
    secondary: "#e87f24"
  fonts:
    heading: Roboto Slab
    body: Open Sans
---

## SF3D Improvements

Previous methods had several issues:

- Light baked into the albedo, which means relighting is not possible
- Vertex colors cannot capture high resolution textures
- Artifacts from Marching Cubes
- Without any material predictions, relightings remain flat

![improvements](images/improvements.png)

---

## Method
<!-- span: 2 -->

![pipeline](images/pipeline.png)

**SF3D**

- **Fast Generation** Feed-Forward Transformer tuned for explicit mesh generation in 0.3s
- **UV Unwrapping** Our implementation enables textures in 200ms
- **Architectural Upgrades** Higher resolution triplanes offer more detail

**Delighting** By performing light estimation and inverse rendering, our albedo textures are delit

**Explicit Materials** Additional material parameters enable richer relightings

**SOTA-Performance** SOTA in terms of speed and quality at the same time

## Export

### UV Unwrapping

- Connected Mesh with UV Island Merging
- UV Disconnectional Darts and UV Island Merges
- Normal Threshold + Scaling

### Process

1. Visible Surfaces extraction
2. Find Occlusion
3. Generate UV Atlas
4. Remove non-mapped surfaces

---

## Topology
<!-- split: true -->

### Topology

- No Vertex Deform vs Vertex Deform
- Quad mesh generation
- By explicitly learning vertex deformations, our meshes can capture fine geometry

|||

### Aliasing Issues

- GT vs Low-Res vs High-Res comparison
- Low resolution triplanes as seen in previous work can lead to severe aliasing

## Comparison - GSO/OmniObject
<!-- span: 2 -->

### Visual Comparisons

| Method | Time | $\\text{CD}_\\downarrow$ | PSNR $\\uparrow$ | SSIM $\\uparrow$ | LPIPS $\\downarrow$ |
|--------|------|------|------|------|-------|
| ZeroShape | 0.9s | 0.160 | 15.689 | 0.787 | 0.206 |
| OpenLRM | 2.0 | 0.160 | 15.689 | 0.787 | 0.206 |
| TripoSR | 0.8 | 0.111 | 16.449 | 0.789 | 0.184 |
| **SF3D (Ours)** | **0.3** | **0.090** | **17.016** | **0.821** | **0.152** |

> Our method is the best method in terms of speed and reconstruction quality

## Speed vs. Quality

### Performance Plot

Our method achieves state-of-the-art results while being significantly faster than all competing methods.

$$\\text{Quality} = \\frac{\\text{PSNR} \\times \\text{SSIM}}{\\text{Time}}$$

Key findings:
- **3x faster** than nearest competitor
- **Higher PSNR** across all benchmarks
- **Better SSIM** scores on both GSO and OmniObject datasets

---

## Decomposition Results

### Material Decomposition

Our method decomposes rendered images into:

- **Diffuse** albedo (delit)
- **Roughness** map
- **Metallic** map
- **Normal** map
- **Relight 1 & 2** demonstrations

Our method clearly captures the geometry well and creates plausible novel views. It also captures reflections and lighting better due to our explicit inverse rendering.

## References & Acknowledgements
<!-- span: 2 -->

1. ZeroShape: Zero-shot 3D shape generation
2. OpenLRM: Open-source Large Reconstruction Model
3. TripoSR: Fast 3D reconstruction from single images
4. LGM: Large Gaussian Model for 3D generation
5. CRM: Convolutional Reconstruction Model
6. InstantMesh: Efficient 3D mesh generation
7. LN3Diff: Learning Normal Fields for 3D generation
8. 3DTopia-XL: Large-scale 3D generation

**Acknowledgements:** We thank the Stability AI team for support and compute resources.
'''


def cmd_new(args):
    """Create a new poster from a template."""
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "images").mkdir(exist_ok=True)

    poster_file = out_dir / "poster.md"

    if args.example:
        poster_file.write_text(EXAMPLE_POSTER, encoding="utf-8")
        print(f"Created example poster at {poster_file}")
    else:
        template = args.template or "classic"
        if template not in TEMPLATES:
            print(f"Unknown template: {template}")
            print(f"Available: {', '.join(TEMPLATES.keys())}")
            sys.exit(1)

        t = TEMPLATES[template]
        # Generate a starter poster
        starter = f'''---
title: "Your Poster Title"
subtitle: "Optional Subtitle"
authors:
  - name: Author Name
    affiliation: "1"
affiliations:
  - key: "1"
    name: University Name
poster:
  size: A0-landscape
  template: {template}
  columns: [1, 2, 1]
  logo: images/logo.png
  qr_code: https://your-project-page.com
  colors:
    primary: "{t['colors']['primary']}"
    secondary: "{t['colors']['secondary']}"
  fonts:
    heading: "{t['fonts']['heading']}"
    body: "{t['fonts']['body']}"
---

## Introduction

Your introduction text here. Supports **bold**, *italic*, and other markdown.

$$E = mc^2$$

## Method

Describe your method here.

```mermaid
graph LR
    A[Input] --> B[Process]
    B --> C[Output]
```

## Key Insight

Highlight your main contribution here.

---

## Results

Your results and tables here.

| Method | Score |
|--------|-------|
| Baseline | 0.75 |
| Ours | **0.95** |

## Analysis

Detailed analysis of the results.

## Conclusion

Your conclusions here.
'''
        poster_file.write_text(starter, encoding="utf-8")
        print(f"Created new poster at {poster_file} (template: {template})")

    print(f"Run: postergeist serve {poster_file}")


def cmd_serve(args):
    """Start the development server."""
    from .server import run_server
    run_server(
        poster_path=args.file,
        host=args.host,
        port=args.port,
        edit_mode=not args.preview,
        open_browser=not args.no_browser,
    )


def cmd_export(args):
    """Export poster to standalone HTML."""
    from .parser import parse_file
    from .renderer import render_poster

    poster = parse_file(args.file)
    html = render_poster(poster, edit_mode=False, base_url=".")

    out = Path(args.output or "poster.html")
    out.write_text(html, encoding="utf-8")
    print(f"Exported to {out}")


def cmd_templates(args):
    """List available templates."""
    for name, t in TEMPLATES.items():
        print(f"  {name:20s} {t['name']} - {t['description']}")


def main():
    parser = argparse.ArgumentParser(
        prog="postergeist",
        description="Academic poster generator from Markdown to HTML",
    )
    sub = parser.add_subparsers(dest="command")

    # new
    p_new = sub.add_parser("new", help="Create a new poster")
    p_new.add_argument("output", help="Output directory")
    p_new.add_argument("-t", "--template", default="classic", help="Template name")
    p_new.add_argument("--example", action="store_true", help="Create SF3D example poster")

    # serve
    p_serve = sub.add_parser("serve", help="Start development server")
    p_serve.add_argument("file", help="Poster markdown file")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--preview", action="store_true", help="Preview mode (no editing)")
    p_serve.add_argument("--no-browser", action="store_true", help="Don't open browser")

    # export
    p_export = sub.add_parser("export", help="Export to standalone HTML")
    p_export.add_argument("file", help="Poster markdown file")
    p_export.add_argument("-o", "--output", help="Output HTML file")

    # templates
    sub.add_parser("templates", help="List available templates")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    {"new": cmd_new, "serve": cmd_serve, "export": cmd_export, "templates": cmd_templates}[args.command](args)


if __name__ == "__main__":
    main()
