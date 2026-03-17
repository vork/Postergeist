"""Development server with live reload and editing capabilities."""

import json
import time
import threading
from pathlib import Path

from flask import Flask, Response, request, send_from_directory, jsonify
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .parser import parse_file, serialize_poster
from .renderer import render_poster


class JsonEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Path):
            return str(o)
        return super().default(o)


def create_app(poster_path: str, edit_mode: bool = True) -> Flask:
    poster_path = Path(poster_path).resolve()
    poster_dir = poster_path.parent

    app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"))

    # Track file changes for SSE
    last_change = {"time": time.time()}

    class ChangeHandler(FileSystemEventHandler):
        def on_modified(self, event):
            if not event.is_directory:
                last_change["time"] = time.time()

    observer = Observer()
    observer.schedule(ChangeHandler(), str(poster_dir), recursive=True)
    observer.daemon = True
    observer.start()

    @app.route("/")
    def index():
        poster = parse_file(poster_path)
        # Allow template override via query param (changes colors/fonts but keeps layout)
        template_override = request.args.get("template")
        if template_override:
            poster.frontmatter.setdefault("poster", {})["template"] = template_override
            poster.frontmatter["poster"].pop("colors", None)
            poster.frontmatter["poster"].pop("fonts", None)
        html = render_poster(poster, edit_mode=edit_mode, base_url="")
        return html

    @app.route("/static/<path:filename>")
    def serve_static(filename):
        static_dir = Path(__file__).parent / "static"
        return send_from_directory(str(static_dir), filename)

    @app.route("/images/<path:filename>")
    def serve_images(filename):
        images_dir = poster_dir / "images"
        if images_dir.exists():
            return send_from_directory(str(images_dir), filename)
        return send_from_directory(str(poster_dir), filename)

    @app.route("/<path:filename>")
    def serve_file(filename):
        return send_from_directory(str(poster_dir), filename)

    @app.route("/events")
    def events():
        """SSE endpoint for live reload."""
        def stream():
            last_sent = time.time()
            while True:
                time.sleep(0.5)
                if last_change["time"] > last_sent:
                    last_sent = last_change["time"]
                    yield f"data: reload\n\n"

        return Response(stream(), mimetype="text/event-stream")

    @app.route("/api/export-pdf", methods=["POST"])
    def export_pdf():
        """Export poster as PDF using Playwright for accurate rendering."""
        from .formats import get_size
        poster = parse_file(poster_path)
        config = poster.poster_config
        size = get_size(config.get("size", "A0-landscape"))

        # Convert to inches for Playwright
        w, h = size["width"], size["height"]
        unit = size["unit"]
        if unit == "mm":
            w_in, h_in = w / 25.4, h / 25.4
        elif unit == "cm":
            w_in, h_in = w / 2.54, h / 2.54
        elif unit == "px":
            w_in, h_in = w / 96, h / 96
        else:
            w_in, h_in = w, h

        # Render poster HTML (no edit mode)
        html = render_poster(poster, edit_mode=False, base_url="")

        import tempfile
        from playwright.sync_api import sync_playwright

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
            # Rewrite relative URLs to absolute file paths
            abs_html = html.replace('src="/images/', f'src="file://{poster_dir}/images/')
            abs_html = abs_html.replace('src="images/', f'src="file://{poster_dir}/images/')
            abs_html = abs_html.replace("src='/images/", f"src='file://{poster_dir}/images/")
            abs_html = abs_html.replace("src='images/", f"src='file://{poster_dir}/images/")
            f.write(abs_html)
            html_path = f.name

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                # Set viewport to poster dimensions so content doesn't reflow
                px_w = int(w_in * 96)
                px_h = int(h_in * 96)
                page = browser.new_page(viewport={"width": px_w, "height": px_h})
                page.goto(f"file://{html_path}", wait_until="networkidle")
                # Wait for fonts, mermaid, KaTeX to render
                page.wait_for_timeout(3000)
                pdf_bytes = page.pdf(
                    width=f"{w_in}in",
                    height=f"{h_in}in",
                    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                    print_background=True,
                )
                browser.close()
        finally:
            import os
            os.unlink(html_path)

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=poster.pdf"},
        )

    @app.route("/api/save", methods=["POST"])
    def save():
        """Save changes back to the markdown file."""
        data = request.get_json()
        poster = parse_file(poster_path)

        action = data.get("action")

        def find_cell(cell_id):
            for c in poster.cells:
                if c.id == cell_id:
                    return c
            return None

        if action == "reorder":
            # Reorder cells: data contains cell IDs per column
            new_columns = data.get("columns_order", [])
            cell_map = {c.id: c for c in poster.cells if not c.id.startswith("__sep__")}
            new_cells = []
            for col_idx, col_ids in enumerate(new_columns):
                for cid in col_ids:
                    if cid in cell_map:
                        cell = cell_map[cid]
                        cell.column = col_idx
                        new_cells.append(cell)
            # Add any cells not in the reorder (shouldn't happen but safety)
            seen = {c.id for c in new_cells}
            for c in poster.cells:
                if c.id not in seen and not c.id.startswith("__sep__"):
                    new_cells.append(c)
            poster.cells = new_cells

        elif action == "columns":
            # Update column widths
            columns = data.get("columns", [])
            if columns:
                poster.frontmatter.setdefault("poster", {})["columns"] = columns

        elif action == "resize":
            # Update cell height
            cell_id = data.get("cell_id")
            height = data.get("height", 1.0)
            cell = find_cell(cell_id)
            if cell:
                cell.height = round(height, 2)

        elif action == "split":
            # Split a cell into two subcells
            cell_id = data.get("cell_id")
            cell = find_cell(cell_id)
            if cell and not cell.split:
                from .parser import Cell
                cell.split = True
                cell.subcells = [
                    Cell(id=f"{cell.id}-sub-0", title="Left", content=cell.content),
                    Cell(id=f"{cell.id}-sub-1", title="Right", content=""),
                ]
                cell.content = ""

        elif action == "merge":
            # Merge split cell back into one
            cell_id = data.get("cell_id")
            cell = find_cell(cell_id)
            if cell and cell.split:
                combined = "\n\n".join(
                    (f"### {s.title}\n\n{s.content}" if s.title else s.content)
                    for s in cell.subcells
                )
                cell.split = False
                cell.content = combined
                cell.subcells = []

        # Serialize and save
        md = serialize_poster(poster)
        poster_path.write_text(md, encoding="utf-8")

        return jsonify({"status": "ok"})

    return app


def run_server(poster_path: str, host: str = "127.0.0.1", port: int = 8765,
               edit_mode: bool = True, open_browser: bool = True):
    """Run the development server."""
    app = create_app(poster_path, edit_mode=edit_mode)
    url = f"http://{host}:{port}"
    print(f"Postergeist server running at {url}")
    print(f"Editing: {poster_path}")
    print(f"Edit mode: {'ON' if edit_mode else 'OFF'}")
    print("Press Ctrl+C to stop")

    if open_browser:
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    app.run(host=host, port=port, debug=False, threaded=True)
