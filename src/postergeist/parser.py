"""Parse poster markdown files into structured data."""

import re
import yaml
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Cell:
    id: str
    title: str
    content: str  # raw markdown content
    column: int = -1  # -1 = auto-assign
    height: float = 1.0  # relative height within column (flex value)
    split: bool = False
    subcells: list["Cell"] = field(default_factory=list)


@dataclass
class Poster:
    frontmatter: dict
    cells: list[Cell] = field(default_factory=list)
    source_path: Path | None = None

    @property
    def title(self) -> str:
        return self.frontmatter.get("title", "Untitled Poster")

    @property
    def subtitle(self) -> str:
        return self.frontmatter.get("subtitle", "")

    @property
    def authors(self) -> list[dict]:
        return self.frontmatter.get("authors", [])

    @property
    def affiliations(self) -> list[dict]:
        return self.frontmatter.get("affiliations", [])

    @property
    def poster_config(self) -> dict:
        return self.frontmatter.get("poster", {})

    def get_columns(self) -> list[list["Cell"]]:
        """Organize cells into columns for rendering."""
        num_cols = len(self.poster_config.get("columns", [1, 1, 1]))
        columns: list[list[Cell]] = [[] for _ in range(num_cols)]

        # Group cells by --- separators (stored as column=-1 groups)
        # Cells with explicit column assignments go directly
        # Auto-assigned cells distribute round-robin within their group
        group: list[Cell] = []
        groups: list[list[Cell]] = []

        for cell in self.cells:
            if cell.id.startswith("__sep__"):
                if group:
                    groups.append(group)
                    group = []
                continue
            group.append(cell)
        if group:
            groups.append(group)

        for grp in groups:
            auto_col = 0
            for cell in grp:
                if cell.column >= 0:
                    target = min(cell.column, num_cols - 1)
                else:
                    target = auto_col % num_cols
                    auto_col += 1
                columns[target].append(cell)

        return columns


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and return (config, body)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    fm = text[3:end].strip()
    body = text[end + 3:].strip()
    return yaml.safe_load(fm) or {}, body


def _parse_meta_value(v: str):
    """Parse a metadata value string to int, float, bool, or str."""
    v = v.strip()
    if v.isdigit():
        return int(v)
    try:
        return float(v)
    except ValueError:
        pass
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    return v


def parse_cell_meta(content: str) -> tuple[dict, str]:
    """Extract <!-- key: value --> metadata from cell content."""
    meta = {}
    def replace_meta(m):
        for pair in m.group(1).split(","):
            pair = pair.strip()
            if ":" in pair:
                k, v = pair.split(":", 1)
                meta[k.strip()] = _parse_meta_value(v)
        return ""

    cleaned = re.sub(r"<!--\s*(.+?)\s*-->", replace_meta, content, count=1)
    return meta, cleaned.strip()


def parse_markdown(text: str) -> Poster:
    """Parse a poster markdown file into a Poster structure."""
    frontmatter, body = parse_frontmatter(text)

    # Protect code blocks from being split
    code_blocks = {}
    counter = [0]

    def protect_code(m):
        key = f"__CODE_BLOCK_{counter[0]}__"
        code_blocks[key] = m.group(0)
        counter[0] += 1
        return key

    protected = re.sub(r"```[\s\S]*?```", protect_code, body)

    # Split on horizontal rules (3+ dashes on their own line)
    raw_groups = re.split(r"\n\s*-{3,}\s*\n", protected)

    cells = []
    cell_id = 0

    for group_idx, raw_group in enumerate(raw_groups):
        if group_idx > 0:
            # Insert separator marker
            cells.append(Cell(id=f"__sep__{group_idx}", title="", content=""))

        # Split group into cells by ## headings
        parts = re.split(r"(?=^## )", raw_group.strip(), flags=re.MULTILINE)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Restore code blocks
            for key, val in code_blocks.items():
                part = part.replace(key, val)

            # Extract title from ## heading
            heading_match = re.match(r"^## (.+?)(?:\s*\{.*?\})?\s*$", part, re.MULTILINE)
            if heading_match:
                title = heading_match.group(1).strip()
                content = part[heading_match.end():].strip()
            else:
                title = ""
                content = part

            # Parse cell metadata
            meta, content = parse_cell_meta(content)

            # Check for split cells
            subcells = []
            is_split = meta.get("split", False)

            if "|||" in content:
                is_split = True
                sub_parts = content.split("|||")
                for si, sub_part in enumerate(sub_parts):
                    sub_part = sub_part.strip()
                    sub_heading = re.match(r"^### (.+?)\s*$", sub_part, re.MULTILINE)
                    if sub_heading:
                        sub_title = sub_heading.group(1).strip()
                        sub_content = sub_part[sub_heading.end():].strip()
                    else:
                        sub_title = ""
                        sub_content = sub_part
                    subcells.append(Cell(
                        id=f"cell-{cell_id}-sub-{si}",
                        title=sub_title,
                        content=sub_content,
                    ))

            cell = Cell(
                id=f"cell-{cell_id}",
                title=title,
                content=content if not is_split else "",
                column=meta.get("col", -1),
                height=meta.get("h", 1.0),
                split=is_split,
                subcells=subcells,
            )
            cells.append(cell)
            cell_id += 1

    return Poster(frontmatter=frontmatter, cells=cells)


def parse_file(path: str | Path) -> Poster:
    """Parse a poster markdown file."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    poster = parse_markdown(text)
    poster.source_path = path
    return poster


def serialize_poster(poster: Poster) -> str:
    """Serialize a Poster back to markdown format."""
    parts = ["---"]
    parts.append(yaml.dump(poster.frontmatter, default_flow_style=False, sort_keys=False).strip())
    parts.append("---\n")

    need_sep = False
    for cell in poster.cells:
        if cell.id.startswith("__sep__"):
            need_sep = True
            continue

        if need_sep:
            parts.append("\n---\n")
            need_sep = False

        if cell.title:
            parts.append(f"## {cell.title}\n")
        meta_parts = []
        if cell.column >= 0:
            meta_parts.append(f"col: {cell.column}")
        if cell.height != 1.0:
            meta_parts.append(f"h: {cell.height}")
        if cell.split:
            meta_parts.append("split: true")
        if meta_parts:
            parts.append(f"<!-- {', '.join(meta_parts)} -->\n")

        if cell.split and cell.subcells:
            for si, sub in enumerate(cell.subcells):
                if si > 0:
                    parts.append("\n|||\n")
                if sub.title:
                    parts.append(f"### {sub.title}\n")
                parts.append(sub.content + "\n")
        else:
            parts.append(cell.content + "\n")

        parts.append("")

    return "\n".join(parts)
