from pathlib import Path
from typing import Iterator
from svgpathtools import parse_path, Line
from handwriter.engine.layout_engine import LayoutResult, PageLayout
from handwriter.models.hwdoc import GCodeParams
from functools import lru_cache

def _subdivide(seg, t0: float, t1: float, tol: float, depth: int) -> Iterator[tuple[float, float]]:
    """Recursively subdivide a Bezier segment into line approximations using
    chordal deviation test. Stops when midpoint deviation from the chord
    is within `tol`, or max depth is reached."""
    if depth > 12: # max recursion; limits to 2^12=4096 pts per segment
        p = seg.point(t1)
        yield (p.real, p.imag)
        return
    tm = (t0 + t1) / 2
    p0, pm, p1 = seg.point(t0), seg.point(tm), seg.point(t1)
    dx, dy = p1.real - p0.real, p1.imag - p0.imag
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-10: # near-zero length segment, skip subdivision
        yield (p1.real, p1.imag)
        return
    dist = abs(dy * (pm.real - p0.real) - dx * (pm.imag - p0.imag)) / length
    if dist <= tol:
        yield (p1.real, p1.imag)
    else:
        yield from _subdivide(seg, t0, tm, tol, depth + 1)
        yield from _subdivide(seg, tm, t1, tol, depth + 1)

def _flatten_segment(seg) -> Iterator[tuple[float, float]]:
    if isinstance(seg, Line):
        yield (seg.end.real, seg.end.imag)
    else:
        yield from _subdivide(seg, 0.0, 1.0, 0.1, 0) # 0.1mm chordal tolerance for curve smoothing

@lru_cache(maxsize=4096)
def _get_base_flattened_path(d_string: str) -> list[list[tuple[float, float]]]:
    try:
        svg_path = parse_path(d_string)
    except Exception as e:
        print(f"[gcode_exporter] Failed to parse SVG path: {e}")
        return []

    subpaths: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    prev_end = None

    for seg in svg_path:
        start = seg.start
        if prev_end is None or abs(start - prev_end) > 1e-6: # > 1e-6 gap is considered a new subpath
            if len(current) >= 2:
                subpaths.append(current)
            current = [(start.real, start.imag)]

        current.extend(_flatten_segment(seg))

        prev_end = seg.end

    if len(current) >= 2:
        subpaths.append(current)

    return subpaths

def _flatten_cubic_bezier(
    x0: float, y0: float,
    cx1: float, cy1: float,
    cx2: float, cy2: float,
    x1: float, y1: float,
    tol: float = 0.1,
) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = [(x0, y0)]

    def _subdivide(ax, ay, bx, by, cx, cy, dx, dy, depth: int) -> None:
        if depth > 12:
            pts.append((dx, dy))
            return
        mx01x, mx01y = (ax + bx) * 0.5, (ay + by) * 0.5
        mx12x, mx12y = (bx + cx) * 0.5, (by + cy) * 0.5
        mx23x, mx23y = (cx + dx) * 0.5, (cy + dy) * 0.5
        mx012x, mx012y = (mx01x + mx12x) * 0.5, (mx01y + mx12y) * 0.5
        mx123x, mx123y = (mx12x + mx23x) * 0.5, (mx12y + mx23y) * 0.5
        mid_x, mid_y = (mx012x + mx123x) * 0.5, (mx012y + mx123y) * 0.5
        # Chord midpoint deviation test
        chord_mx = (ax + dx) * 0.5
        chord_my = (ay + dy) * 0.5
        dev = abs(mid_x - chord_mx) + abs(mid_y - chord_my)
        if dev <= tol:
            pts.append((dx, dy))
        else:
            _subdivide(ax, ay, mx01x, mx01y, mx012x, mx012y, mid_x, mid_y, depth + 1)
            _subdivide(mid_x, mid_y, mx123x, mx123y, mx23x, mx23y, dx, dy, depth + 1)

    _subdivide(x0, y0, cx1, cy1, cx2, cy2, x1, y1, 0)
    return pts

def _flatten_glyph_path(d_string: str, tx: float, ty: float, scale: float) -> list[list[tuple[float, float]]]:
    base_subpaths = _get_base_flattened_path(d_string)
    result = []
    for sp in base_subpaths:
        result.append([(x * scale + tx, y * scale + ty) for x, y in sp])
    return result

def _merge_chains(subpaths: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """Merge subpaths whose endpoints are close enough into longer chains.
    Uses a spatial grid to find merge candidates in O(n) average time."""
    if not subpaths:
        return []

    n = len(subpaths)
    merge_dist_sq = 0.25 # (0.5mm)^2 max squared distance to merge endpoints
    cell = merge_dist_sq ** 0.5

    grid: dict[tuple[int, int], list[int]] = {}
    for i, sp in enumerate(subpaths):
        key = (int(sp[0][0] // cell), int(sp[0][1] // cell))
        grid.setdefault(key, []).append(i)

    next_of: list[int | None] = [None] * n
    prev_of: list[int | None] = [None] * n

    for i, sp in enumerate(subpaths):
        ex, ey = sp[-1]
        gx = int(ex // cell)
        gy = int(ey // cell)
        best_j: int | None = None
        best_d = merge_dist_sq

        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((gx + dx, gy + dy), ()):
                    if j == i:
                        continue
                    sx, sy = subpaths[j][0]
                    d = (ex - sx) ** 2 + (ey - sy) ** 2
                    if d < best_d:
                        best_d = d
                        best_j = j

        if best_j is not None and prev_of[best_j] is None:
            next_of[i] = best_j
            prev_of[best_j] = i

    used = [False] * n
    chains: list[list[tuple[float, float]]] = []
    for i in range(n):
        if used[i] or prev_of[i] is not None:
            continue
        chain = list(subpaths[i])
        used[i] = True
        j = next_of[i]
        while j is not None and not used[j]:
            chain.extend(subpaths[j][1:])
            used[j] = True
            j = next_of[j]
        chains.append(chain)

    for i in range(n):
        if not used[i]:
            chains.append(subpaths[i])

    return chains

def _optimize_order(subpaths: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """Reorder subpaths using nearest-neighbor heuristic with spatial grid
    acceleration. May reverse individual paths when the end is closer to
    the current position, reducing total travel distance."""
    if not subpaths:
        return []

    n = len(subpaths)

    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    for sp in subpaths:
        for px, py in (sp[0], sp[-1]):
            if px < min_x: min_x = px
            if px > max_x: max_x = px
            if py < min_y: min_y = py
            if py > max_y: max_y = py

    span = max(max_x - min_x, max_y - min_y, 1.0)
    cell = max(span / (n ** 0.5), 0.1)

    def _key(x: float, y: float) -> tuple[int, int]:
        return (int(x // cell), int(y // cell))

    grid: dict[tuple[int, int], set[int]] = {}

    def _grid_add(idx: int) -> None:
        for pt in (subpaths[idx][0], subpaths[idx][-1]):
            k = _key(*pt)
            if k in grid:
                grid[k].add(idx)
            else:
                grid[k] = {idx}

    def _grid_remove(idx: int) -> None:
        for pt in (subpaths[idx][0], subpaths[idx][-1]):
            k = _key(*pt)
            s = grid.get(k)
            if s is not None:
                s.discard(idx)
                if not s:
                    del grid[k]

    for i in range(n):
        _grid_add(i)

    remaining = set(range(n))
    ordered: list[list[tuple[float, float]]] = []
    cur_x, cur_y = 0.0, 0.0
    max_ring = int(span / cell) + 2

    while remaining:
        cc = _key(cur_x, cur_y)
        best_i: int | None = None
        best_dist = float('inf')
        best_rev = False

        for r in range(max_ring + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if r > 0 and abs(dx) < r and abs(dy) < r:
                        continue
                    bucket = grid.get((cc[0] + dx, cc[1] + dy))
                    if not bucket:
                        continue
                    for idx in bucket:
                        if idx not in remaining:
                            continue
                        sp = subpaths[idx]
                        ds = (sp[0][0] - cur_x) ** 2 + (sp[0][1] - cur_y) ** 2
                        de = (sp[-1][0] - cur_x) ** 2 + (sp[-1][1] - cur_y) ** 2
                        if ds < best_dist:
                            best_dist, best_i, best_rev = ds, idx, False
                        if de < best_dist:
                            best_dist, best_i, best_rev = de, idx, True

            if best_i is not None:
                min_outer = r * cell
                if min_outer * min_outer > best_dist:
                    break

        if best_i is None:
            best_i = next(iter(remaining))
            best_rev = False

        remaining.discard(best_i)
        _grid_remove(best_i)

        sp = subpaths[best_i]
        if best_rev:
            sp = list(reversed(sp))
        ordered.append(sp)
        cur_x, cur_y = sp[-1]

    return ordered

def _two_opt(ordered: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """Apply 2-opt heuristic to further reduce travel distance after initial greedy ordering."""
    if len(ordered) < 2:
        return ordered

    n = len(ordered)
    pts = [(p[0][0], p[0][1], p[-1][0], p[-1][1]) for p in ordered]

    improved = True
    passes = 0
    while improved and passes < 10:
        improved = False
        passes += 1
        for i in range(n - 1):
            for j in range(i + 1, n):
                if i > 0:
                    ex_prev, ey_prev = pts[i-1][2], pts[i-1][3]
                else:
                    ex_prev, ey_prev = 0.0, 0.0

                sx_i, sy_i = pts[i][0], pts[i][1]
                d_old1 = (ex_prev - sx_i)**2 + (ey_prev - sy_i)**2

                ex_j, ey_j = pts[j][2], pts[j][3]
                d_new1 = (ex_prev - ex_j)**2 + (ey_prev - ey_j)**2

                if j < n - 1:
                    sx_jp1, sy_jp1 = pts[j+1][0], pts[j+1][1]
                else:
                    sx_jp1, sy_jp1 = 0.0, 0.0

                d_old2 = (ex_j - sx_jp1)**2 + (ey_j - sy_jp1)**2
                d_new2 = (sx_i - sx_jp1)**2 + (sy_i - sy_jp1)**2

                if d_new1 + d_new2 < d_old1 + d_old2 - 1e-9:
                    ordered[i:j+1] = [list(reversed(p)) for p in reversed(ordered[i:j+1])]
                    pts[i:j+1] = [(p[2], p[3], p[0], p[1]) for p in reversed(pts[i:j+1])]
                    improved = True

    return ordered

class GCodeExporter:
    def export(self, layout: LayoutResult, gcode_params: GCodeParams, output_dir: str, basename: str = "page") -> list[str]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        created = []

        for page in layout.pages:
            idx = page.page_index + 1
            filename = out / f"{basename}_{idx}.gcode"
            gcode = self._generate_page_gcode(page, gcode_params)
            with open(filename, "w", encoding="utf-8") as f:
                f.write(gcode)
            created.append(str(filename))

        return created

    def _generate_page_gcode(self, page: PageLayout, params: GCodeParams) -> str:
        all_subpaths: list[list[tuple[float, float]]] = []

        for pg in page.glyphs:
            if pg.missing:
                continue
            for d_str in pg.glyph_variant.paths:
                subpaths = _flatten_glyph_path(d_str, pg.x, pg.y, pg.scale)
                all_subpaths.extend(subpaths)

        for conn in page.connectors:
            if conn.cx1 is not None:
                all_subpaths.append(_flatten_cubic_bezier(
                    conn.x1, conn.y1,
                    conn.cx1, conn.cy1,
                    conn.cx2, conn.cy2,
                    conn.x2, conn.y2,
                ))
            else:
                all_subpaths.append([(conn.x1, conn.y1), (conn.x2, conn.y2)])

        page_h = page.height
        all_subpaths = [[(x, page_h - y) for x, y in sp] for sp in all_subpaths]

        all_subpaths = _merge_chains(all_subpaths)
        all_subpaths = _optimize_order(all_subpaths)
        all_subpaths = _two_opt(all_subpaths)

        lines = [
            "(Generated by Handwriter)",
            "G21 (All units in mm)",
            "G90 (Absolute positioning)",
            f"G00 Z{params.z_up} F{params.passing_feed}",
            "",
        ]

        for sp in all_subpaths:
            x0, y0 = sp[0]
            lines.append(f"G00 X{x0:.4f} Y{y0:.4f} F{params.passing_feed}")
            lines.append(f"G01 Z{params.z_down} F{params.penetration_feed}")
            first = True
            for x, y in sp[1:]:
                if first:
                    lines.append(f"G01 X{x:.4f} Y{y:.4f} F{params.feed}")
                    first = False
                else:
                    lines.append(f"X{x:.4f} Y{y:.4f}")
            lines.append(f"G00 Z{params.z_up} F{params.passing_feed}")

        lines += ["", f"G00 X0.0 Y0.0 F{params.passing_feed}", "M02", ""]
        return "\n".join(line for line in lines if line)