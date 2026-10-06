"""Build the offline copy of the website for sharing (e.g. with TAs).

Produces HW4/output/website/:
    index.html   the whole site in one file (JS, CSS, fonts, banner photos inlined)
    images/      the 102 product photos, referenced relatively from index.html

Open output/website/index.html directly (double-click). No server needed.
Browsing, product pages, compare, and the carousel work. The AI chat and
accounts need the live backend, so they show a note instead.

Steps: snapshot the catalogue (with per-size stock) from the database into
frontend/src/static/catalogue.json, run the static Vite build, copy images.

Usage (from HW4/):  .venv/bin/python scripts/export_static_site.py
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "campus_customs.db"
IMAGES = ROOT / "data" / "products"
FRONTEND = ROOT / "frontend"
SNAPSHOT = FRONTEND / "src" / "static" / "catalogue.json"
OUT = ROOT / "output" / "website"
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]


def snapshot_catalogue() -> int:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    products = []
    for row in conn.execute("SELECT * FROM catalogue ORDER BY name"):
        stock = {r["size"]: r["quantity"] for r in conn.execute(
            "SELECT size, quantity FROM inventory WHERE product_id = ?", (row["product_id"],))}
        sizes = [{"size": s, "quantity": stock[s], "in_stock": stock[s] > 0}
                 for s in SIZE_ORDER if s in stock]
        products.append({
            "product_id": row["product_id"],
            "name": row["name"],
            "garment_type": row["garment_type"],
            "description": row["description"],
            "colors": json.loads(row["colors"]),
            "search_tags": json.loads(row["search_tags"]),
            "price": row["price"],
            # Relative to index.html, so it works when opened as a file.
            "image_url": "images/" + Path(row["image_file_path"]).name,
            "sizes": sizes,
            "in_stock": any(s["in_stock"] for s in sizes),
        })
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(products, indent=1))
    return len(products)


def main() -> None:
    n = snapshot_catalogue()
    print(f"catalogue snapshot: {n} products -> {SNAPSHOT.relative_to(ROOT)}")
    subprocess.run(["npm", "run", "build:static"], cwd=FRONTEND, check=True)
    shutil.copytree(IMAGES, OUT / "images", dirs_exist_ok=True)
    print(f"copied {len(list(IMAGES.glob('*.jpg')))} product images -> {(OUT / 'images').relative_to(ROOT)}")
    print(f"done: open {(OUT / 'index.html').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
