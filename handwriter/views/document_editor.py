from PySide6.QtCore import Qt, Signal, QTimer, QSize, QRect, QRunnable, QThreadPool, QObject
from PySide6.QtGui import QFont, QColor, QPainter, QTextFormat, QPalette
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsScene, QGraphicsView,
    QTextEdit, QPlainTextEdit, QSplitter, QLabel,
    QPushButton, QStackedWidget,
)
from qtawesome import icon
from re import compile as recompile
from dataclasses import replace
from pathlib import Path
from handwriter.models.hfont import HFont
from handwriter.models.hwdoc import HWDoc, GCodeParams
from handwriter.engine.layout_engine import LayoutEngine, LayoutResult
from handwriter.engine.renderer import SceneRenderer
from handwriter.engine.svg_exporter import SVGExporter
from handwriter.engine.gcode_exporter import GCodeExporter
from handwriter.views.theme import (
    COL_BASE, COL_MANTLE, COL_SURFACE0, COL_SURFACE1, COL_SURFACE2,
    COL_TEXT, COL_SUBTEXT
)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)
        self._line_color = QColor(COL_SURFACE1)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(COL_SUBTEXT))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(COL_SURFACE2))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(COL_TEXT))
        self.setPalette(palette)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.textChanged.connect(self.highlightCurrentLine)
        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()

    def lineNumberAreaWidth(self):
        digits = len(str(max(1, self.blockCount())))
        space = 16 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _=0):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))
        self.updateLineNumberAreaWidth(0)

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly() and not self.document().isEmpty() and not self.textCursor().hasSelection():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(self._line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor(COL_MANTLE))

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        pen_color = QColor(COL_SUBTEXT)
        painter.setPen(pen_color)
        font_height = self.fontMetrics().height()
        area_width = self.lineNumberArea.width() - 4

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.drawText(0, top, area_width, font_height,
                                 Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, number)
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            blockNumber += 1

class DocumentCanvas(QGraphicsView):
    def zoom_in(self, center: bool = False) -> None:
        if self.transform().m11() < 10.0: # Max zoom level
            old_anchor = self.transformationAnchor()
            if center:
                self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
            self.scale(1.15, 1.15) # Zoom factor
            if center:
                self.setTransformationAnchor(old_anchor)

    def zoom_out(self, center: bool = False) -> None:
        if self.transform().m11() > 0.1: # Min zoom level
            old_anchor = self.transformationAnchor()
            if center:
                self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
            self.scale(1.0 / 1.15, 1.0 / 1.15) # Zoom factor
            if center:
                self.setTransformationAnchor(old_anchor)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

ALIGN_PATTERN = recompile(r'\[/?(center|right)\]')

class WorkerSignals(QObject):
    result_ready = Signal(tuple)
    error_occurred = Signal(str)

class LayoutTask(QRunnable):
    def __init__(self, task_id, task_state, font, settings, text, variant_map):
        super().__init__()
        self.task_id = task_id
        self.task_state = task_state
        self.font = font
        self.settings = settings
        self.text = text
        self.variant_map = variant_map
        self.signals = WorkerSignals()

    def run(self):
        try:
            if self.task_id != self.task_state.get("latest_id"):
                return

            engine = LayoutEngine(self.font, self.settings)

            def is_cancelled():
                return self.task_id != self.task_state.get("latest_id")

            result = engine.layout_text(
                self.text, 
                self.variant_map if self.variant_map else None, 
                is_cancelled=is_cancelled
            )

            if not is_cancelled():
                self.signals.result_ready.emit((self.task_id, result))
        except Exception as e:
            print(f"LayoutTask error: {e}")
            self.signals.error_occurred.emit(str(e))
        finally:
            self.signals.deleteLater()

class DocumentEditorWidget(QWidget):
    text_changed = Signal()
    settings_changed = Signal()
    open_font_requested = Signal()
    create_font_requested = Signal()
    warnings_changed = Signal(str)

    def __init__(self, doc: HWDoc, parent=None):
        super().__init__(parent)
        self._doc = doc
        self._font: HFont | None = None
        self._layout_result: LayoutResult | None = None
        self._task_state = {"latest_id": 0}
        self._relayout_timer = QTimer(self)
        self._relayout_timer.setSingleShot(True)
        self._relayout_timer.setInterval(300)
        self._relayout_timer.timeout.connect(self._do_relayout)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        import handwriter.resources_rc
        _ = handwriter.resources_rc
        from PySide6.QtCore import QFile, QTextStream
        file = QFile(":/handwriter/views/document_editor.qss")
        if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
            qss_template = QTextStream(file).readAll()
            file.close()
        else:
            qss_template = ""
        self.setStyleSheet(
            qss_template
            .replace("{COL_BASE}", COL_BASE)
            .replace("{COL_MANTLE}", COL_MANTLE)
            .replace("{COL_SURFACE0}", COL_SURFACE0)
            .replace("{COL_SURFACE1}", COL_SURFACE1)
            .replace("{COL_SURFACE2}", COL_SURFACE2)
            .replace("{COL_TEXT}", COL_TEXT)
            .replace("{COL_SUBTEXT}", COL_SUBTEXT)
        )

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.text_edit = CodeEditor()
        self.text_edit.setPlaceholderText(self.tr("Enter or paste text"))
        self.text_edit.textChanged.connect(self._on_text_changed)
        left_layout.addWidget(self.text_edit)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.canvas_stack = QStackedWidget()

        placeholder_widget = QWidget()
        placeholder_layout = QVBoxLayout(placeholder_widget)
        placeholder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        placeholder_label = QLabel(self.tr("Select a font to get started"))
        placeholder_label.setObjectName("PlaceholderLabel")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(placeholder_label)
        placeholder_layout.addSpacing(16)

        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_layout.setSpacing(12)

        self.btn_placeholder_open = QPushButton(self.tr("Open") + " " + self.tr("Font").lower())
        self.btn_placeholder_open.setObjectName("PlaceholderButton")
        self.btn_placeholder_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_placeholder_open.clicked.connect(self.open_font_requested.emit)
        self.btn_placeholder_create = QPushButton(self.tr("New") + " " + self.tr("Font").lower())
        self.btn_placeholder_create.setObjectName("PlaceholderButton")
        self.btn_placeholder_create.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_placeholder_create.clicked.connect(self.create_font_requested.emit)

        btn_layout.addWidget(self.btn_placeholder_open)
        btn_layout.addWidget(self.btn_placeholder_create)

        placeholder_layout.addLayout(btn_layout)
        self.canvas_stack.addWidget(placeholder_widget)

        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)

        self.scene = QGraphicsScene(self)
        self.canvas = DocumentCanvas(self.scene)
        self.canvas.setRenderHints(
            self.canvas.renderHints()
            | QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.canvas.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.canvas.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        canvas_layout.addWidget(self.canvas)

        zoom_bar = QHBoxLayout()
        zoom_bar.setContentsMargins(0, 0, 8, 8)
        zoom_in_btn = QPushButton(icon('mdi6.magnify-plus', color=COL_TEXT), "")
        zoom_in_btn.setObjectName("ZoomButtonSquare")
        zoom_in_btn.setFixedSize(28, 28)
        zoom_in_btn.clicked.connect(lambda: self.canvas.zoom_in(center=True))
        
        zoom_out_btn = QPushButton(icon('mdi6.magnify-minus', color=COL_TEXT), "")
        zoom_out_btn.setObjectName("ZoomButtonSquare")
        zoom_out_btn.setFixedSize(28, 28)
        zoom_out_btn.clicked.connect(lambda: self.canvas.zoom_out(center=True))
        
        fit_btn = QPushButton(icon('mdi6.arrow-expand-all', color=COL_TEXT), " " + self.tr("Fit"))
        fit_btn.setObjectName("ZoomButtonFit")
        fit_btn.setFixedHeight(28)
        fit_btn.clicked.connect(self._fit_view)

        zoom_bar.addStretch()
        zoom_bar.addWidget(zoom_out_btn)
        zoom_bar.addWidget(zoom_in_btn)
        zoom_bar.addWidget(fit_btn)
        canvas_layout.addLayout(zoom_bar)

        self.canvas_stack.addWidget(canvas_container)
        right_layout.addWidget(self.canvas_stack)

        self.canvas_stack.setCurrentIndex(0)

        left_panel.setMinimumWidth(200)
        right_panel.setMinimumWidth(300)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([350, 750])

        layout.addWidget(splitter)

        self.renderer = SceneRenderer(self.scene)

    def set_document(self, doc: HWDoc) -> None:
        self._doc = doc
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(doc.text)
        self.text_edit.blockSignals(False)
        self._schedule_relayout()

    def set_font(self, font: HFont | None) -> None:
        self._font = font
        self.canvas_stack.setCurrentIndex(1 if font else 0)
        self._schedule_relayout()

    def sync_to_document(self) -> None:
        self._doc.text = self.text_edit.toPlainText()
        if self._layout_result:
            self._doc.variant_map = self._layout_result.variant_map

    def on_settings_changed_external(self) -> None:
        self.settings_changed.emit()
        self._schedule_relayout()

    def refresh(self) -> None:
        self._schedule_relayout()

    def export_svg(self, output_dir: str) -> None:
        if self._layout_result:
            exporter = SVGExporter()
            exporter.export(self._layout_result, output_dir)

    def export_gcode(self, output_dir: str, gcode_params: GCodeParams) -> None:
        if self._layout_result:
            exporter = GCodeExporter()
            exporter.export(self._layout_result, gcode_params, output_dir)

    def _apply_alignment(self, tag: str | None) -> None:
        cursor = self.text_edit.textCursor()

        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()

        cursor.beginEditBlock()

        cursor.setPosition(start_pos)
        cursor.movePosition(cursor.MoveOperation.StartOfBlock)
        start_block_pos = cursor.position()

        cursor.setPosition(end_pos)
        if start_pos != end_pos and cursor.positionInBlock() == 0:
            cursor.movePosition(cursor.MoveOperation.PreviousBlock)
        cursor.movePosition(cursor.MoveOperation.EndOfBlock)
        end_block_pos = cursor.position()

        cursor.setPosition(start_block_pos)
        cursor.setPosition(end_block_pos, cursor.MoveMode.KeepAnchor)

        selected_text = cursor.selectedText().replace('\u2029', '\n').replace('\u2028', '\n')

        clean_text = ALIGN_PATTERN.sub('', selected_text)

        if tag:
            new_text = f"[{tag}]{clean_text}[/{tag}]"
        else:
            new_text = clean_text

        cursor.insertText(new_text)

        cursor.setPosition(start_block_pos)
        cursor.setPosition(start_block_pos + len(new_text), cursor.MoveMode.KeepAnchor)
        self.text_edit.setTextCursor(cursor)

        cursor.endEditBlock()

    def align_left(self) -> None:
        self._apply_alignment(None)

    def align_center(self) -> None:
        self._apply_alignment("center")

    def align_right(self) -> None:
        self._apply_alignment("right")

    def _on_text_changed(self) -> None:
        self.text_changed.emit()
        self._schedule_relayout()

    def _schedule_relayout(self) -> None:
        self._relayout_timer.start()

    def _do_relayout(self) -> None:
        if not self._font:
            self.renderer.clear()
            return

        text = self.text_edit.toPlainText()
        self._doc.text = text

        settings_copy = replace(self._doc.settings, margins=self._doc.settings.margins.copy())
        variant_map_copy = self._doc.variant_map.copy() if self._doc.variant_map else {}

        self._task_state["latest_id"] += 1

        task = LayoutTask(
            task_id=self._task_state["latest_id"],
            task_state=self._task_state,
            font=self._font,
            settings=settings_copy,
            text=text,
            variant_map=variant_map_copy
        )
        task.signals.result_ready.connect(
            self._on_layout_finished, 
            Qt.ConnectionType.QueuedConnection
        )
        task.signals.error_occurred.connect(
            lambda err: self.warnings_changed.emit(self.tr("Layout error: {}").format(err)),
            Qt.ConnectionType.QueuedConnection
        )
        QThreadPool.globalInstance().start(task)

    def _on_layout_finished(self, payload: tuple) -> None:
        task_id, result = payload
        if task_id != self._task_state["latest_id"]:
            return

        self._layout_result = result
        self._doc.variant_map = self._layout_result.variant_map

        self.renderer.set_settings(self._doc.settings)

        self.renderer.render_all_pages(self._layout_result)

        warnings = []
        if self._layout_result.missing_chars:
            missing = ", ".join(sorted(self._layout_result.missing_chars)[:10])
            warnings.append(self.tr("Missing characters: {}").format(missing))

        if self._layout_result.invalid_bbcode_lines:
            lines_str = ", ".join(map(str, self._layout_result.invalid_bbcode_lines[:10]))
            if len(self._layout_result.invalid_bbcode_lines) > 10:
                lines_str += ", ..."
            warnings.append(self.tr("Invalid bbcode tags on line {}").format(lines_str))

        msg = " | ".join(warnings) if warnings else ""
        self.warnings_changed.emit(msg)

    def _fit_view(self) -> None:
        self.canvas.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)