---
name: paper-to-poster
description: This skill should be used when the user asks to "create a poster from a paper", "generate a poster from a PDF", "make a conference poster", "convert paper to poster", "poster from arxiv", "poster from URL", or mentions creating an academic poster from a research paper PDF or paper URL.
argument-hint: <path or URL to paper PDF> [conference name or style notes]
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch, Agent
---

# Paper-to-Poster Skill

Convert an academic paper PDF into a polished 3-column Postergeist markdown poster. This is a multi-pass process: extract content, generate poster, review for accuracy, and optimize whitespace.

## Step 0: Setup

Get the PDF path or URL from `$ARGUMENTS`. If no path is provided, ask the user for the PDF file path or URL. Optionally, the user may also provide a conference name or style notes after the path.

**URL support:** If the argument is a URL (starts with `http://` or `https://`), download the PDF first:

```bash
curl -L -o /tmp/paper.pdf "<url>"
```

Common academic PDF URL patterns to handle:
- ArXiv: `https://arxiv.org/abs/XXXX.XXXXX` → convert to `https://arxiv.org/pdf/XXXX.XXXXX`
- ArXiv PDF: `https://arxiv.org/pdf/XXXX.XXXXX` → use directly
- Direct PDF links: any URL ending in `.pdf` → use directly
- Other URLs: try to fetch and check if the response is a PDF

Determine the output directory. If the input was a URL, create a new directory based on the paper title (determined after extraction). If the input was a local file, create the poster in the same directory as the PDF. Create an `images/` subdirectory for extracted figures.

Ensure the environment is installed:

```bash
uv sync --extra nougat
```

## Step 1: Extract Paper Content

Run the built-in extraction module to extract text and figures from the PDF:

```bash
uv run python -m postergeist.extract "<pdf_path>" "<output_dir>/images"
```

To skip Nougat (faster, but no equation support):
```bash
uv run python -m postergeist.extract "<pdf_path>"  "<output_dir>/images" --no-nougat
```

This produces:
- `<output_dir>/extracted_text.txt` — full text organized by page
- `<output_dir>/figures_meta.json` — metadata for each extracted figure (filename, page, caption, aspect ratio, dimensions)
- `<output_dir>/images/fig1_p1.png ...` — extracted figure images at 150 DPI

After extraction, read the `extracted_text.txt` and `figures_meta.json` files to understand the paper's content and available figures.

## Step 2: Generate the Poster Markdown

Read the extracted text carefully. Identify these sections from the paper:
- **Title, authors, affiliations** (from the first page)
- **Abstract / introduction** (motivation, problem statement)
- **Method** (approach, architecture, key equations)
- **Results** (quantitative tables, qualitative figures, comparisons)
- **Ablations** (supporting experiments, analysis)
- **References** (select 3-5 key references)

Read `figures_meta.json` to understand available images and their aspect ratios. Assign figures to columns:
- Wide/landscape figures (aspect > 1.5) go to **Column 1** (the wide center column)
- Narrow/portrait figures go to **Columns 0 or 2** (side columns)
- The most impactful result figure should be prominent in Column 1

### Poster Structure

Create `poster.md` with the following Postergeist frontmatter and 3-column layout:

**Frontmatter:**
```yaml
---
title: "<Paper Title>"
subtitle: "<Conference or short description>"
authors:
  - name: "<Author 1>"
    affiliation: "1"
affiliations:
  - key: "1"
    name: "<University/Institution>"
poster:
  size: A0-landscape
  template: gradient
  columns: [1, 2, 1]
  font_scale: 1.0
  colors:
    primary: '#2d1b69'
    secondary: '#A382FF'
---
```

If the user provided a conference name, use it as the subtitle. Pick colors that feel appropriate for the venue or topic.

**Column 0 (Left, narrow) -- Setting the Stage:**
- Cell: Problem statement / motivation. Use a blockquote for the key challenge.
- Cell: Background / related context. Keep it brief.
- Cell: Approach overview. Consider a mermaid diagram for the pipeline if the method has clear stages.
- Cell: Key equation(s) if central to the contribution, using `$$...$$` display math.

**Column 1 (Center, wide) -- The Star:**
- Cell: Method overview with the main architecture/method figure as a large image.
- Cell: Qualitative results — combine the main comparison figure AND supporting result grids in ONE cell for space efficiency. Put the main comparison figure at the top, then stack `{grid:2}` blocks to show result pairs. Prefer `{grid:2}` over `{grid:4}` — 4 images in a row become too small.
- Cell: Quantitative results table if it is the paper's crown jewel. Bold the best results with `**Ours**`.

**Column 2 (Right, narrow) -- Supporting Evidence:**
- Cell: Comparison table with baselines. Use markdown tables with bolded best results.
- Cell: Ablation study results (table or small figure).
- Cell: Additional analysis or supplementary results.
- Cell: Key references (3-5 most relevant, formatted as a compact list).

Use ALL available Postergeist features where they fit naturally:
- `split: true` cells for side-by-side comparisons
- `{grid:2}` for image pairs, `{grid:3}` for triples — avoid `{grid:4}` as images become too small
- Mermaid diagrams for method pipelines
- `$$...$$` for important equations
- `>` blockquotes for key takeaways or findings
- Bold (`**...**`) for emphasis on results
- Tables for quantitative comparisons

**Image grid layout tips:**
- Use `{grid:2}` blocks stacked vertically instead of one `{grid:4}` — images stay larger and more readable
- Place the grid tag and its images with NO blank line between them (they must be in the same markdown paragraph)
- Use `{w:N}` weights when images have different aspect ratios to allocate proportional space

Set cell heights using `<!-- col: N, h: X.X -->` comments. **CRITICAL: The comment MUST come AFTER the `## Heading`, not before it.** Placing it before creates an empty cell.

Correct:
```markdown
## My Cell Title
<!-- col: 0, h: 0.8 -->

Cell content here...
```

Wrong (creates empty cell):
```markdown
<!-- col: 0, h: 0.8 -->
## My Cell Title
```

**Every `## Heading` cell MUST have a `<!-- col: N, h: X.X -->` comment** to ensure it lands in the correct column. Without it, cells are auto-assigned round-robin which leads to wrong placement.

Height guidelines:
- Narrow column cells: `h: 0.8` to `h: 1.2`
- Wide column cells with figures: `h: 1.5` to `h: 2.0`
- Small text-only cells: `h: 0.5` to `h: 0.8`

Heights are fractional units relative to the poster height. All cells in the poster across all columns should sum to roughly the same total height per column.

Write the complete `poster.md` file to the output directory.

## Step 3: Review and Refine

This step is critical. Read back the generated `poster.md` in full and evaluate it against the original `extracted_text.txt`:

1. **Contribution check:** Does the poster clearly communicate the paper's main contribution? A reader should understand what is new within 10 seconds of looking at the center column.
2. **Narrative flow:** Does it follow a logical story? Left column sets up the problem, center shows the solution and results, right provides supporting evidence.
3. **Key results:** Are the most important quantitative results (SOTA numbers, improvements) prominently displayed? Are they bolded in tables?
4. **Figure selection:** Are the best figures used? Is the main result figure large and centered? Are figures placed in appropriate columns based on aspect ratio?
5. **Completeness:** Are any critical elements missing (key equations, important baselines, ablations)?
6. **Visual balance:** Do the columns feel roughly balanced in content density?

Fix any issues found. Update `poster.md` using the Edit tool. Common fixes:
- Adding missing key results or findings as blockquotes
- Reordering cells for better narrative flow
- Adjusting image grid layouts
- Adding mermaid diagrams for method pipelines that were missed
- Fixing table formatting

## Step 4: Whitespace Optimization

Start the Postergeist dev server to measure the actual rendered layout:

```bash
postergeist serve poster.md --no-browser &
```

Wait a moment for the server to start (it serves on `http://localhost:1234` by default).

Use the Claude Preview tool to take a screenshot of the rendered poster and visually inspect the layout. Look for:
- Cells with excessive empty space at the bottom
- Columns that are too sparse or too packed
- Figures that are too small or too large

Adjust cell heights (`h: X.X` values) in the markdown to minimize whitespace. Guidelines:
- If a cell has lots of empty space, reduce its `h` value by 0.1-0.2
- If content is clipped or cramped, increase `h` by 0.1-0.2
- Ensure total height per column is balanced (all columns should sum to approximately the same total `h`)
- Text-heavy cells need less height than image-heavy cells

After adjustments, take another screenshot to verify. Iterate 1-2 times if needed.

Kill the server when done:

```bash
kill %1 2>/dev/null
```

## Output

When complete, report to the user:
- Path to the generated `poster.md`
- Path to the `images/` directory with extracted figures
- Number of figures extracted and used
- Summary of the poster structure (how many cells per column)
- Any issues encountered (missing figures, unclear sections in the paper)

The user can then run `postergeist serve poster.md` to preview their poster or `postergeist render poster.md` to export it.
