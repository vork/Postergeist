"""Extract text and figures from an academic paper PDF.

Usage:
    python -m postergeist.extract <pdf_path> <output_images_dir>

Outputs:
    <parent_of_images_dir>/extracted_text.txt  — full text by page
    <parent_of_images_dir>/figures_meta.json   — metadata for each extracted figure
    <output_images_dir>/fig1_p1.png ...         — extracted figure images
"""

import sys
import os
import json

import fitz  # PyMuPDF


def _extract_text_nougat(pdf_path: str) -> list[str] | None:
    """Extract text per page using the Nougat model (HuggingFace transformers).

    Returns a list of markdown strings (one per page) with LaTeX equations,
    or None if the required dependencies are not installed.
    Model weights (~1.3 GB) are downloaded on first use.
    """
    try:
        import torch
        from transformers import NougatProcessor, VisionEncoderDecoderModel
        from PIL import Image
    except ImportError:
        return None

    print("Loading Nougat model (first run downloads ~1.3 GB)...")
    processor = NougatProcessor.from_pretrained("facebook/nougat-small")
    model = VisionEncoderDecoderModel.from_pretrained("facebook/nougat-small")

    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    model = model.to(device)
    model.eval()

    doc = fitz.open(pdf_path)
    page_texts: list[str] = []

    for page_idx, page in enumerate(doc):
        print(f"  Nougat: page {page_idx + 1}/{len(doc)}...")
        pix = page.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        pixel_values = processor(img, return_tensors="pt").pixel_values.to(device)

        with torch.no_grad():
            outputs = model.generate(
                pixel_values,
                min_length=1,
                max_new_tokens=4096,
                bad_words_ids=[[processor.tokenizer.unk_token_id]],
            )

        text = processor.batch_decode(outputs, skip_special_tokens=True)[0]
        text = processor.post_process_generation(text, fix_markdown=True)
        page_texts.append(text)

    doc.close()
    return page_texts


def _autocrop_save(pix: "fitz.Pixmap", fpath: str, margin: int = 6, threshold: int = 250) -> tuple[int, int]:
    """Save pixmap to file, trimming near-white borders. Returns (width, height)."""
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    if img.mode == "RGBA":
        # Work with RGB for border detection
        rgb = img.convert("RGB")
    else:
        rgb = img

    w, h = rgb.size
    pixels = rgb.load()

    def row_is_blank(y: int) -> bool:
        for x in range(0, w, max(1, w // 50)):  # sample every ~50 pixels
            r, g, b = pixels[x, y]
            if r < threshold or g < threshold or b < threshold:
                return False
        return True

    def col_is_blank(x: int) -> bool:
        for y in range(0, h, max(1, h // 50)):
            r, g, b = pixels[x, y]
            if r < threshold or g < threshold or b < threshold:
                return False
        return True

    top = 0
    while top < h and row_is_blank(top):
        top += 1
    bottom = h - 1
    while bottom > top and row_is_blank(bottom):
        bottom -= 1
    left = 0
    while left < w and col_is_blank(left):
        left += 1
    right = w - 1
    while right > left and col_is_blank(right):
        right -= 1

    # Apply margin
    top = max(0, top - margin)
    bottom = min(h - 1, bottom + margin)
    left = max(0, left - margin)
    right = min(w - 1, right + margin)

    if top < bottom and left < right:
        img = img.crop((left, top, right + 1, bottom + 1))

    img.save(fpath)
    return img.size


def extract(pdf_path: str, img_dir: str, use_nougat: bool = True) -> None:
    os.makedirs(img_dir, exist_ok=True)

    nougat_pages: list[str] | None = None
    if use_nougat:
        nougat_pages = _extract_text_nougat(pdf_path)
        if nougat_pages:
            print(f"Nougat: extracted text with LaTeX from {len(nougat_pages)} pages")
        else:
            print("Nougat unavailable, falling back to PyMuPDF text extraction")

    doc = fitz.open(pdf_path)
    full_text: list[str] = []
    figures: list[dict] = []
    fig_count = 0

    for page_idx, page in enumerate(doc):
        # --- Extract text ---
        full_text.append(f"\n--- Page {page_idx + 1} ---\n")
        text_blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, type)
        nougat_page = nougat_pages[page_idx] if nougat_pages and page_idx < len(nougat_pages) else None
        if nougat_page:
            full_text.append(nougat_page)
        else:
            for b in text_blocks:
                if b[6] == 0:
                    full_text.append(b[4])

        # --- Identify large vs small text blocks ---
        large_text_rects: list[fitz.Rect] = []
        small_text_rects: list[tuple[fitz.Rect, str]] = []
        for b in text_blocks:
            if b[6] != 0:
                continue
            txt = b[4].strip()
            rect = fitz.Rect(b[:4])
            lower = txt.lower()
            is_caption = lower.startswith("fig") or lower.startswith("table")
            if len(txt) > 100 and not is_caption:
                large_text_rects.append(rect)
            elif len(txt) < 30:
                small_text_rects.append((rect, txt))

        # --- Gather non-text visual elements ---
        visual_rects: list[fitz.Rect] = []

        # Raster images (deduplicate by hash, pick smallest bbox)
        img_info = page.get_image_info(hashes=True)
        hash_map: dict[str, fitz.Rect] = {}
        for im in img_info:
            h = im.get("digest")
            r = fitz.Rect(im["bbox"])
            if r.is_empty or r.is_infinite or r.width < 20 or r.height < 20:
                continue
            if h not in hash_map or r.get_area() < hash_map[h].get_area():
                hash_map[h] = r
        for r in hash_map.values():
            visual_rects.append(r)

        # Vector drawings
        drawings = page.get_drawings()
        for d in drawings:
            r = fitz.Rect(d["rect"])
            if r.is_empty or r.is_infinite or r.width < 20 or r.height < 20:
                continue
            visual_rects.append(r)

        # Small text labels (likely part of figures), excluding captions
        for r, txt in small_text_rects:
            if txt.lower().startswith("fig") or txt.lower().startswith("table"):
                continue  # Don't merge caption starts into figure regions
            visual_rects.append(r)

        if not visual_rects:
            continue

        # --- Merge adjacent visual elements into figure regions ---
        def merge_rects(
            rects: list[fitz.Rect], gap: int = 15
        ) -> list[fitz.Rect]:
            if not rects:
                return []
            rects = sorted(rects, key=lambda r: (r.y0, r.x0))
            merged = [rects[0]]
            for r in rects[1:]:
                expanded = fitz.Rect(merged[-1])
                expanded.x0 -= gap
                expanded.y0 -= gap
                expanded.x1 += gap
                expanded.y1 += gap
                if expanded.intersects(r):
                    # Check overlap with large text blocks
                    candidate = merged[-1] | r
                    overlaps_text = any(
                        candidate.intersects(lt)
                        and (candidate & lt).get_area() > lt.get_area() * 0.3
                        for lt in large_text_rects
                    )
                    if not overlaps_text:
                        merged[-1] = candidate
                        continue
                merged.append(r)
            # Repeat once more for transitive merges
            if len(merged) < len(rects):
                return merge_rects(merged, gap)
            return merged

        fig_regions = merge_rects(visual_rects)

        # --- Second merge pass for nearby figure regions ---
        # Merge figure regions that are close to each other (within
        # a generous gap) and whose union doesn't overlap body text.
        # This catches multi-row pipeline diagrams and horizontally
        # spread figures that the first conservative pass missed.
        def merge_nearby_figures(
            regions: list[fitz.Rect], gap: int = 40
        ) -> list[fitz.Rect]:
            if len(regions) <= 1:
                return regions
            changed = True
            while changed:
                changed = False
                regions = sorted(regions, key=lambda r: (r.y0, r.x0))
                new: list[fitz.Rect] = []
                skip: set[int] = set()
                for i in range(len(regions)):
                    if i in skip:
                        continue
                    cur = fitz.Rect(regions[i])
                    for j in range(i + 1, len(regions)):
                        if j in skip:
                            continue
                        other = regions[j]
                        # Check proximity: vertical gap between regions
                        v_gap = max(0, max(other.y0 - cur.y1, cur.y0 - other.y1))
                        h_gap = max(0, max(other.x0 - cur.x1, cur.x0 - other.x1))
                        if v_gap > gap and h_gap > gap:
                            continue
                        candidate = cur | other
                        overlaps_text = any(
                            candidate.intersects(lt)
                            and (candidate & lt).get_area() > lt.get_area() * 0.3
                            for lt in large_text_rects
                        )
                        if not overlaps_text:
                            cur = candidate
                            skip.add(j)
                            changed = True
                    new.append(cur)
                regions = new
            return regions

        fig_regions = merge_nearby_figures(fig_regions)

        # --- Filter out tiny or degenerate regions ---
        pw, ph = page.rect.width, page.rect.height
        fig_regions = [
            r
            for r in fig_regions
            if r.width > pw * 0.12
            and r.height > ph * 0.05
            and r.width / max(r.height, 1) > 0.15  # reject very tall/narrow slivers
        ]

        # --- Extract each figure region ---
        for region in fig_regions:
            fig_count += 1

            # Look for caption below the figure
            caption = ""
            caption_zone = fitz.Rect(
                region.x0 - 10, region.y1, region.x1 + 10, region.y1 + 60
            )
            for b in text_blocks:
                if b[6] != 0:
                    continue
                br = fitz.Rect(b[:4])
                if caption_zone.intersects(br):
                    txt = b[4].strip()
                    if txt.lower().startswith(
                        "fig"
                    ) or txt.lower().startswith("table"):
                        caption = txt
                        break

            # Crop away caption text from the bottom of the region
            crop_region = fitz.Rect(region)
            # Collect all caption-like text blocks near or inside the bottom
            caption_blocks = []
            search_zone = fitz.Rect(
                region.x0 - 20, region.y0 + region.height * 0.6,
                region.x1 + 20, region.y1 + 30
            )
            for b in text_blocks:
                if b[6] != 0:
                    continue
                br = fitz.Rect(b[:4])
                txt = b[4].strip()
                if not search_zone.intersects(br):
                    continue
                # Caption typically starts with "Figure" or "Table"
                if txt.lower().startswith("fig") or txt.lower().startswith("table"):
                    caption_blocks.append(br)
                    # Also include continuation text blocks below this caption
                    cap_bottom = br.y1
                    for b2 in text_blocks:
                        if b2[6] != 0:
                            continue
                        br2 = fitz.Rect(b2[:4])
                        if br2.y0 >= cap_bottom - 2 and br2.y0 < cap_bottom + 15:
                            if br2.x0 >= region.x0 - 20 and br2.x1 <= region.x1 + 20:
                                caption_blocks.append(br2)
                                cap_bottom = max(cap_bottom, br2.y1)
            if caption_blocks:
                # Crop to just above the first caption block
                top_of_caption = min(cb.y0 for cb in caption_blocks)
                crop_region.y1 = min(crop_region.y1, top_of_caption - 3)

            clip = crop_region + fitz.Rect(-3, -3, 3, 3)  # small padding
            clip &= page.rect  # clamp to page

            # Guard against degenerate clips (e.g. caption cropping pushed y1 above y0)
            if clip.is_empty or clip.width < 5 or clip.height < 5:
                fig_count -= 1
                continue

            pix = page.get_pixmap(dpi=300, clip=clip)

            # PyMuPDF can produce zero-dimension pixmaps for certain clip regions
            if pix.width < 1 or pix.height < 1:
                fig_count -= 1
                continue

            fname = f"fig{fig_count}_p{page_idx + 1}.png"
            fpath = os.path.join(img_dir, fname)

            # Auto-crop whitespace borders and save
            final_w, final_h = _autocrop_save(pix, fpath, margin=6)

            aspect = round(final_w / max(final_h, 1), 2)
            figures.append(
                {
                    "file": fname,
                    "page": page_idx + 1,
                    "caption": caption[:200],
                    "aspect": aspect,
                    "width": final_w,
                    "height": final_h,
                }
            )

    page_count = len(doc)
    doc.close()

    # Write outputs
    out_dir = os.path.join(img_dir, "..")
    text_path = os.path.join(out_dir, "extracted_text.txt")
    with open(text_path, "w") as f:
        f.write("\n".join(full_text))

    meta_path = os.path.join(out_dir, "figures_meta.json")
    with open(meta_path, "w") as f:
        json.dump(figures, f, indent=2)

    print(f"Extracted {fig_count} figure regions from {page_count} pages")
    for fig in figures:
        print(
            f"  {fig['file']}: aspect={fig['aspect']}, caption={fig['caption'][:80]}"
        )


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if len(args) < 2:
        print("Usage: python extract.py <pdf_path> <images_dir> [--no-nougat]")
        sys.exit(1)
    extract(args[0], args[1], use_nougat="--no-nougat" not in flags)
