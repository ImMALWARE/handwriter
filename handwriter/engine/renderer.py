from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor, QPainterPath, QFont, QBrush, QFontMetricsF, QTransform
from PySide6.QtWidgets import QGraphicsScene, QGraphicsPathItem, QGraphicsSimpleTextItem
from functools import lru_cache
from svgpathtools import parse_path, Line, CubicBezier, QuadraticBezier, Arc
from handwriter.engine.layout_engine import LayoutResult, PageLayout
from handwriter.models.hwdoc import DocumentSettings

@lru_cache(maxsize=8192)
def _svg_d_to_painter_path(d_string: str) -> QPainterPath:
    path = QPainterPath()
    try:
        svg_path = parse_path(d_string)
    except Exception:
        return path

    if len(svg_path) == 0:
        return path

    start = svg_path[0].start
    path.moveTo(start.real, start.imag)

    prev_end = start
    for seg in svg_path:
        if abs(seg.start - prev_end) > 1e-6:
            path.moveTo(seg.start.real, seg.start.imag)

        if isinstance(seg, Line):
            path.lineTo(seg.end.real, seg.end.imag)
        elif isinstance(seg, CubicBezier):
            path.cubicTo(
                seg.control1.real, seg.control1.imag,
                seg.control2.real, seg.control2.imag,
                seg.end.real, seg.end.imag,
            )
        elif isinstance(seg, QuadraticBezier):
            path.quadTo(
                seg.control.real, seg.control.imag,
                seg.end.real, seg.end.imag,
            )
        elif isinstance(seg, Arc):
            n_steps = 20
            for step in range(1, n_steps + 1):
                t = step / n_steps
                pt = seg.point(t)
                path.lineTo(pt.real, pt.imag)
        else:
            path.lineTo(seg.end.real, seg.end.imag)

        prev_end = seg.end

    return path

class SceneRenderer:
    PEN_COLOR = QColor(20, 20, 40)
    CONNECTOR_COLOR = QColor(20, 20, 40)
    GRID_COLOR = QColor(160, 200, 240, 60)
    MARGIN_LINE_COLOR = QColor(220, 60, 60, 120)
    PAGE_BG_COLOR = QColor(255, 255, 255)
    PAGE_SHADOW_COLOR = QColor(0, 0, 0, 40)
    MISSING_COLOR = QColor(220, 60, 60)
    def __init__(self, scene: QGraphicsScene):
        self.scene = scene
        self._scale = 3.0  # mm → scene units (pixels at 1:1 zoom)
        self._settings: DocumentSettings | None = None

    def set_settings(self, settings: DocumentSettings) -> None:
        self._settings = settings

    def clear(self) -> None:
        self.scene.clear()

    def render_all_pages(self, layout: LayoutResult, gap: float = 10.0) -> None:
        self.clear()

        y_offset = 0.0
        s = self._scale
        for page_idx, page in enumerate(layout.pages):
            self._render_page_at_offset(layout, page_idx, y_offset)
            y_offset += page.height * s + gap * s

    def _render_page_at_offset(self, layout: LayoutResult, page_index: int, y_offset: float) -> None:
        if page_index >= len(layout.pages):
            return

        page = layout.pages[page_index]
        s = self._scale

        # Page shadow
        self.scene.addRect(
            4, y_offset + 4,
            page.width * s, page.height * s,
            QPen(Qt.PenStyle.NoPen),
            QBrush(self.PAGE_SHADOW_COLOR),
        )

        # Page background
        self.scene.addRect(
            0, y_offset,
            page.width * s, page.height * s,
            QPen(QColor(200, 200, 200), 1),
            QBrush(self.PAGE_BG_COLOR),
        )

        if self._settings and self._settings.show_grid:
            self._draw_notebook_grid(page, y_offset)

        self._draw_margin_lines(page, y_offset)

        connector_pen_width = 0.15 * s
        connector_pen = QPen(self.CONNECTOR_COLOR, connector_pen_width)
        connector_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        if page.connectors:
            for conn in page.connectors:
                conn_path = QPainterPath()
                conn_path.moveTo(conn.x1 * s, y_offset + conn.y1 * s)
                if conn.cx1 is not None:
                    conn_path.cubicTo(
                        conn.cx1 * s, y_offset + conn.cy1 * s,
                        conn.cx2 * s, y_offset + conn.cy2 * s,
                        conn.x2 * s, y_offset + conn.y2 * s,
                    )
                else:
                    conn_path.lineTo(conn.x2 * s, y_offset + conn.y2 * s)
                self.scene.addPath(conn_path, connector_pen)

        glyph_pen = QPen(self.PEN_COLOR, 0.15 * s)
        glyph_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        glyph_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        for pg in page.glyphs:
            if pg.missing:
                font = QFont("sans-serif")
                font.setPixelSize(int(6 * pg.scale * s))
                font.setWeight(QFont.Weight.Light)
                text_item = QGraphicsSimpleTextItem(pg.char)
                text_item.setFont(font)
                text_item.setBrush(QBrush(self.MISSING_COLOR))
                fm = QFontMetricsF(font)
                text_item.setPos(pg.x * s, y_offset + pg.y * s - fm.ascent())
                self.scene.addItem(text_item)
                continue

            transform = QTransform()
            transform.translate(pg.x * s, y_offset + pg.y * s)
            transform.scale(pg.scale * s, pg.scale * s)

            pg_path = QPainterPath()
            for d_str in pg.glyph_variant.paths:
                painter_path = _svg_d_to_painter_path(d_str)
                if not painter_path.isEmpty():
                    pg_path.addPath(transform.map(painter_path))
            
            if not pg_path.isEmpty():
                item = QGraphicsPathItem(pg_path)
                item.setPen(glyph_pen)
                item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
                self.scene.addItem(item)

    def _draw_notebook_grid(self, page: PageLayout, y_offset: float) -> None:
        s = self._scale
        pen = QPen(self.GRID_COLOR, 0.5)
        cell = 5.0

        path = QPainterPath()

        x = 0.0
        while x <= page.width:
            path.moveTo(x * s, y_offset)
            path.lineTo(x * s, y_offset + page.height * s)
            x += cell

        y = 0.0
        while y <= page.height:
            path.moveTo(0, y_offset + y * s)
            path.lineTo(page.width * s, y_offset + y * s)
            y += cell

        self.scene.addPath(path, pen)

    def _draw_margin_lines(self, page: PageLayout, y_offset: float) -> None:
        s = self._scale
        pen = QPen(self.MARGIN_LINE_COLOR, 1.0)

        if not self._settings:
            return

        margins = self._settings.margins
        mt = margins["top"]
        mb = margins["bottom"]
        ml = margins["left"]
        mr = margins["right"]
        pw = page.width
        ph = page.height

        path = QPainterPath()
        # Margin lines
        path.moveTo(0, y_offset + mt * s)
        path.lineTo(pw * s, y_offset + mt * s)

        top_first = margins.get("top_first", 0.0)
        if page.page_index == 0 and top_first > 0:
            path.moveTo(0, y_offset + top_first * s)
            path.lineTo(pw * s, y_offset + top_first * s)

        path.moveTo(0, y_offset + (ph - mb) * s)
        path.lineTo(pw * s, y_offset + (ph - mb) * s)
        path.moveTo(ml * s, y_offset)
        path.lineTo(ml * s, y_offset + ph * s)
        path.moveTo((pw - mr) * s, y_offset)
        path.lineTo((pw - mr) * s, y_offset + ph * s)

        self.scene.addPath(path, pen)