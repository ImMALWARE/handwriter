from PySide6.QtCore import Qt, QPointF, Signal, QSize, QRectF, QPoint, QLineF, QSortFilterProxyModel, QModelIndex
from PySide6.QtGui import (
    QPen, QColor, QBrush,
    QCursor, QPainter, QUndoStack, QUndoCommand,
    QMouseEvent, QWheelEvent, QCloseEvent, QKeySequence,
    QShortcut, QStandardItemModel, QStandardItem, QPainterPath
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGraphicsScene, QGraphicsView, QGraphicsEllipseItem, QGraphicsPathItem,
    QListView, QLabel, QPushButton, QLineEdit,
    QFrame, QGraphicsItem, QMainWindow, QMessageBox, QFileDialog,
    QToolButton, QSizePolicy, QMenu, QStackedWidget,
    QGraphicsSceneMouseEvent
)
from handwriter.models.hfont import HFont, GlyphVariant
from handwriter.engine.renderer import _svg_d_to_painter_path
from qtawesome import icon
from pathlib import Path

from handwriter.views.theme import (
    COL_BASE, COL_MANTLE, COL_SURFACE0, COL_SURFACE1, COL_SURFACE2,
    COL_TEXT, COL_SUBTEXT, COL_BLUE, COL_GREEN, COL_RED
)

CANVAS_X_MIN = -15.0
CANVAS_X_MAX = 30.0
CANVAS_Y_MIN = -15.0
CANVAS_Y_MAX = 15.0

def _clamp_point(pos: QPointF) -> QPointF:
    x = max(CANVAS_X_MIN, min(CANVAS_X_MAX, pos.x()))
    y = max(CANVAS_Y_MIN, min(CANVAS_Y_MAX, pos.y()))
    return QPointF(x, y)

def _make_ribbon_button(icon_name: str, label: str, color: str = COL_TEXT,
                        icon_size: int = 28) -> QToolButton:
    btn = QToolButton()
    btn.setIcon(icon(icon_name, color=color, scale_factor=1.1))
    btn.setIconSize(QSize(icon_size, icon_size))
    btn.setText(label)
    btn.setToolTip(label.replace('\n', ' '))
    btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
    btn.setObjectName("RibbonButton")
    return btn

def _make_ribbon_separator() -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setFixedWidth(1)
    sep.setObjectName("RibbonSeparator")
    return sep

def _make_group_box(title: str, layout: QHBoxLayout) -> QWidget:
    container = QWidget()
    outer = QVBoxLayout(container)
    outer.setContentsMargins(4, 2, 4, 0)
    outer.setSpacing(0)

    layout.setContentsMargins(0, 0, 0, 0)
    content = QWidget()
    content.setLayout(layout)
    outer.addWidget(content, 1)

    title_label = QLabel(title)
    title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    title_label.setObjectName("GroupBoxTitle")
    outer.addWidget(title_label)

    return container

def _make_stroke_pen() -> QPen:
    pen = QPen(QColor(20, 20, 40), 0.15)  # Dark ink color, stroke width
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen

class DraggableMarker(QGraphicsEllipseItem):
    """A draggable circle marker for start/end connection points on the glyph canvas.
    Reports position changes via callbacks so the editor can update labels and push undo commands."""
    def __init__(self, x: float, y: float, color: QColor, label: str, on_move=None, on_release=None):
        r = 6
        super().__init__(-r, -r, 2 * r, 2 * r)
        self.setPos(x, y)
        self.setBrush(QBrush(color))
        self.setPen(QPen(color.darker(120), 1.5))  # Border width in screen pixels
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
            | QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
        )
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        self.setToolTip(label)
        self._on_move = on_move
        self._on_release = on_release
        self._label = label
        self._start_pos = QPointF(x, y)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        self._start_pos = self.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        super().mouseReleaseEvent(event)
        if self._on_release and self._start_pos != self.pos():
            self._on_release(self._label, self._start_pos, self.pos())

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            return _clamp_point(value)
        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self._on_move:
            self._on_move(self._label, value)
        return super().itemChange(change, value)

class DrawingView(QGraphicsView):
    """Custom QGraphicsView that supports freehand stroke drawing and zoom.
    Drawn strokes are converted to SVG path 'd' strings and emitted via stroke_drawn."""

    stroke_drawn = Signal(str)
    context_menu_requested = Signal(QPointF, QPoint)

    _CELL_SIZE = 5.0
    _GRID_X_START = -_CELL_SIZE * 3
    _GRID_X_END = _CELL_SIZE * 6
    _GRID_Y_START = -_CELL_SIZE * 3
    _GRID_Y_END = _CELL_SIZE * 3
    _GRID_X_STEPS = range(int(_GRID_X_START / _CELL_SIZE), int(_GRID_X_END / _CELL_SIZE) + 1)
    _GRID_Y_STEPS = range(int(_GRID_Y_START / _CELL_SIZE), int(_GRID_Y_END / _CELL_SIZE) + 1)

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setMouseTracking(True)
        self._drawing = False
        self._current_path_item = None
        self._current_painter_path = None
        self._current_points = []

        self._cached_grid_lines = []
        for i in self._GRID_X_STEPS:
            x = i * self._CELL_SIZE
            self._cached_grid_lines.append(QLineF(x, self._GRID_Y_START, x, self._GRID_Y_END))
        for i in self._GRID_Y_STEPS:
            y = i * self._CELL_SIZE
            self._cached_grid_lines.append(QLineF(self._GRID_X_START, y, self._GRID_X_END, y))

        self._pen_grid = QPen(QColor(160, 200, 240, 80), 0.08)
        self._pen_main = QPen(QColor(80, 140, 220, 160), 0.15)

    @staticmethod
    def _is_in_canvas(pos: QPointF) -> bool:
        """Check whether a scene position is within the drawable canvas bounds."""
        return CANVAS_X_MIN <= pos.x() <= CANVAS_X_MAX and CANVAS_Y_MIN <= pos.y() <= CANVAS_Y_MAX

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)

        painter.setPen(self._pen_grid)
        painter.drawLines(self._cached_grid_lines)

        painter.setPen(self._pen_main)
        painter.drawRect(0, -self._CELL_SIZE, self._CELL_SIZE, self._CELL_SIZE)

    def mousePressEvent(self, event: QMouseEvent):
        item = self.itemAt(event.pos())
        if isinstance(item, DraggableMarker):
            super().mousePressEvent(event)
            return

        pos = self.mapToScene(event.pos())
        if not self._is_in_canvas(pos):
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = True
            self._current_points = [pos]
            self._current_path_item = QGraphicsPathItem()
            self._current_painter_path = QPainterPath()
            self._current_painter_path.moveTo(pos)
            self._current_path_item.setPen(_make_stroke_pen())
            self.scene().addItem(self._current_path_item)
        elif event.button() == Qt.MouseButton.RightButton:
            self.context_menu_requested.emit(pos, event.globalPos())

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_in_canvas(self.mapToScene(event.pos())):
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.unsetCursor()

        if self._drawing and self._current_path_item and self._current_painter_path is not None:
            pos = _clamp_point(self.mapToScene(event.pos()))
            self._current_points.append(pos)
            self._current_painter_path.lineTo(pos)
            self._current_path_item.setPath(self._current_painter_path)
        super().mouseMoveEvent(event)

    @staticmethod
    def _build_svg_path(points: list[QPointF]) -> str:
        if not points: return ""
        return f"M {points[0].x():.2f} {points[0].y():.2f} " + " ".join(f"L {p.x():.2f} {p.y():.2f}" for p in points[1:])

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False
            # Remove the preview stroke before re-rendering via callback
            if self._current_path_item and self._current_path_item.scene():
                self.scene().removeItem(self._current_path_item)
            if len(self._current_points) > 1:
                self.stroke_drawn.emit(self._build_svg_path(self._current_points))
            self._current_points = []
            self._current_path_item = None
            self._current_painter_path = None
        super().mouseReleaseEvent(event)

    def zoom_by(self, factor: float) -> None:
        current_scale = self.transform().m11()
        min_scale = 10.0   # Minimum zoom scale
        max_scale = 200.0  # Maximum zoom scale

        new_scale = current_scale * factor
        if new_scale < min_scale:
            factor = min_scale / current_scale
        elif new_scale > max_scale:
            factor = max_scale / current_scale

        if abs(factor - 1.0) > 0.001:
            self.scale(factor, factor)

    def cancel_drawing(self) -> None:
        if not self._drawing:
            return
        self._drawing = False
        if self._current_path_item is not None:
            try:
                scene = self._current_path_item.scene()
                if scene is not None:
                    scene.removeItem(self._current_path_item)
            except RuntimeError:
                pass
        self._current_path_item = None
        self._current_painter_path = None
        self._current_points = []

    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            self.zoom_by(1.15)  # Zoom step factor
        else:
            self.zoom_by(1.0 / 1.15)

class ActionCommand(QUndoCommand):
    """Universal command class replacing the boilerplates of specific commands."""
    def __init__(self, editor: "FontEditorWindow", description: str, do_fn, undo_fn, with_context: bool = True):
        super().__init__(description)
        self.editor = editor
        self.do_fn = do_fn
        self.undo_fn = undo_fn
        self.with_context = with_context
        self.char = editor._current_char
        self.variant_idx = editor._current_variant_idx

    def _restore(self) -> None:
        if self.editor._current_char != self.char or self.editor._current_variant_idx != self.variant_idx:
            self.editor._current_char = self.char
            self.editor._current_variant_idx = self.variant_idx
            self.editor.select_char_silently(self.char)

    def redo(self) -> None:
        if not self.editor._font: return
        if self.with_context: self._restore()
        self.do_fn()
        if self.with_context: self.editor._render_current_variant()
        self.editor._update_window_title()

    def undo(self) -> None:
        if not self.editor._font: return
        if self.with_context: self._restore()
        self.undo_fn()
        if self.with_context: self.editor._render_current_variant()
        self.editor._update_window_title()

def check_saved(func):
    def wrapper(self, *args, **kwargs):
        if not self._check_saved():
            return
        return func(self, *args, **kwargs)
    return wrapper

class FontEditorWindow(QMainWindow):
    font_saved = Signal(object)

    @property
    def _is_dirty(self) -> bool:
        return not self.undo_stack.isClean()

    def _has_active_variant(self) -> bool:
        return self._font is not None and self._current_char is not None

    @property
    def _current_variants(self) -> list[GlyphVariant]:
        if not self._has_active_variant():
            return []
        return self._font.get_variants(self._current_char)

    def _get_current_variant(self) -> "GlyphVariant | None":
        variants = self._current_variants
        if not variants or self._current_variant_idx >= len(variants):
            return None
        return variants[self._current_variant_idx]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(900, 600)  # Minimum window dimensions
        self._font: HFont | None = None
        self._original_font: HFont | None = None
        self._current_char: str | None = None
        self._current_variant_idx: int = 0

        self._pen_stroke = _make_stroke_pen()
        self._no_brush = QBrush(Qt.BrushStyle.NoBrush)
        self._color_start = QColor(COL_BLUE)
        self._color_end = QColor(COL_RED)

        self._char_items_map = {}
        self._char_model = QStandardItemModel(self)
        self._proxy_model = QSortFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._char_model)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.undo_stack = QUndoStack(self)
        self.undo_stack.cleanChanged.connect(self._update_window_title)

        QShortcut(QKeySequence.StandardKey.Undo, self, self.undo_stack.undo)
        QShortcut(QKeySequence.StandardKey.Redo, self, self.undo_stack.redo)
        QShortcut(QKeySequence.StandardKey.Save, self, self._save_font)

        self._setup_ui()
        self._update_window_title()

    def _setup_ui(self) -> None:
        import handwriter.resources_rc
        _ = handwriter.resources_rc
        from PySide6.QtCore import QFile, QTextStream
        file = QFile(":/handwriter/views/font_editor.qss")
        if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
            qss_template = QTextStream(file).readAll()
            file.close()
        else:
            qss_template = ""
        color_map = {
            "{COL_BASE}": COL_BASE, "{COL_MANTLE}": COL_MANTLE,
            "{COL_SURFACE0}": COL_SURFACE0, "{COL_SURFACE1}": COL_SURFACE1,
            "{COL_SURFACE2}": COL_SURFACE2, "{COL_TEXT}": COL_TEXT,
            "{COL_SUBTEXT}": COL_SUBTEXT, "{COL_BLUE}": COL_BLUE,
            "{COL_GREEN}": COL_GREEN, "{COL_RED}": COL_RED,
        }
        for placeholder, value in color_map.items():
            qss_template = qss_template.replace(placeholder, value)
        self.setStyleSheet(qss_template)

        self.menuBar().hide()

        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setCentralWidget(central)

        self._setup_ribbon(main_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._setup_left_panel(splitter)
        self._setup_canvas(splitter)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([200, 700])

        main_layout.addWidget(splitter, 1)

    def _make_bar_button(self, icon_name: str, tooltip: str | None = None,
                         callback=None) -> QPushButton:
        btn = QPushButton(icon(icon_name, color=COL_TEXT), "")
        btn.setFixedSize(28, 28)
        btn.setObjectName("BarButton")
        if tooltip:
            btn.setToolTip(tooltip)
        if callback:
            btn.clicked.connect(callback)
        return btn

    def _setup_left_panel(self, splitter: QSplitter) -> None:
        left = QWidget()
        left.setObjectName("LeftPanel")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

        title = QLabel(self.tr("Characters"))
        title.setObjectName("LeftPanelTitle")
        left_layout.addWidget(title)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("Search"))
        self.search_input.setObjectName("SearchInput")
        self.search_input.textChanged.connect(self._filter_chars)
        left_layout.addWidget(self.search_input)

        self.char_list = QListView()
        self.char_list.setModel(self._proxy_model)
        self.char_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.char_list.customContextMenuRequested.connect(self._on_char_context_menu)
        self.char_list.setObjectName("CharList")
        self.char_list.selectionModel().currentChanged.connect(self._on_char_selected)
        left_layout.addWidget(self.char_list)

        add_row = QHBoxLayout()
        add_row.setSpacing(4)
        self.new_char_input = QLineEdit()
        self.new_char_input.setMaxLength(1)
        self.new_char_input.setObjectName("NewCharInput")
        self.new_char_input.setFixedWidth(50)
        add_row.addWidget(self.new_char_input)

        add_char_btn = QPushButton(icon('mdi6.plus', color=COL_BASE), "")
        add_char_btn.setFixedSize(32, 32)
        add_char_btn.setObjectName("AddCharBtn")
        add_char_btn.clicked.connect(self._add_new_char)
        add_row.addWidget(add_char_btn)
        left_layout.addLayout(add_row)

        left.setMinimumWidth(150)
        splitter.addWidget(left)

    def _setup_canvas(self, splitter: QSplitter) -> None:
        middle = QWidget()
        middle.setObjectName("MiddlePanel")
        mid_layout = QVBoxLayout(middle)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(0)

        self.canvas_stack = QStackedWidget()
        mid_layout.addWidget(self.canvas_stack)

        placeholder_widget = QWidget()
        placeholder_widget.setObjectName("PlaceholderWidget")
        placeholder_layout = QVBoxLayout(placeholder_widget)
        placeholder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label = QLabel(self.tr("Select or create a character"))
        self.placeholder_label.setObjectName("PlaceholderLabel")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(self.placeholder_label)
        self.canvas_stack.addWidget(placeholder_widget)

        self.glyph_scene = QGraphicsScene()
        self.glyph_scene.setSceneRect(-15, -15, 45, 30)  # Fixed rect matching canvas/grid bounds
        self.glyph_view = DrawingView(self.glyph_scene)
        self.glyph_view.stroke_drawn.connect(self._on_stroke_drawn)
        self.glyph_view.context_menu_requested.connect(self._on_canvas_context_menu)
        self.glyph_view.setRenderHints(
            self.glyph_view.renderHints()
            | QPainter.RenderHint.Antialiasing
        )
        self.glyph_view.setObjectName("GlyphView")
        self.canvas_stack.addWidget(self.glyph_view)

        self._setup_variant_bar(mid_layout)

        middle.setMinimumWidth(300)
        splitter.addWidget(middle)

    def _setup_variant_bar(self, parent_layout: QVBoxLayout) -> None:
        var_bar = QHBoxLayout()
        var_bar.setContentsMargins(8, 4, 8, 4)
        var_bar.setSpacing(4)

        self.prev_var_btn = self._make_bar_button('mdi6.chevron-left', callback=self._prev_variant)
        var_bar.addWidget(self.prev_var_btn)

        self.var_label = QLabel("0/0")
        self.var_label.setObjectName("VarLabel")
        self.var_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.var_label.setFixedWidth(40)
        var_bar.addWidget(self.var_label)

        self.next_var_btn = self._make_bar_button('mdi6.chevron-right', callback=self._next_variant)
        var_bar.addWidget(self.next_var_btn)

        var_bar.addSpacing(8)

        buttons = [
            ('add_var_btn', 'mdi6.plus', self.tr("Add variant"), self._add_variant),
            ('del_var_btn', 'mdi6.trash-can-outline', self.tr("Delete variant"), self._delete_variant),
            ('clear_btn', 'mdi6.eraser', self.tr("Clear"), self._clear_variant),
            (None, None, None, None), # Stretch placeholder
            ('zoom_out_btn', 'mdi6.magnify-minus', self.tr("Zoom out"), lambda: self.glyph_view.zoom_by(1/1.2)),
            ('zoom_in_btn', 'mdi6.magnify-plus', self.tr("Zoom in"), lambda: self.glyph_view.zoom_by(1.2)),
        ]

        for attr, icon_name, tooltip, cb in buttons:
            if attr is None:
                var_bar.addStretch()
                continue
            btn = self._make_bar_button(icon_name, tooltip, cb)
            setattr(self, attr, btn)
            var_bar.addWidget(btn)

        self.fit_btn = QPushButton(icon('mdi6.arrow-expand-all', color=COL_TEXT), " " + self.tr("Fit"))
        self.fit_btn.setFixedHeight(28)
        self.fit_btn.setObjectName("BarButton")
        self.fit_btn.clicked.connect(self._fit_view)
        var_bar.addWidget(self.fit_btn)

        parent_layout.addLayout(var_bar)

    @staticmethod
    def _add_ribbon_group(title: str, buttons: list, target_layout: QHBoxLayout) -> list:
        layout = QHBoxLayout()
        layout.setSpacing(2)
        btns = []
        for icon, label, callback in buttons:
            btn = _make_ribbon_button(icon, label)
            if callback:
                btn.clicked.connect(callback)
            layout.addWidget(btn)
            btns.append(btn)
        target_layout.addWidget(_make_group_box(title, layout))
        return btns

    def _setup_ribbon(self, main_layout: QVBoxLayout) -> None:
        ribbon = QWidget()
        ribbon.setFixedHeight(90)  # Ribbon panel height
        ribbon.setObjectName("Ribbon")
        ribbon_layout = QHBoxLayout(ribbon)
        ribbon_layout.setContentsMargins(4, 2, 4, 2)
        ribbon_layout.setSpacing(0)

        self.btn_new_font, self.btn_open_font, self.btn_save_font, self.btn_save_font_as = self._add_ribbon_group(self.tr("File"), [
            ('mdi6.file-plus-outline', self.tr("New") + "\n" + self.tr("font"), self._new_font),
            ('mdi6.folder-open-outline', self.tr("Open"), self._open_font),
            ('mdi6.content-save-outline', self.tr("Save"), self._save_font),
            ('mdi6.content-save-edit-outline', self.tr("Save") + "\n" + self.tr("As").lower(), self._save_font_as)
        ], ribbon_layout)

        ribbon_layout.addWidget(_make_ribbon_separator())

        self.btn_undo, self.btn_redo = self._add_ribbon_group(self.tr("History"), [
            ('mdi6.undo', self.tr("Undo"), self.undo_stack.undo),
            ('mdi6.redo', self.tr("Redo"), self.undo_stack.redo)
        ], ribbon_layout)
        self.btn_undo.setEnabled(False)
        self.btn_redo.setEnabled(False)
        self.undo_stack.canUndoChanged.connect(self.btn_undo.setEnabled)
        self.undo_stack.canRedoChanged.connect(self.btn_redo.setEnabled)

        ribbon_layout.addWidget(_make_ribbon_separator())

        pts_layout = QVBoxLayout()
        pts_layout.setSpacing(2)

        def _make_pt_label(text: str, name: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setObjectName(name)
            pts_layout.addWidget(lbl)
            return lbl

        self.start_label = _make_pt_label(self.tr("Start: {}").format("—"), "StartLabel")
        self.end_label = _make_pt_label(self.tr("End: {}").format("—"), "EndLabel")

        pts_wrapper_layout = QHBoxLayout()
        pts_wrapper_layout.addLayout(pts_layout)
        ribbon_layout.addWidget(_make_group_box(self.tr("Connection points"), pts_wrapper_layout))

        ribbon_layout.addStretch()

        main_layout.addWidget(ribbon)

    def _reset_state(self) -> None:
        self._current_char = None
        self._current_variant_idx = 0
        self.undo_stack.clear()
        self._refresh_char_list()
        self.glyph_scene.clear()
        self._show_empty_state()
        self._update_window_title()

    def set_font(self, font: HFont | None) -> None:
        self._original_font = font
        if font is not None:
            self._font = font.clone()
        else:
            self._font = None
        self._reset_state()

    def set_active_char(self, char: str | None, variant_idx: int = 0) -> None:
        self._current_char = char
        self._current_variant_idx = variant_idx
        self.select_char_silently(char)
        self._render_current_variant()
        self._update_window_title()

    def _find_item_by_char(self, char: str) -> QStandardItem | None:
        return self._char_items_map.get(char)

    def select_char_silently(self, char: str | None) -> None:
        sel_model = self.char_list.selectionModel()
        if not sel_model: return

        sel_model.blockSignals(True)
        idx = QModelIndex()
        if char is not None and (item := self._find_item_by_char(char)):
            idx = self._proxy_model.mapFromSource(item.index())
        sel_model.setCurrentIndex(idx, sel_model.SelectionFlag.ClearAndSelect)
        sel_model.blockSignals(False)

    def _get_char_display_text(self, char: str) -> str:
        count = len(self._font.get_variants(char))
        return f"  {char}   ({count})"

    def _update_char_item(self, char: str) -> None:
        if item := self._find_item_by_char(char):
            item.setText(self._get_char_display_text(char))

    def _create_char_item(self, char: str) -> QStandardItem:
        item = QStandardItem(self._get_char_display_text(char))
        item.setData(char, Qt.ItemDataRole.UserRole)
        item.setEditable(False)
        return item

    def _insert_char_item(self, row: int, char: str) -> None:
        item = self._create_char_item(char)
        self._char_items_map[char] = item
        if row >= 0:
            self._char_model.insertRow(row, item)
        else:
            self._char_model.appendRow(item)

    def _remove_char_item(self, char: str) -> None:
        if item := self._find_item_by_char(char):
            self._char_model.removeRow(item.row())
            self._char_items_map.pop(char, None)

    def _add_char_completely(self, char: str, row: int = -1, variants: list = None) -> None:
        if variants is None:
            self._font.add_variant(char, GlyphVariant())
        else:
            self._font.set_variants(char, list(variants))
        self._insert_char_item(row, char)
        self.set_active_char(char)

    def _remove_char_completely(self, char: str) -> None:
        self._font.remove_char(char)
        self._remove_char_item(char)
        if self._current_char == char:
            self.set_active_char(None)

    def _refresh_char_list(self) -> None:
        self._char_model.clear()
        self._char_items_map.clear()

        if not self._font:
            self._update_variant_buttons()
            return

        items = []
        for char in self._font.chars:
            item = self._create_char_item(char)
            self._char_items_map[char] = item
            items.append(item)

        if items:
            self._char_model.invisibleRootItem().appendRows(items)

        self.select_char_silently(self._current_char)
        self._update_variant_buttons()

    def _filter_chars(self, text: str) -> None:
        self._proxy_model.setFilterRegularExpression(text)

    def _on_char_selected(self, current: QModelIndex, _: QModelIndex) -> None:
        if not current.isValid() or not self._font:
            return
        self._current_char = current.data(Qt.ItemDataRole.UserRole)
        self._current_variant_idx = 0
        self._render_current_variant()
        self._update_window_title()
        self._fit_view()

    def _on_char_context_menu(self, pos: QPoint) -> None:
        index = self.char_list.indexAt(pos)
        if not index.isValid() or not self._font:
            return
        char = index.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        delete_act = menu.addAction(icon('mdi6.trash-can-outline', color=COL_RED), self.tr("Delete"))
        action = menu.exec_(self.char_list.viewport().mapToGlobal(pos))
        if action == delete_act:
            self._delete_char(char)

    def _delete_char(self, char: str) -> None:
        if not self._font or not self._font.has_char(char): return

        deleted_variants = list(self._font.get_variants(char))
        item = self._find_item_by_char(char)
        row_index = item.row() if item else -1

        self.undo_stack.push(ActionCommand(
            self, f"Delete Character '{char}'",
            lambda: self._remove_char_completely(char),
            lambda: self._add_char_completely(char, row_index, deleted_variants),
            with_context=False
        ))

    def _prev_variant(self) -> None:
        if self._current_variant_idx > 0:
            self._current_variant_idx -= 1
            self._render_current_variant()

    def _next_variant(self) -> None:
        if self._current_variant_idx < len(self._current_variants) - 1:
            self._current_variant_idx += 1
            self._render_current_variant()

    def _update_variant_buttons(self) -> None:
        has_variant = self._has_active_variant()
        var_count = len(self._current_variants) if has_variant else 0

        for btn in (self.add_var_btn, self.del_var_btn, self.clear_btn,
                    self.zoom_in_btn, self.zoom_out_btn, self.fit_btn):
            btn.setEnabled(has_variant)
        self.prev_var_btn.setEnabled(has_variant and self._current_variant_idx > 0)
        self.next_var_btn.setEnabled(
            has_variant and self._current_variant_idx < var_count - 1
        )

    def _set_marker_label(self, label: str, point: tuple[float, float] | None = None, show_hint: bool = False) -> None:
        tr_label = self.tr("Start: {}") if label == "start" else self.tr("End: {}")
        status_label = self.start_label if label == "start" else self.end_label

        if point is not None:
            text = f"({point[0]:.1f}, {point[1]:.1f})"
        elif show_hint:
            text = "— " + self.tr("(right-click to add)")
        else:
            text = "—"

        status_label.setText(tr_label.format(text))

    def _show_empty_state(self) -> None:
        self.var_label.setText("0/0")
        self._set_marker_label("start")
        self._set_marker_label("end")
        self.canvas_stack.setCurrentIndex(0)
        self._update_variant_buttons()

    def _render_current_variant(self) -> None:
        self.glyph_view.cancel_drawing()
        self.glyph_scene.clear()

        variant = self._get_current_variant()
        if not variant:
            self._show_empty_state()
            return

        was_placeholder = self.canvas_stack.currentIndex() == 0
        self.canvas_stack.setCurrentIndex(1)
        if was_placeholder:
            self._fit_view()

        variants = self._current_variants
        idx = min(self._current_variant_idx, len(variants) - 1)
        self._current_variant_idx = idx

        self.var_label.setText(f"{idx + 1}/{len(variants)}")

        for d_str in variant.paths:
            painter_path = _svg_d_to_painter_path(d_str)
            if not painter_path.isEmpty():
                item = QGraphicsPathItem()
                item.setPath(painter_path)
                item.setPen(self._pen_stroke)
                item.setBrush(self._no_brush)
                self.glyph_scene.addItem(item)

        self._place_marker(variant.start, self._color_start, "start")
        self._place_marker(variant.end, self._color_end, "end")
        self._update_variant_buttons()

    def _place_marker(self, point: tuple[float, float] | None, color: QColor, label: str) -> None:
        """Add a draggable connection-point marker to the scene, or show a placeholder hint."""
        if point is not None:
            marker = DraggableMarker(
                point[0], point[1], color, label,
                on_move=self._on_marker_moved,
                on_release=self._on_marker_released,
            )
            self.glyph_scene.addItem(marker)
        self._set_marker_label(label, point, show_hint=point is None)

    def _on_marker_moved(self, label: str, pos: QPointF) -> None:
        self._set_marker_label(label, (pos.x(), pos.y()))

    def _push_marker_move_command(self, is_start: bool, old_pt: tuple[float, float] | None, new_pt: tuple[float, float]) -> None:
        variant = self._get_current_variant()
        if not variant: return
        def set_pt(pt):
            if is_start: variant.start = pt
            else: variant.end = pt
        self.undo_stack.push(ActionCommand(
            self, f"Move {'Start' if is_start else 'End'} Marker",
            lambda: set_pt(new_pt),
            lambda: set_pt(old_pt)
        ))

    def _on_marker_released(self, label: str, old_pos: QPointF, new_pos: QPointF) -> None:
        self._push_marker_move_command(
            label == "start",
            (old_pos.x(), old_pos.y()),
            (new_pos.x(), new_pos.y())
        )

    def _add_variant(self) -> None:
        char = self._current_char
        if not char: return

        def do_add():
            self._font.add_variant(char, GlyphVariant())
            self._current_variant_idx = len(self._current_variants) - 1
            self._update_char_item(char)

        def undo_add():
            self._font.remove_variant(char, len(self._current_variants) - 1)
            self._current_variant_idx = max(0, len(self._current_variants) - 1)
            self._update_char_item(char)

        self.undo_stack.push(ActionCommand(self, "Add Variant", do_add, undo_add))

    def _delete_variant(self) -> None:
        char = self._current_char
        if not char: return
        del_idx = self._current_variant_idx
        deleted_variant = self._current_variants[del_idx]

        def do_del():
            self._font.remove_variant(char, del_idx)
            if not self._current_variants: self.set_active_char(None)
            else: self._current_variant_idx = max(0, del_idx - 1)
            self._update_char_item(char)

        def undo_del():
            self._font.insert_variant(char, del_idx, deleted_variant)
            self._current_char = char
            self._current_variant_idx = del_idx
            self._update_char_item(char)

        self.undo_stack.push(ActionCommand(self, "Delete Variant", do_del, undo_del))

    def _clear_variant(self) -> None:
        variant = self._get_current_variant()
        if not variant: return
        old_paths = list(variant.paths)

        self.undo_stack.push(ActionCommand(
            self, "Clear Variant",
            lambda: variant.paths.clear(),
            lambda: setattr(variant, 'paths', list(old_paths))
        ))

    def _on_stroke_drawn(self, d_string: str) -> None:
        variant = self._get_current_variant()
        if not variant: return

        self.undo_stack.push(ActionCommand(
            self, "Add Stroke",
            lambda: variant.paths.append(d_string),
            lambda: variant.paths.pop() if variant.paths else None
        ))

    def _on_canvas_context_menu(self, scene_pos, global_pos) -> None:
        variant = self._get_current_variant()
        if not variant: return

        menu = QMenu(self)
        start_act = menu.addAction(self.tr("Set start point"))
        end_act = menu.addAction(self.tr("Set end point"))

        action = menu.exec_(global_pos)

        if action in (start_act, end_act):
            is_start = action == start_act
            old_pos = variant.start if is_start else variant.end
            self._push_marker_move_command(
                is_start,
                old_pos,
                (scene_pos.x(), scene_pos.y())
            )

    def _add_new_char(self) -> None:
        char = self.new_char_input.text().strip()
        if not char: return
        if not self._font:
            self._font = HFont()
            self._original_font = self._font.clone()

        if self._font.has_char(char):
            QMessageBox.information(self, self.tr("Handwriter Font Editor"), self.tr('Character "{}" already exists.').format(char))
            return

        self.undo_stack.push(ActionCommand(
            self, f"Add Character '{char}'",
            lambda: self._add_char_completely(char) if not self._font.has_char(char) else None,
            lambda: self._remove_char_completely(char),
            with_context=False
        ))
        self.new_char_input.clear()

    def _fit_view(self) -> None:
        self.glyph_view.fitInView(
            self.glyph_scene.sceneRect().adjusted(-5, -5, 5, 5),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    def _check_saved(self) -> bool:
        if not self._is_dirty:
            return True

        msg = QMessageBox(self)
        msg.setWindowTitle(self.tr("Unsaved changes"))
        msg.setText(self.tr("You have unsaved changes. Do you want to save them?"))
        msg.setIcon(QMessageBox.Icon.Question)
        btn_yes = msg.addButton(self.tr("Yes"), QMessageBox.ButtonRole.YesRole)
        btn_no = msg.addButton(self.tr("No"), QMessageBox.ButtonRole.NoRole)
        btn_cancel = msg.addButton(self.tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        
        reply = msg.clickedButton()
        if reply == btn_yes:
            self._save_font()
            if self._is_dirty:
                return False
        if reply == btn_cancel:
            return False

        return True

    @check_saved
    def _new_font(self) -> None:
        self._font = HFont()
        self._reset_state()

    def _mark_saved(self) -> None:
        self.undo_stack.setClean()
        self._original_font = self._font.clone()
        self.font_saved.emit(self._font)
        self._update_window_title()

    def _save_font(self) -> None:
        if not self._font:
            return
        if self._font.path:
            self._font.save()
            self._mark_saved()
        else:
            self._save_font_as()

    def _save_font_as(self) -> None:
        if not self._font:
            return
        path, _ = QFileDialog.getSaveFileName(
            None, self.tr("Save") + " " + self.tr("As").lower(), "myfont.hfont",
            self.tr("Handwriter Fonts (*.hfont)")
        )
        if path:
            self._font.save(path)
            self._mark_saved()

    @check_saved
    def _open_font(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None, self.tr("Open") + " " + self.tr("font"), "",
            self.tr("Handwriter Fonts (*.hfont);;All Files (*)")
        )
        if path:
            try:
                font = HFont.load(path)
                self.set_font(font)
            except Exception as e:
                QMessageBox.critical(self, self.tr("Error"), self.tr("Failed to") + " " + self.tr("Load").lower() + ": " + self.tr("font") + f"\n{e}")

    @check_saved
    def _close_font(self) -> None:
        self._font = None
        self._reset_state()

    def _update_window_title(self) -> None:
        editor_title = self.tr("Handwriter Font Editor")
        font_name = self._font.name if self._font else self.tr("New font")

        if self._current_char:
            self.setWindowTitle(f"[*] {self._current_char} — {font_name} — {editor_title}")
        else:
            self.setWindowTitle(f"[*] {font_name} — {editor_title}")

        self.setWindowModified(self._is_dirty)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._check_saved():
            event.ignore()
        else:
            # Revert to the original font so the parent window doesn't
            # see uncommitted edits after the editor is closed.
            if self._is_dirty and self._original_font is not None:
                self._font = self._original_font.clone()
            event.accept()