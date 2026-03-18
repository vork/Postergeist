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


def extract(pdf_path: str, img_dir: str) -> None:
    os.makedirs(img_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    full_text: list[str] = []
    figures: list[dict] = []
    fig_count = 0

    for page_idx, page in enumerate(doc):
        # --- Extract text ---
        full_text.append(f"\n--- Page {page_idx + 1} ---\n")
        text_blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, type)
        for b in text_blocks:
            if b[6] == 0:  # text block
                full_text.append(b[4])

        # --- Identify large vs small text blocks ---
        large_text_rects: list[fitz.Rect] = []
        small_text_rects: list[tuple[fitz.Rect, str]] = []
        for b in text_blocks:
            if b[6] != 0:
                continue
            txt = b[4].strip()
            rect = fitz.Rect(b[:4])
            if len(txt) > 100:
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

        # --- Filter out tiny regions ---
        pw, ph = page.rect.width, page.rect.height
        fig_regions = [
            r
            for r in fig_regions
            if r.width > pw * 0.08 and r.height > ph * 0.05
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
            pix = page.get_pixmap(dpi=300, clip=clip)

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
    if len(sys.argv) < 3:
        print(f"Usage: python -m postergeist.extract <pdf_path> <images_dir>")
        sys.exit(1)
    extract(sys.argv[1], sys.argv[2])
