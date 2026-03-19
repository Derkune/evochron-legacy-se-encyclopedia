import argparse
import html
import json
import os
import re
from dataclasses import dataclass
from typing import Iterable


KNOWN_FOLDERS = (
    "commodities",
    "equipment",
    "weapons",
    "engines",
    "modules",
    "plating",
    "resistors",
    "wings",
)


STARFIELD_CSS = r"""
:root{
  --bg0:#050712;
  --bg1:#070a18;
  --panel: rgba(10, 16, 38, 0.72);
  --panel2: rgba(14, 23, 55, 0.6);
  --text: #d8f0ff;
  --muted: rgba(216, 240, 255, 0.72);
  --accent: #76d2ff;
  --accent2:#b7f7ff;
  --border: rgba(118, 210, 255, 0.35);
  --shadow: rgba(118, 210, 255, 0.18);
  --card-radius: 14px;
}

body{
  margin:0;
  color: var(--text);
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji","Segoe UI Emoji";
  background: radial-gradient(1200px 900px at 20% -10%, rgba(118, 210, 255, 0.22), transparent 60%),
              radial-gradient(900px 700px at 90% 10%, rgba(183, 247, 255, 0.16), transparent 55%),
              linear-gradient(180deg, var(--bg0), var(--bg1));
  overflow-x:hidden;
}

/* Starfield background (pure CSS) */
body::before{
  content:"";
  position:fixed;
  inset:0;
  pointer-events:none;
  background:
    radial-gradient(circle at 10% 20%, rgba(255,255,255,0.75) 1px, transparent 1.5px),
    radial-gradient(circle at 20% 80%, rgba(255,255,255,0.55) 1px, transparent 1.5px),
    radial-gradient(circle at 35% 30%, rgba(255,255,255,0.5) 1px, transparent 1.5px),
    radial-gradient(circle at 55% 65%, rgba(255,255,255,0.6) 1px, transparent 1.5px),
    radial-gradient(circle at 75% 25%, rgba(255,255,255,0.45) 1px, transparent 1.5px),
    radial-gradient(circle at 88% 78%, rgba(255,255,255,0.55) 1px, transparent 1.5px);
  opacity: 0.25;
  filter: drop-shadow(0 0 6px rgba(118,210,255,0.12));
}

body::after{
  content:"";
  position:fixed;
  inset:-30%;
  pointer-events:none;
  background:
    radial-gradient(circle at 25% 15%, rgba(118,210,255,0.14) 0, transparent 40%),
    radial-gradient(circle at 80% 35%, rgba(183,247,255,0.11) 0, transparent 45%);
  transform: rotate(10deg);
}

.wrap{
  position:relative;
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 18px 60px;
}

.topbar{
  display:flex;
  gap: 14px;
  align-items:center;
  justify-content:space-between;
  margin-bottom: 18px;
}

.brand{
  display:flex;
  gap: 12px;
  align-items:center;
}

.logo{
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: radial-gradient(circle at 30% 30%, rgba(255,255,255,0.25), transparent 55%),
              linear-gradient(135deg, rgba(118,210,255,0.35), rgba(183,247,255,0.12));
  border: 1px solid var(--border);
  box-shadow: 0 10px 35px var(--shadow);
}

.brand h1{
  margin: 0;
  font-size: 18px;
  letter-spacing: 0.04em;
}

.brand p{
  margin: 2px 0 0;
  color: var(--muted);
  font-size: 12.5px;
}

.nav a{
  color: var(--accent2);
  text-decoration:none;
  border: 1px solid rgba(118, 210, 255, 0.28);
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(12, 18, 44, 0.45);
  box-shadow: 0 12px 30px rgba(118,210,255,0.09);
}
.nav a:hover{
  border-color: rgba(118, 210, 255, 0.55);
}

.page-title{
  margin: 18px 0 8px;
  font-size: 20px;
  letter-spacing: 0.02em;
}

.subtitle{
  margin: 0 0 18px;
  color: var(--muted);
  font-size: 13.5px;
}

.list{
  display:flex;
  flex-direction:column;
  gap: 14px;
}

.item-card{
  display:flex;
  gap: 14px;
  align-items:flex-start;
  padding: 14px;
  border-radius: var(--card-radius);
  background: linear-gradient(180deg, var(--panel), rgba(10,16,38,0.52));
  border: 1px solid rgba(118, 210, 255, 0.26);
  box-shadow: 0 18px 55px rgba(118,210,255,0.08);
}

.icon{
  width: 76px;
  height: 76px;
  object-fit: contain;
  border-radius: 14px;
  background: rgba(6, 10, 28, 0.45);
  border: 1px solid rgba(118, 210, 255, 0.22);
}

.item-text{
  flex: 1;
  white-space: pre-wrap;
  line-height: 1.25;
  font-size: 13.2px;
  color: rgba(216, 240, 255, 0.92);
}

.missing{
  color: rgba(255, 190, 190, 0.95);
  font-style: italic;
}

.footer{
  margin-top: 28px;
  color: rgba(216,240,255,0.55);
  font-size: 12px;
}
"""


def _normalize_rel(path: str) -> str:
    # jsonl uses backslashes on Windows; html prefers forward slashes.
    return path.replace("\\", "/").lstrip("./")


def _escape_text(text: str) -> str:
    return html.escape(text, quote=False)


def _clean_ocr_text(text: str) -> str:
    """
    Reduce common OCR / LLM artifacts for display:
    - remove model preface lines (if any)
    - normalize whitespace (collapse extra spaces, trim edges)
    - remove obvious repeated words/phrases on a line
    - remove consecutive duplicate lines and extra blank lines
    """
    if not text:
        return ""

    raw = text.replace("\r\n", "\n").replace("\r", "\n")

    # Many OCR outputs start with an item index that is redundant with the icon.
    # Examples: "1\nFood - Compressed Food..." or "10 Mach - Machinery Parts..."
    raw = re.sub(r"^\s*\d+\s*(?:\n\s*)?", "", raw, count=1)
    lines = raw.split("\n")

    # Drop lines that look like model wrapper text.
    drop_line_re_list = [
        re.compile(r"^\s*```+\s*$"),
        re.compile(
            r"^\s*(here\s+(is|are)|sure|certainly|as\s+an\s+ai|note\s*:|disclaimer|explanation)\b.*$",
            re.IGNORECASE,
        ),
    ]

    kept: list[str] = []
    for line in lines:
        if line.strip() == "":
            kept.append("")
            continue
        if any(rx.search(line) for rx in drop_line_re_list):
            continue
        kept.append(line)

    # Normalize per-line spacing and remove repeated words/phrases.
    normalized: list[str] = []
    multi_word_repeated = re.compile(
        r"\b([A-Za-z0-9_-]+)\s+([A-Za-z0-9_-]+)\s+\1\s+\2\b",
        re.IGNORECASE,
    )
    single_word_repeated = re.compile(
        r"\b([A-Za-z][A-Za-z0-9_-]{1,})\s+\1\b", re.IGNORECASE
    )

    for line in kept:
        if line == "":
            normalized.append("")
            continue

        line = line.replace("\t", " ")
        # Collapse whitespace and remove indentation artifacts.
        line = re.sub(r" {2,}", " ", line).strip()
        # Remove repeated 2-word phrases: "Shield Pack Shield Pack" -> "Shield Pack"
        line = multi_word_repeated.sub(r"\1 \2", line)
        # Remove repeated single word: "Torpedo Torpedo" -> "Torpedo"
        line = single_word_repeated.sub(r"\1", line)

        normalized.append(line)

    # Remove consecutive duplicate lines; collapse multiple blank lines to one.
    dedup: list[str] = []
    prev_nonempty: str | None = None
    last_blank = False
    for line in normalized:
        if line == "":
            if last_blank:
                continue
            dedup.append("")
            last_blank = True
            prev_nonempty = None
            continue

        if prev_nonempty is not None and line == prev_nonempty:
            continue

        dedup.append(line)
        prev_nonempty = line
        last_blank = False

    # Reflow line breaks that are clearly "wrapped text" rather than real paragraph/section breaks.
    # Heuristic: if the previous non-empty line doesn't end with sentence punctuation, and the next line
    # starts with a lowercase letter, join them with a space.
    reflowed: list[str] = []
    for line in dedup:
        if line == "":
            if reflowed and reflowed[-1] != "":
                reflowed.append("")
            continue

        if reflowed and reflowed[-1] != "":
            prev = reflowed[-1]
            prev_stripped = prev.rstrip()
            next_stripped = line.lstrip()

            prev_ends_sentence = bool(re.search(r"[.!?;:]\s*$", prev_stripped))
            next_starts_lower = bool(re.match(r"^[a-z]", next_stripped))

            # Keep the newline if the previous line looks like a header/title.
            # Specifically look for " - " with spaces, not hyphens inside words (e.g. "Anti-matter").
            prev_is_header_like = bool(re.search(r"\s-\s", prev_stripped)) or bool(
                re.match(r"^\d+\s*$", prev_stripped)
            )

            if (
                (not prev_ends_sentence)
                and next_starts_lower
                and (not prev_is_header_like)
            ):
                reflowed[-1] = re.sub(
                    r"\s+", " ", prev_stripped + " " + next_stripped
                ).strip()
                continue

        reflowed.append(line)

    return "\n".join(reflowed).strip()


@dataclass(frozen=True)
class ItemRow:
    icon_src: str
    text: str
    icon_ok: bool
    key: str  # used for stable alt/title
    order_idx: int
    seq: int  # stable ordering among duplicates


def _parse_jsonl_items(jsonl_path: str) -> Iterable[dict]:
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _folder_from_path(rel_path: str) -> str | None:
    parts = _normalize_rel(rel_path).split("/")
    for p in parts:
        if p in KNOWN_FOLDERS:
            return p
    return None


def _item_to_icon_filename(item_filename: str) -> str | None:
    # Example: commodities_item_10.jpg -> commodities_item_icon_10.jpg
    if "_item_icon_" in item_filename:
        return None
    if "_item_" not in item_filename:
        return None
    return item_filename.replace("_item_", "_item_icon_", 1)


def _parse_item_index(filename: str) -> int:
    # Expected: commodities_item_1.jpg, equipment_item_12.jpg, weapons_item_3.jpg, etc.
    # Extract the first integer after "_item_".
    m = re.search(r"_item_(\d+)\.jpg$", filename)
    if not m:
        # Fallback: try parsing any digits in the same region.
        m = re.search(r"_item_(\d+)", filename)
    if not m:
        return 10**12
    return int(m.group(1))


def _selected_match_key(filename: str) -> str | None:
    # Example: selected_cropped_20260223200545_1_part_1.png -> 20260223200545_1
    m = re.match(r"^selected_cropped_(.+)_part_\d+\.png$", filename)
    return m.group(1) if m else None


def _description_match_key(filename: str) -> str | None:
    # Example: description_20260223200545_1.png -> 20260223200545_1
    m = re.match(r"^description_(.+)\.png$", filename)
    return m.group(1) if m else None


def _parse_selected_part_index(filename: str) -> int:
    # Example: selected_cropped_..._part_5.png -> 5
    m = re.search(r"_part_(\d+)\.png$", filename)
    if not m:
        return 10**12
    return int(m.group(1))


def build_rows(repo_root: str, jsonl_path: str, folder: str) -> list[ItemRow]:
    rows: list[ItemRow] = []
    seq = 0
    records = list(_parse_jsonl_items(jsonl_path))
    for rec in records:
        rel_path = rec.get("path")
        text = rec.get("text") or ""
        if not isinstance(rel_path, str) or not isinstance(text, str):
            continue
        f = _folder_from_path(rel_path)
        if f != folder:
            continue

        item_rel_norm = _normalize_rel(rel_path)
        item_filename = os.path.basename(item_rel_norm)
        icon_filename = _item_to_icon_filename(item_filename)
        if not icon_filename:
            continue

        icon_rel = f"{folder}/{icon_filename}"
        icon_fs = os.path.join(repo_root, icon_rel)
        icon_ok = os.path.exists(icon_fs)
        key = f"{folder}:{icon_filename}"
        order_idx = _parse_item_index(item_filename)
        rows.append(
            ItemRow(
                icon_src=icon_rel,
                text=_clean_ocr_text(text),
                icon_ok=icon_ok,
                key=key,
                order_idx=order_idx,
                seq=seq,
            )
        )
        seq += 1

    # New extraction format:
    # - selected_cropped_*.png files are icons with labels.
    # - description_*.png files are matching descriptions.
    desc_text_by_key: dict[str, str] = {}
    for rec in records:
        rel_path = rec.get("path")
        text = rec.get("text") or ""
        if not isinstance(rel_path, str) or not isinstance(text, str):
            continue
        if _folder_from_path(rel_path) != folder:
            continue
        filename = os.path.basename(_normalize_rel(rel_path))
        desc_key = _description_match_key(filename)
        if not desc_key:
            continue
        desc_text_by_key[desc_key] = _clean_ocr_text(text)

    for rec in records:
        rel_path = rec.get("path")
        text = rec.get("text") or ""
        if not isinstance(rel_path, str) or not isinstance(text, str):
            continue
        if _folder_from_path(rel_path) != folder:
            continue
        icon_rel = _normalize_rel(rel_path)
        filename = os.path.basename(icon_rel)
        match_key = _selected_match_key(filename)
        if not match_key:
            continue
        icon_fs = os.path.join(repo_root, icon_rel)
        icon_ok = os.path.exists(icon_fs)
        desc_text = desc_text_by_key.get(match_key, "")
        clean_label = _clean_ocr_text(text)
        body_text = desc_text if desc_text else clean_label
        key = f"{folder}:{filename}"
        rows.append(
            ItemRow(
                icon_src=icon_rel,
                text=body_text,
                icon_ok=icon_ok,
                key=key,
                order_idx=_parse_selected_part_index(filename),
                seq=seq,
            )
        )
        seq += 1

    # Sort by numeric item index (1, 2, 3, ...), but keep duplicates stable.
    rows.sort(key=lambda r: (r.order_idx, r.seq))
    return rows


def render_page(folder: str, rows: list[ItemRow], out_path: str) -> None:
    title = folder.title()
    nav_links = "".join(
        [
            f'<a href="index.html">Index</a>',
        ]
    )

    items_html = []
    for row in rows:
        icon_img = (
            f'<img class="icon" src="{_escape_text(row.icon_src)}" alt="{_escape_text(row.key)}" loading="lazy"/>'
            if row.icon_ok
            else f'<div class="missing">Missing icon for {html.escape(row.key)}</div>'
        )
        items_html.append(
            f"""
<div class="item-card" data-key="{_escape_text(row.key)}">
  {icon_img}
  <div class="item-text">{_escape_text(row.text)}</div>
</div>
""".strip(
                "\n"
            )
        )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(
            f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)} - Evochron Encyclopedia OCR</title>
  <style>{STARFIELD_CSS}</style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div class="brand">
        <div class="logo" aria-hidden="true"></div>
        <div>
          <h1>Evochron Encyclopedia</h1>
        </div>
      </div>
      <div class="nav">
        {nav_links}
      </div>
    </div>

    <div class="page-title">{html.escape(title)} Items</div>

    <div class="list">
      {''.join(items_html)}
    </div>

  </div>
</body>
</html>
"""
        )


def render_index(out_path: str, pages: dict[str, str]) -> None:
    links_html = []
    for folder, href in pages.items():
        links_html.append(
            f'<a href="{html.escape(href)}">{html.escape(folder.title())}</a>'
        )
    links_html_str = "\n    ".join(links_html)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(
            f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Evochron Encyclopedia OCR - Index</title>
  <style>{STARFIELD_CSS}</style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div class="brand">
        <div class="logo" aria-hidden="true"></div>
        <div>
          <h1>Evochron Encyclopedia</h1>
        </div>
      </div>
      <div class="nav">
        {''.join(['<a href="index.html">Index</a>'])}
      </div>
    </div>

    <div class="page-title">Choose a Category</div>

    <div class="list">
      <div class="item-card" style="align-items:center;">
        <div style="display:flex; flex-wrap:wrap; gap: 12px;">
          {links_html_str}
        </div>
      </div>
    </div>

  </div>
</body>
</html>
"""
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="ocr_results.jsonl")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument(
        "--folders",
        default=",".join(KNOWN_FOLDERS),
        help="Comma-separated folder names to generate pages for.",
    )
    parser.add_argument(
        "--no-index",
        action="store_true",
        help="Generate category pages only and skip index.html rendering.",
    )
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.abspath(__file__))
    jsonl_path = os.path.join(repo_root, args.input)
    if not os.path.exists(jsonl_path):
        raise SystemExit(f"Missing input JSONL: {jsonl_path}")

    out_dir = os.path.join(repo_root, args.output_dir)
    os.makedirs(out_dir, exist_ok=True)

    requested_folders = [f.strip() for f in args.folders.split(",") if f.strip()]
    pages = {}
    for folder in requested_folders:
        rows = build_rows(repo_root=repo_root, jsonl_path=jsonl_path, folder=folder)
        out_path = os.path.join(out_dir, f"{folder}.html")
        render_page(folder=folder, rows=rows, out_path=out_path)
        pages[folder] = f"{folder}.html"

    if not args.no_index:
        render_index(out_path=os.path.join(out_dir, "index.html"), pages=pages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
