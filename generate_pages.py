import argparse
import html
import json
import os
import re
from dataclasses import dataclass
from typing import Iterable


KNOWN_FOLDERS = ("commodities", "equipment", "weapons")


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


def build_rows(repo_root: str, jsonl_path: str, folder: str) -> list[ItemRow]:
    rows: list[ItemRow] = []
    seq = 0
    for rec in _parse_jsonl_items(jsonl_path):
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
                text=text,
                icon_ok=icon_ok,
                key=key,
                order_idx=order_idx,
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
    <div class="subtitle">{len(rows)} OCR entries (duplicates kept).</div>

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
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.abspath(__file__))
    jsonl_path = os.path.join(repo_root, args.input)
    if not os.path.exists(jsonl_path):
        raise SystemExit(f"Missing input JSONL: {jsonl_path}")

    out_dir = os.path.join(repo_root, args.output_dir)
    os.makedirs(out_dir, exist_ok=True)

    pages = {}
    for folder in KNOWN_FOLDERS:
        rows = build_rows(repo_root=repo_root, jsonl_path=jsonl_path, folder=folder)
        out_path = os.path.join(out_dir, f"{folder}.html")
        render_page(folder=folder, rows=rows, out_path=out_path)
        pages[folder] = f"{folder}.html"

    render_index(out_path=os.path.join(out_dir, "index.html"), pages=pages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
