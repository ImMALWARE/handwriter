from pathlib import Path
from svgwrite import Drawing
from handwriter.engine.layout_engine import LayoutResult

class SVGExporter:
    def export(self, layout: LayoutResult, output_dir: str, basename: str = "page") -> list[str]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        created = []

        for page in layout.pages:
            idx = page.page_index + 1
            filename = out / f"{basename}_{idx}.svg"
            dwg = Drawing(
                str(filename),
                size=(f"{page.width}mm", f"{page.height}mm"),
            )
            dwg.viewbox(0, 0, page.width, page.height)

            if page.connectors:
                conn_group = dwg.add(dwg.g(id="connectors", fill="none", stroke="black", stroke_width=0.4))
                d_parts = []
                for conn in page.connectors:
                    if conn.cx1 is not None:
                        d_parts.append(
                            f"M{conn.x1:.3f},{conn.y1:.3f} "
                            f"C{conn.cx1:.3f},{conn.cy1:.3f} "
                            f"{conn.cx2:.3f},{conn.cy2:.3f} "
                            f"{conn.x2:.3f},{conn.y2:.3f}"
                        )
                    else:
                        d_parts.append(f"M{conn.x1:.3f},{conn.y1:.3f} L{conn.x2:.3f},{conn.y2:.3f}")
                conn_group.add(dwg.path(d=" ".join(d_parts)))

            glyph_group = dwg.add(dwg.g(id="glyphs", fill="none", stroke="black", stroke_width=0.5))
            for pg in page.glyphs:
                if pg.missing or not pg.glyph_variant.paths:
                    continue

                if abs(pg.scale - 1.0) < 1e-4:
                    transform_str = f"translate({pg.x:.3f},{pg.y:.3f})"
                else:
                    transform_str = f"translate({pg.x:.3f},{pg.y:.3f}) scale({pg.scale:.3f})"

                combined_path = " ".join(pg.glyph_variant.paths)
                if combined_path:
                    glyph_group.add(dwg.path(d=combined_path, transform=transform_str))

            dwg.save()
            created.append(str(filename))

        return created