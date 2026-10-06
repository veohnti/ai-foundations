"""Replace black product-photo backgrounds with white.

74 of the 102 catalogue photos sit on black: either a garment cut out on solid
black, or a white photo padded with black bars at the sides. This turns that
background white so every tile matches the site's white cards.

Method: start from the image border and spread inward only through pixels that
are near-black AND neutral (not bluish). Navy fabric, even in shadow, keeps more
blue than red, so it stops the spread and the garment is left untouched. Black
bars are cleared to their exact column edges, including the 1-2 px JPEG seam.

Originals are copied to data/products_original/ before anything is changed, and
the script always reads from that copy, so it can be re-run safely.

Usage (from HW4/):  .venv/bin/python scripts/whiten_backgrounds.py [--out DIR] [names...]
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "data" / "products"
BACKUP_DIR = ROOT / "data" / "products_original"

DARK_MAX = 10      # every channel at or below this counts as backdrop black.
                   # Measured: backdrops are exactly 0; navy shadows start ~13.
BLUE_TINT = 12     # blue exceeding red by more than this means navy fabric, not backdrop
BORDER_DARK_SHARE = 0.5  # only process photos whose border is mostly black


def _grow(m: np.ndarray) -> np.ndarray:
    g = m.copy()
    g[1:, :] |= m[:-1, :]
    g[:-1, :] |= m[1:, :]
    g[:, 1:] |= m[:, :-1]
    g[:, :-1] |= m[:, 1:]
    return g


def _shrink(m: np.ndarray) -> np.ndarray:
    return ~_grow(~m)


def background_mask(rgb: np.ndarray) -> np.ndarray:
    """Pixels connected to the border through neutral near-black pixels.

    The spread runs on a 1-px-eroded version of the candidate area, so it can't
    squeeze through a hairline gap into a dark garment, then a final 1-px grow
    (still limited to candidate pixels) restores the true edge.
    """
    r, g, b = (rgb[..., i].astype(int) for i in range(3))
    candidate = (rgb.max(axis=2) <= DARK_MAX) & ((b - r) <= BLUE_TINT)
    core = _shrink(candidate)

    reached = np.zeros_like(core)
    reached[0, :], reached[-1, :] = candidate[0, :], candidate[-1, :]
    reached[:, 0], reached[:, -1] = candidate[:, 0], candidate[:, -1]
    reached &= core | np.pad(np.zeros((rgb.shape[0] - 2, rgb.shape[1] - 2), bool), 1, constant_values=True)

    while True:
        grown = _grow(reached) & core
        grown |= reached
        if (grown == reached).all():
            break
        reached = grown
    return _grow(reached) & candidate


GAP_BLACK_MAX = 6       # enclosed gaps are the same pure black as the backdrop
GAP_MIN_PIXELS = 40     # ignore tiny dark specks inside the print
GAP_MIN_CENTER_Y = 0.35 # arm/body gaps sit below the shoulders; hood linings sit above


def enclosed_gaps(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Backdrop showing through gaps the border fill can't reach.

    The black between an arm and the body is enclosed by the garment, so it
    isn't connected to the image border. Those gaps are pure black (like the
    backdrop), at least GAP_MIN_PIXELS in size, and centered below the
    shoulders. The last rule keeps dark hood linings, which are real fabric
    near the top of the photo, from being whitened.
    """
    r, b = rgb[..., 0].astype(int), rgb[..., 2].astype(int)
    pure = (rgb.max(axis=2) <= GAP_BLACK_MAX) & ((b - r) <= 6) & ~mask
    labels, count = ndimage.label(pure)
    if count == 0:
        return np.zeros_like(mask)
    ids = np.arange(1, count + 1)
    sizes = ndimage.sum(pure, labels, ids)
    centers = ndimage.center_of_mass(pure, labels, ids)
    keep = [i for i, size, (cy, _) in zip(ids, sizes, centers)
            if size >= GAP_MIN_PIXELS and cy >= GAP_MIN_CENTER_Y * rgb.shape[0]]
    return np.isin(labels, keep)


HALO_MAX = 45      # dark JPEG noise just outside the garment reaches about this value
HALO_REACH = 5     # but only this many px out from the true backdrop
HALO_NEUTRAL = 12  # and only near-grey pixels (navy fabric has a blue cast)


def extend_into_halo(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Add the ring of dark-grey noise that hugs the old black edge.

    The strict DARK_MAX cutoff protects navy shadows but leaves a speckled
    near-black halo along the garment outline. This takes neutral dark pixels
    (max channel <= HALO_MAX, channel spread <= HALO_NEUTRAL) that are within
    HALO_REACH px of the backdrop. It doesn't go deeper, so dark garments lose
    at most a few edge pixels, which soften_edges then blends anyway.
    """
    lo, hi = rgb.min(axis=2).astype(int), rgb.max(axis=2).astype(int)
    halo_like = (hi <= HALO_MAX) & ((hi - lo) <= HALO_NEUTRAL)
    grown = mask.copy()
    for _ in range(HALO_REACH):
        grown = grown | (_grow(grown) & halo_like)
    return grown


def clear_side_bars(rgb: np.ndarray, mask: np.ndarray) -> None:
    """For letterboxed photos, also whiten the soft JPEG seam beside each bar."""
    h, w = mask.shape
    full_cols = np.where(mask.mean(axis=0) > 0.98)[0]
    if len(full_cols) == 0:
        return
    left = [c for c in full_cols if c < w // 2]
    right = [c for c in full_cols if c >= w // 2]
    seam = 3
    if left:
        edge = max(left)
        mask[:, edge + 1 : min(w, edge + 1 + seam)] |= rgb[:, edge + 1 : edge + 1 + seam].max(axis=2) < 200
    if right:
        edge = min(right)
        mask[:, max(0, edge - seam) : edge] |= rgb[:, max(0, edge - seam) : edge].max(axis=2) < 200


def absorb_specks(mask: np.ndarray, passes: int = 3) -> np.ndarray:
    """Fold stray JPEG specks along the garment edge into the background.

    A non-background pixel with at least 5 of its 8 neighbours already in the
    background is noise sticking out of the edge, not garment, so it joins the
    background. A few passes clear speckled, jagged edges; solid garment pixels
    never have 5 background neighbours, so the garment itself is not eroded.
    """
    m = mask.copy()
    for _ in range(passes):
        p = np.pad(m, 1).astype(np.uint8)
        neighbours = sum(
            p[1 + dy : p.shape[0] - 1 + dy, 1 + dx : p.shape[1] - 1 + dx]
            for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy, dx) != (0, 0)
        )
        m = m | (neighbours >= 5)
    return m


ISLAND_MAX_PIXELS = 80  # foreground blobs this small, fully surrounded by background, are noise


def drop_islands(mask: np.ndarray) -> np.ndarray:
    """Fold small specks that float inside the background into it.

    After the background is found, everything else should be one garment.
    Tiny separate blobs (JPEG noise left along the old black edge) are
    surrounded by background on all sides; real garment parts are connected to
    the garment, so they're far larger than ISLAND_MAX_PIXELS and are kept.
    """
    labels, count = ndimage.label(~mask)
    if count <= 1:
        return mask
    sizes = ndimage.sum(~mask, labels, np.arange(1, count + 1))
    small = np.where(sizes <= ISLAND_MAX_PIXELS)[0] + 1
    return mask | np.isin(labels, small)


def soften_edges(rgb: np.ndarray, mask: np.ndarray, band: int = 3) -> np.ndarray:
    """Remove the dark fringe left where the garment was blended with black.

    An edge pixel in a cut-out photo is a mix of garment color and the black
    backdrop: pixel = alpha * garment. Its alpha is estimated as its brightness
    relative to the garment just inside (a 7x7 local max of non-edge pixels),
    and the black share is replaced with white: out = pixel + (1 - alpha) * 255.
    Pixels as bright as the garment have alpha 1 and are left unchanged.
    """
    edge = mask.copy()
    for _ in range(band):
        edge = _grow(edge)
    edge &= ~mask

    lum = rgb.astype(float) @ np.array([0.299, 0.587, 0.114])
    solid = np.where(mask | edge, 0, lum).astype(np.uint8)
    ref = np.asarray(Image.fromarray(solid).filter(ImageFilter.MaxFilter(7))).astype(float)
    ref = np.where(ref < 1, lum, ref)  # no solid garment nearby: leave pixel as is

    alpha = np.clip(lum / np.maximum(ref, 1), 0, 1)
    out = rgb.astype(float)
    out[edge] = np.clip(out[edge] + ((1 - alpha[edge]) * 255)[:, None], 0, 255)
    return out.astype(np.uint8)


FEATHER_RADIUS = 1.1  # px of blur on the background edge


def feather(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Blend the hard background edge over about a pixel so cut-outs don't stair-step.

    The background mask is blurred slightly. Where the blurred value is between
    0 and 1 (right at the edge), the pixel is mixed toward white by that amount.
    Pixels well inside the garment get 0 and are unchanged.
    """
    soft = np.asarray(
        Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(FEATHER_RADIUS))
    ).astype(float) / 255
    soft = np.maximum(soft, mask.astype(float))
    out = rgb.astype(float) * (1 - soft[..., None]) + 255 * soft[..., None]
    return out.astype(np.uint8)


SPECK_WINDOW = 9          # px square examined around each pixel
SPECK_WHITE_SHARE = 0.88  # a pixel this surrounded by white is a speck, not fabric


def clear_floating_specks(rgb: np.ndarray) -> np.ndarray:
    """Whiten small dark specks left floating in the new white background.

    Specks along the old black edge can be chained to the garment by faint
    noise, so they aren't separate islands. They're recognised instead by
    their surroundings: at least 88% of a 9x9 window is white. A garment edge
    is about half fabric, and a 2-px drawstring is ~78% white, so both stay.
    """
    white = (rgb.min(axis=2) >= 240).astype(float)
    share = ndimage.uniform_filter(white, size=SPECK_WINDOW, mode="nearest")
    specks = (white == 0) & (share >= SPECK_WHITE_SHARE)
    out = rgb.copy()
    out[specks] = 255
    return out


def border_dark_share(rgb: np.ndarray) -> float:
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    return float((border.max(axis=1) < 40).mean())


def process(src: Path, dst: Path) -> tuple[bool, float]:
    rgb = np.asarray(Image.open(src).convert("RGB")).copy()
    if border_dark_share(rgb) <= BORDER_DARK_SHARE:
        if src != dst:
            shutil.copy2(src, dst)
        return False, 0.0
    mask = background_mask(rgb)
    clear_side_bars(rgb, mask)
    mask |= enclosed_gaps(rgb, mask)
    mask = extend_into_halo(rgb, mask)
    mask = absorb_specks(mask)
    mask = drop_islands(mask)
    rgb = soften_edges(rgb, mask)
    rgb[mask] = 255
    rgb = feather(rgb, mask)
    rgb = clear_floating_specks(rgb)
    Image.fromarray(rgb).save(dst, quality=92)
    return True, float(mask.mean())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write here instead of data/products (for previews)")
    ap.add_argument("names", nargs="*", help="product image stems to process (default: all)")
    args = ap.parse_args()

    if not BACKUP_DIR.exists():
        shutil.copytree(SRC_DIR, BACKUP_DIR)
        print(f"backed up originals -> {BACKUP_DIR.relative_to(ROOT)}")

    out_dir = Path(args.out) if args.out else SRC_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    files = [BACKUP_DIR / f"{n}.jpg" for n in args.names] if args.names else sorted(BACKUP_DIR.glob("*.jpg"))

    changed = 0
    for f in files:
        did, share = process(f, out_dir / f.name)
        changed += did
        if did and args.names:
            print(f"  {f.stem}: {share:.0%} of pixels whitened")
    print(f"{changed} of {len(files)} images had their black background replaced")


if __name__ == "__main__":
    main()
