from copy import copy
from time import time
from os.path import exists, basename
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QSettings, QSize, QPointF, QTimer, QSignalBlocker, QStandardPaths
from PySide6.QtGui import QPainter, QColor, QPolygonF, QUndoStack, QUndoCommand, QShortcut, QKeySequence, QPaintEvent, QCloseEvent
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QWidget,
    QFileDialog, QMessageBox, QHBoxLayout, QVBoxLayout,
    QToolButton, QLabel, QFrame, QSizePolicy, QDoubleSpinBox,
    QStyle, QStyleOptionSpinBox,
)
from qtawesome import icon
from handwriter.models.hfont import HFont
from handwriter.models.hwdoc import HWDoc
from handwriter.models.presets import TemplateManager, PaperTemplate
from handwriter.views.document_editor import DocumentEditorWidget
from handwriter.views.font_editor import FontEditorWindow
from handwriter.views.export_dialog import ExportDialog

from handwriter.views.theme import (
    COL_BASE, COL_MANTLE, COL_SURFACE0, COL_SURFACE1, COL_SURFACE2,
    COL_TEXT, COL_SUBTEXT, COL_BLUE, COL_GREEN, COL_RED
)

class RibbonBuilder:
    @staticmethod
    def make_button(icon_name: str, label: str, slot=None, color: str = COL_TEXT,
                    icon_size: int = 28) -> QToolButton:
        btn = QToolButton()
        btn.setIcon(icon(icon_name, color=color, scale_factor=1.1))
        btn.setIconSize(QSize(icon_size, icon_size))
        btn.setText(label)
        # Tooltip = same text as label, but with newlines replaced by spaces
        btn.setToolTip(label.replace('\n', ' '))
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        btn.setObjectName("ribbonButton")
        if slot:
            btn.clicked.connect(slot)
        return btn

    @staticmethod
    def make_separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setObjectName("ribbonSeparator")
        return sep

    @staticmethod
    def make_group_box(title: str, layout: QHBoxLayout) -> QWidget:
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
        title_label.setObjectName("ribbonGroupTitle")
        outer.addWidget(title_label)

        return container

    @staticmethod
    def add_group(main_layout: QHBoxLayout, title: str, widgets: list[QWidget], spacing: int = 2, separator: bool = True) -> None:
        group_layout = QHBoxLayout()
        group_layout.setSpacing(spacing)
        for w in widgets:
            group_layout.addWidget(w)
        main_layout.addWidget(RibbonBuilder.make_group_box(title, group_layout))
        if separator:
            main_layout.addWidget(RibbonBuilder.make_separator())

class RibbonSpinBox(QDoubleSpinBox):
    _UP_POLY = QPolygonF([QPointF(0, -2.5), QPointF(-3.5, 2), QPointF(3.5, 2)])
    _DOWN_POLY = QPolygonF([QPointF(-3.5, -2), QPointF(3.5, -2), QPointF(0, 2.5)])

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDecimals(0)

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COL_TEXT))

        opt = QStyleOptionSpinBox()
        self.initStyleOption(opt)
        style = self.style()

        up_rect = style.subControlRect(
            QStyle.ComplexControl.CC_SpinBox, opt,
            QStyle.SubControl.SC_SpinBoxUp, self)
        down_rect = style.subControlRect(
            QStyle.ComplexControl.CC_SpinBox, opt,
            QStyle.SubControl.SC_SpinBoxDown, self)

        cx_up = up_rect.center().x()
        cy_up = up_rect.center().y()
        painter.translate(cx_up, cy_up)
        painter.drawPolygon(self._UP_POLY)
        painter.translate(-cx_up, -cy_up)

        cx_down = down_rect.center().x()
        cy_down = down_rect.center().y()
        painter.translate(cx_down, cy_down)
        painter.drawPolygon(self._DOWN_POLY)

        painter.end()

class LabeledSpinBox(QWidget):
    def __init__(self, label_text: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(1)

        self.spin = RibbonSpinBox()
        layout.addWidget(self.spin, 0, Qt.AlignmentFlag.AlignVCenter)

        self.label = QLabel(label_text)
        self.label.setObjectName("labeledSpinBoxLabel")
        self.label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.label)

    def setup(self, min_val, max_val, step, suffix="", decimals=0, value=0.0, slot=None):
        self.spin.setRange(min_val, max_val)
        self.spin.setSingleStep(step)
        self.spin.setDecimals(decimals)
        if suffix:
            self.spin.setSuffix(suffix)
        self.spin.setValue(value)
        if slot:
            self.spin.valueChanged.connect(slot)
        return self

    @property
    def value(self):
        return self.spin.value

    @value.setter
    def value(self, v):
        self.spin.setValue(v)

class SettingsCommand(QUndoCommand):
    def __init__(self, window, old_settings, new_settings):
        super().__init__("Change Settings")
        self.window = window
        self.old_settings = old_settings
        self.new_settings = new_settings
        self.time = time()

    def id(self):
        return 1

    def mergeWith(self, other):
        if other.id() != self.id():
            return False
        if other.time - self.time < 1.0:
            self.new_settings = copy(other.new_settings)
            self.new_settings.margins = self.new_settings.margins.copy()
            self.time = other.time
            return True
        return False

    def redo(self):
        self.window._apply_settings_state(self.new_settings)

    def undo(self):
        self.window._apply_settings_state(self.old_settings)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Handwriter")
        self.setMinimumSize(1100, 750)
        self.resize(1400, 900)

        self.template_manager = TemplateManager()
        self._current_font: HFont | None = None
        self._current_doc: HWDoc = HWDoc()
        self._doc_dirty: bool = False
        self._cells_mode: bool = False

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(1000)
        self.save_timer.timeout.connect(self._save_settings)

        self.undo_stack = QUndoStack(self)
        QShortcut(QKeySequence.StandardKey.Undo, self, self.undo_stack.undo)
        QShortcut(QKeySequence.StandardKey.Redo, self, self.undo_stack.redo)
        QShortcut(QKeySequence.StandardKey.Save, self, self._save_document)

        self._setup_ui()
        self._setup_ribbon()
        self._setup_statusbar()

        config_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
        config_path = str(Path(config_dir) / "Handwriter.conf")
        self.settings = QSettings(config_path, QSettings.Format.IniFormat)
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        s = self._current_doc.settings
        for key in ["paper_width", "paper_height", "letter_size", "line_spacing"]:
            setattr(s, key, MainWindow._safe_float(self.settings.value(key), getattr(s, key)))

        s.show_grid = self.settings.value("show_grid", s.show_grid, type=bool)

        for key in ["top", "bottom", "left", "right"]:
            s.margins[key] = MainWindow._safe_float(self.settings.value(f"margin_{key}"), s.margins[key])

        last_doc_path = self.settings.value("last_doc_path", "")
        if last_doc_path and exists(last_doc_path):
            self._current_doc.path = Path(last_doc_path)

        self._current_doc.text = self.settings.value("last_text", "")

        gp = self._current_doc.gcode_params
        for key in ["feed", "passing_feed", "penetration_feed", "z_up", "z_down"]:
            setattr(gp, key, MainWindow._safe_float(self.settings.value(f"gcode_{key}"), getattr(gp, key)))

        font_path = self.settings.value("last_font_path", "")
        if font_path and exists(font_path):
            try:
                self._current_font = HFont.load(font_path)
                self.font_editor_window.set_font(self._current_font)
                self.doc_editor.set_font(self._current_font)
            except Exception as e:
                print(f"Failed to load last font: {e}")

        self.doc_editor.set_document(self._current_doc)
        self._sync_ribbon_from_doc()
        self._update_window_title()

    @staticmethod
    def _safe_float(val: Any, default: float) -> float:
        try: return float(val) if val is not None else default
        except (TypeError, ValueError): return default

    def _apply_settings_state(self, settings: Any) -> None:
        self._current_doc.settings = copy(settings)
        self._current_doc.settings.margins = self._current_doc.settings.margins.copy()
        self._sync_ribbon_from_doc()
        self.doc_editor.on_settings_changed_external()
        self._doc_dirty = True
        self.setWindowModified(True)

    def _setup_ui(self) -> None:
        self.doc_editor = DocumentEditorWidget(self._current_doc)
        self.doc_editor.text_changed.connect(self._on_text_changed)
        self.doc_editor.settings_changed.connect(self._on_settings_changed)
        self.doc_editor.open_font_requested.connect(self._open_font)
        self.doc_editor.create_font_requested.connect(self._show_font_editor)
        self.doc_editor.warnings_changed.connect(self._on_warnings_changed)
        self.setCentralWidget(self.doc_editor)

        self.font_editor_window = FontEditorWindow()
        self.font_editor_window.font_saved.connect(self._on_font_saved_from_editor)

        self.setStyleSheet(self._get_stylesheet())

    def _setup_ribbon(self) -> None:
        self.menuBar().hide()
        self.ribbon = QTabWidget()
        self.ribbon.setFixedHeight(132)
        self.ribbon.setObjectName("ribbonTabWidget")
        home_tab = self._create_home_tab()
        self.ribbon.addTab(home_tab, self.tr("Home"))
        font_tab = self._create_font_tab()
        self.ribbon.addTab(font_tab, self.tr("Font"))
        paper_tab = self._create_paper_tab()
        self.ribbon.addTab(paper_tab, self.tr("Paper"))
        export_tab = self._create_export_tab()
        self.ribbon.addTab(export_tab, self.tr("Export"))

        self._cell_widgets_map = [
            (self.paper_w_spin, "paper_width", False, 10, 600),
            (self.paper_h_spin, "paper_height", False, 10, 600),
            (self.margin_top_spin, "top", True, 0, 100),
            (self.margin_top_first_spin, "top_first", True, 0, 100),
            (self.margin_bottom_spin, "bottom", True, 0, 100),
            (self.margin_left_spin, "left", True, 0, 100),
            (self.margin_right_spin, "right", True, 0, 100),
        ]

        central = self.centralWidget()
        self.takeCentralWidget()

        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)
        wrapper_layout.addWidget(self.ribbon)
        wrapper_layout.addWidget(central, 1)
        self.setCentralWidget(wrapper)

    def _create_home_tab(self) -> QWidget:
        tab = QWidget()
        main_layout = QHBoxLayout(tab)
        main_layout.setContentsMargins(4, 2, 4, 2)
        main_layout.setSpacing(0)
        self.btn_new = RibbonBuilder.make_button('mdi6.file-plus-outline', (self.tr("New") + " " + self.tr("Document").lower()).replace(" ", "\n"))
        self.btn_new.clicked.connect(self._new_document)
        self.btn_open = RibbonBuilder.make_button('mdi6.folder-open-outline', self.tr("Open"))
        self.btn_open.clicked.connect(self._open_document)
        self.btn_save = RibbonBuilder.make_button('mdi6.content-save-outline', self.tr("Save"))
        self.btn_save.clicked.connect(self._save_document)
        self.btn_save_as = RibbonBuilder.make_button('mdi6.content-save-edit-outline', (self.tr('Save') + " " + self.tr('As').lower()).replace(" ", "\n"))
        self.btn_save_as.clicked.connect(self._save_document_as)

        RibbonBuilder.add_group(main_layout, self.tr("File"), [self.btn_new, self.btn_open, self.btn_save, self.btn_save_as])

        self.btn_undo = RibbonBuilder.make_button('mdi6.undo', self.tr("Undo"))
        self.btn_undo.clicked.connect(self._smart_undo)
        self.btn_redo = RibbonBuilder.make_button('mdi6.redo', self.tr("Redo"))
        self.btn_redo.clicked.connect(self._smart_redo)

        self.undo_stack.canUndoChanged.connect(self._update_undo_redo_buttons)
        self.undo_stack.canRedoChanged.connect(self._update_undo_redo_buttons)
        self.doc_editor.text_edit.document().undoAvailable.connect(self._update_undo_redo_buttons)
        self.doc_editor.text_edit.document().redoAvailable.connect(self._update_undo_redo_buttons)
        self._update_undo_redo_buttons()

        RibbonBuilder.add_group(main_layout, self.tr("History"), [self.btn_undo, self.btn_redo])

        self.btn_cut = RibbonBuilder.make_button('mdi6.content-cut', self.tr("Cut"))
        self.btn_cut.clicked.connect(self.doc_editor.text_edit.cut)
        self.btn_copy = RibbonBuilder.make_button('mdi6.content-copy', self.tr("Copy"))
        self.btn_copy.clicked.connect(self.doc_editor.text_edit.copy)
        self.btn_paste = RibbonBuilder.make_button('mdi6.content-paste', self.tr("Paste"))
        self.btn_paste.clicked.connect(self.doc_editor.text_edit.paste)

        RibbonBuilder.add_group(main_layout, self.tr("Clipboard"), [self.btn_cut, self.btn_copy, self.btn_paste])

        self.btn_open_font = RibbonBuilder.make_button('mdi6.format-font', (self.tr("Open") + " " + self.tr("Font").lower()).replace(" ", "\n"))
        self.btn_open_font.clicked.connect(self._open_font)

        RibbonBuilder.add_group(main_layout, self.tr("Font"), [self.btn_open_font], separator=False)

        main_layout.addStretch()

        self.font_label = QLabel("")
        self.font_label.setObjectName("fontLabel")
        self.font_label.setProperty("fontLoaded", False)
        main_layout.addWidget(self.font_label)

        return tab

    def _create_font_tab(self) -> QWidget:
        tab = QWidget()
        main_layout = QHBoxLayout(tab)
        main_layout.setContentsMargins(4, 2, 4, 2)
        main_layout.setSpacing(0)

        btn_open_font = RibbonBuilder.make_button('mdi6.format-font', (self.tr("Open") + " " + self.tr("Font").lower()).replace(" ", "\n"))
        btn_open_font.clicked.connect(self._open_font)
        btn_font_editor = RibbonBuilder.make_button('mdi6.fountain-pen-tip', self.tr("Font Editor").replace(" ", "\n"))
        btn_font_editor.clicked.connect(self._show_font_editor)
        self.btn_close_font = RibbonBuilder.make_button('mdi6.close', (self.tr("Close") + " " + self.tr("Font").lower()).replace(" ", "\n"))
        self.btn_close_font.clicked.connect(self._close_font)

        RibbonBuilder.add_group(main_layout, self.tr("Font"), [btn_open_font, btn_font_editor, self.btn_close_font])

        self.size_spin_widget = LabeledSpinBox(self.tr("Font Size")).setup(
            0.10, 3.00, 0.01, decimals=2, value=self._current_doc.settings.letter_size,
            slot=self._on_ribbon_settings_changed
        )

        self.spacing_spin_widget = LabeledSpinBox(self.tr("Spacing")).setup(
            3, 30, 1, suffix=" " + self.tr("mm"), value=self._current_doc.settings.line_spacing,
            slot=self._on_ribbon_settings_changed
        )

        RibbonBuilder.add_group(main_layout, self.tr("Size"), [self.size_spin_widget, self.spacing_spin_widget], spacing=6)

        self.btn_align_left = RibbonBuilder.make_button('mdi6.format-align-left', self.tr("Align left").replace(" ", "\n"))
        self.btn_align_left.clicked.connect(self.doc_editor.align_left)
        self.btn_align_center = RibbonBuilder.make_button('mdi6.format-align-center', self.tr("Align center").replace(" ", "\n"))
        self.btn_align_center.clicked.connect(self.doc_editor.align_center)
        self.btn_align_right = RibbonBuilder.make_button('mdi6.format-align-right', self.tr("Align right").replace(" ", "\n"))
        self.btn_align_right.clicked.connect(self.doc_editor.align_right)

        RibbonBuilder.add_group(main_layout, self.tr("Alignment"), [self.btn_align_left, self.btn_align_center, self.btn_align_right], separator=False)

        main_layout.addStretch()

        return tab

    def _create_paper_tab(self) -> QWidget:
        tab = QWidget()
        main_layout = QHBoxLayout(tab)
        main_layout.setContentsMargins(4, 2, 4, 2)
        main_layout.setSpacing(0)
        self.btn_load_template = RibbonBuilder.make_button('mdi6.folder-open-outline', (self.tr("Load") + " " + self.tr("Preset").lower()).replace(" ", "\n"))
        self.btn_load_template.clicked.connect(self._load_template)
        self.btn_save_template = RibbonBuilder.make_button('mdi6.content-save-outline', (self.tr("Save") + " " + self.tr("Preset").lower()).replace(" ", "\n"))
        self.btn_save_template.clicked.connect(self._save_template)

        RibbonBuilder.add_group(main_layout, self.tr("Preset"), [self.btn_load_template, self.btn_save_template])

        mm_suffix = " " + self.tr("mm")
        self.paper_w_spin = LabeledSpinBox(self.tr("Width")).setup(
            10, 600, 1, suffix=mm_suffix, value=self._current_doc.settings.paper_width,
            slot=self._on_ribbon_settings_changed
        )
        self.paper_h_spin = LabeledSpinBox(self.tr("Height")).setup(
            10, 600, 1, suffix=mm_suffix, value=self._current_doc.settings.paper_height,
            slot=self._on_ribbon_settings_changed
        )

        RibbonBuilder.add_group(main_layout, self.tr("Paper size"), [self.paper_w_spin, self.paper_h_spin], spacing=6)

        self.margin_top_spin = LabeledSpinBox(self.tr("Top")).setup(
            0, 100, 1, suffix=mm_suffix, value=self._current_doc.settings.margins["top"],
            slot=self._on_ribbon_settings_changed
        )
        self.margin_top_first_spin = LabeledSpinBox(self.tr("First Top")).setup(
            0, 100, 1, suffix=mm_suffix, value=self._current_doc.settings.margins.get("top_first", 0.0),
            slot=self._on_ribbon_settings_changed
        )
        self.margin_bottom_spin = LabeledSpinBox(self.tr("Bottom")).setup(
            0, 100, 1, suffix=mm_suffix, value=self._current_doc.settings.margins["bottom"],
            slot=self._on_ribbon_settings_changed
        )
        self.margin_left_spin = LabeledSpinBox(self.tr("Left")).setup(
            0, 100, 1, suffix=mm_suffix, value=self._current_doc.settings.margins["left"],
            slot=self._on_ribbon_settings_changed
        )
        self.margin_right_spin = LabeledSpinBox(self.tr("Right")).setup(
            0, 100, 1, suffix=mm_suffix, value=self._current_doc.settings.margins["right"],
            slot=self._on_ribbon_settings_changed
        )

        self.btn_cells_mode = RibbonBuilder.make_button('mdi6.view-grid-outline', self.tr("In cells"))
        self.btn_cells_mode.setCheckable(True)
        self.btn_cells_mode.setChecked(False)
        self.btn_cells_mode.clicked.connect(self._toggle_cells_mode)

        margins_widgets = [
            self.margin_top_spin, self.margin_top_first_spin,
            self.margin_bottom_spin, self.margin_left_spin,
            self.margin_right_spin, self.btn_cells_mode
        ]
        RibbonBuilder.add_group(main_layout, self.tr("Margins"), margins_widgets, spacing=6)

        self.btn_toggle_grid = RibbonBuilder.make_button('mdi6.grid', self.tr("Toggle grid").replace(" ", "\n"))
        self.btn_toggle_grid.setCheckable(True)
        self.btn_toggle_grid.setChecked(self._current_doc.settings.show_grid)
        self.btn_toggle_grid.clicked.connect(self._toggle_grid)

        RibbonBuilder.add_group(main_layout, self.tr("Preview"), [self.btn_toggle_grid], separator=False)

        main_layout.addStretch()

        return tab

    def _create_export_tab(self) -> QWidget:
        tab = QWidget()
        main_layout = QHBoxLayout(tab)
        main_layout.setContentsMargins(4, 2, 4, 2)
        main_layout.setSpacing(0)

        self.btn_export_svg = RibbonBuilder.make_button('mdi6.export', self.tr("Export to SVG").replace(" to ", "\n"))
        self.btn_export_svg.clicked.connect(self._export_svg)
        self.btn_export_gcode = RibbonBuilder.make_button('mdi6.cog-outline', self.tr("Export to G-code").replace(" to ", "\n"))
        self.btn_export_gcode.clicked.connect(self._export_gcode)

        RibbonBuilder.add_group(main_layout, self.tr("Export"), [self.btn_export_svg, self.btn_export_gcode], separator=False)

        main_layout.addStretch()

        return tab

    def _setup_statusbar(self) -> None:
        self.status = QStatusBar()
        self.status.setFixedHeight(32)
        self.setStatusBar(self.status)

        self.warning_icon_label = QLabel()
        self.status.addWidget(self.warning_icon_label)

        self.warning_label = QLabel("")
        self.status.addWidget(self.warning_label)

    def _toggle_cells_mode(self, checked: bool) -> None:
        self._cells_mode = checked
        s = self._current_doc.settings

        for widget, attr, is_margin, base_min, base_max in self._cell_widgets_map:
            current_mm = s.margins.get(attr, 0.0) if is_margin else getattr(s, attr)

            with QSignalBlocker(widget.spin):
                if self._cells_mode:
                    widget.spin.setRange(base_min / 5.0, base_max / 5.0)
                    widget.spin.setSuffix(" " + self.tr("cl"))
                    widget.spin.setDecimals(0)
                    widget.spin.setSingleStep(1.0)
                    val = round(current_mm / 5.0)
                    if widget.spin.value() != val:
                        widget.spin.setValue(val)
                else:
                    widget.spin.setRange(base_min, base_max)
                    widget.spin.setSuffix(" " + self.tr("mm"))
                    widget.spin.setDecimals(0)
                    widget.spin.setSingleStep(1)
                    val = round(current_mm)
                    if widget.spin.value() != val:
                        widget.spin.setValue(val)

    def _on_ribbon_settings_changed(self) -> None:
        old_settings = copy(self._current_doc.settings)
        old_settings.margins = old_settings.margins.copy()

        new_settings = copy(self._current_doc.settings)
        new_settings.margins = new_settings.margins.copy()

        cell = 5.0 if self._cells_mode else 1.0
        new_settings.letter_size = self.size_spin_widget.spin.value()
        new_settings.line_spacing = self.spacing_spin_widget.spin.value()

        for widget, attr, is_margin, _, _ in self._cell_widgets_map:
            val = widget.spin.value() * cell
            if is_margin:
                new_settings.margins[attr] = val
            else:
                setattr(new_settings, attr, val)

        new_settings.show_grid = self.btn_toggle_grid.isChecked()

        cmd = SettingsCommand(self, old_settings, new_settings)
        self.undo_stack.push(cmd)
        self._save_settings()

    def _sync_ribbon_from_doc(self) -> None:
        s = self._current_doc.settings
        cell = 5.0 if self._cells_mode else 1.0

        sync_list = [
            (self.size_spin_widget.spin, s.letter_size),
            (self.spacing_spin_widget.spin, s.line_spacing),
        ]

        for widget, attr, is_margin, _, _ in self._cell_widgets_map:
            val = s.margins.get(attr, 0.0) if is_margin else getattr(s, attr)
            sync_list.append((widget.spin, val / cell))

        for widget, val in sync_list:
            with QSignalBlocker(widget):
                if widget.value() != val:
                    widget.setValue(val)

        with QSignalBlocker(self.btn_toggle_grid):
            if self.btn_toggle_grid.isChecked() != s.show_grid:
                self.btn_toggle_grid.setChecked(s.show_grid)

    def _check_saved(self) -> bool:
        if self._doc_dirty:
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
                self._save_document()
                return not self._doc_dirty
            elif reply == btn_cancel:
                return False
        return True

    def _update_undo_redo_buttons(self) -> None:
        can_undo = self.doc_editor.text_edit.document().isUndoAvailable() or self.undo_stack.canUndo()
        can_redo = self.doc_editor.text_edit.document().isRedoAvailable() or self.undo_stack.canRedo()
        self.btn_undo.setEnabled(can_undo)
        self.btn_redo.setEnabled(can_redo)

    def _smart_undo(self) -> None:
        if self.doc_editor.text_edit.document().isUndoAvailable():
            self.doc_editor.text_edit.undo()
        else:
            self.undo_stack.undo()

    def _smart_redo(self) -> None:
        if self.doc_editor.text_edit.document().isRedoAvailable():
            self.doc_editor.text_edit.redo()
        else:
            self.undo_stack.redo()

    def _on_text_changed(self) -> None:
        if not self._doc_dirty:
            self._doc_dirty = True
            self.setWindowModified(True)
        self.save_timer.start()

    def _on_settings_changed(self) -> None:
        if not self._doc_dirty:
            self._doc_dirty = True
            self.setWindowModified(True)
        self.save_timer.start()

    def _on_warnings_changed(self, msg: str) -> None:
        if msg:
            self.warning_label.setText(msg)
            self.warning_icon_label.setPixmap(icon('mdi6.alert-outline', color=COL_RED).pixmap(18, 18))
        else:
            self.warning_label.clear()
            self.warning_icon_label.clear()

    def _save_settings(self) -> None:
        self.doc_editor.sync_to_document()
        self.settings.setValue("geometry", self.saveGeometry())

        s = self._current_doc.settings
        for key in ["paper_width", "paper_height", "letter_size", "line_spacing", "show_grid"]:
            self.settings.setValue(key, getattr(s, key))

        for key in ["top", "bottom", "left", "right"]:
            self.settings.setValue(f"margin_{key}", s.margins[key])
        self.settings.setValue("last_text", self._current_doc.text)

        if self._current_doc.path:
            self.settings.setValue("last_doc_path", str(self._current_doc.path))
        else:
            self.settings.setValue("last_doc_path", "")

        if self._current_font and self._current_font.path:
            self.settings.setValue("last_font_path", str(self._current_font.path))
        else:
            self.settings.setValue("last_font_path", "")

        gp = self._current_doc.gcode_params
        self.settings.setValue("gcode_feed", gp.feed)
        self.settings.setValue("gcode_passing_feed", gp.passing_feed)
        self.settings.setValue("gcode_penetration_feed", gp.penetration_feed)
        self.settings.setValue("gcode_z_up", gp.z_up)
        self.settings.setValue("gcode_z_down", gp.z_down)

    def _new_document(self) -> None:
        if not self._check_saved():
            return
        self._current_doc = HWDoc()
        self._doc_dirty = False
        self.doc_editor.set_document(self._current_doc)
        self._sync_ribbon_from_doc()
        self._doc_dirty = False
        self.status.showMessage(self.tr("New document created"), 4000)

    def _load_document_from_path(self, path: str) -> None:
        try:
            self._current_doc = HWDoc.load(path)
            self.doc_editor.set_document(self._current_doc)
            self._sync_ribbon_from_doc()
            if self._current_doc.font_path:
                font_path = Path(path).parent / self._current_doc.font_path
                if font_path.exists():
                    self._load_font(str(font_path))
            self._doc_dirty = False
            self._update_window_title()
            self.status.showMessage(self.tr("Opened: {}").format(path), 4000)
        except Exception as e:
            QMessageBox.critical(self, self.tr("Error"), self.tr('Failed to') + " " + self.tr('Open').lower() + ": " + self.tr('Document').lower() + f"\n{e}")

    def _open_document(self) -> None:
        if not self._check_saved():
            return
        path, _ = QFileDialog.getOpenFileName(
            None, self.tr("Open") + " " + self.tr("Document").lower(), "",
            self.tr("Handwriter Documents (*.hwdoc);;All Files (*)")
        )
        if not path:
            return
        self._load_document_from_path(path)

    def _save_document(self) -> None:
        if self._current_doc.path:
            self._do_save(str(self._current_doc.path))
        else:
            self._save_document_as()

    def _save_document_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            None, self.tr("Save") + " " + self.tr("Document").lower(), "document.hwdoc",
            self.tr("Handwriter Documents (*.hwdoc);;All Files (*)")
        )
        if path:
            self._do_save(path)

    def _do_save(self, path: str) -> None:
        try:
            self.doc_editor.sync_to_document()
            self._current_doc.save(path)
            self._doc_dirty = False
            self._update_window_title()
            self.status.showMessage(self.tr("Saved: {}").format(path), 4000)
        except Exception as e:
            QMessageBox.critical(self, self.tr("Error"), self.tr('Failed to') + " " + self.tr('Save').lower() + f":\n{e}")

    def _open_font(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None, self.tr("Open") + " " + self.tr("Font").lower(), "",
            self.tr("Handwriter Fonts (*.hfont);;All Files (*)")
        )
        if path:
            self._load_font(path)

    def _load_font(self, path: str) -> None:
        try:
            self._current_font = HFont.load(path)
            self.doc_editor.set_font(self._current_font)
            self.font_editor_window.set_font(self._current_font)
            self._current_doc.font_path = basename(path)
            self._update_window_title()
            self._update_font_status_ui(True, self.tr("Opened font:\n{}\n{} characters").format(
                self._current_font.name, self._current_font.char_count
            ))
            self.status.showMessage(
                self.tr("Font loaded: {} ({} characters)").format(
                    self._current_font.name,
                    self._current_font.char_count
                ), 4000
            )
            self._save_settings()
        except Exception as e:
            QMessageBox.critical(self, self.tr("Error"), self.tr('Failed to') + " " + self.tr('Load').lower() + ": " + self.tr('Font').lower() + f"\n{e}")

    def _update_font_status_ui(self, font_loaded: bool, text: str = "") -> None:
        self.font_label.setText(text)
        self.font_label.setProperty("fontLoaded", font_loaded)
        self.font_label.style().unpolish(self.font_label)
        self.font_label.style().polish(self.font_label)

    def _close_font(self) -> None:
        self._current_font = None
        self.doc_editor.set_font(None)
        self.font_editor_window.set_font(None)
        self._current_doc.font_path = ""
        self._update_window_title()
        self._update_font_status_ui(False)
        self.status.showMessage(self.tr("No font loaded"), 4000)
        self._save_settings()

    def _on_font_saved_from_editor(self, font: HFont) -> None:
        if font.path:
            self._load_font(str(font.path))

    def _show_font_editor(self) -> None:
        self.font_editor_window.show()
        self.font_editor_window.raise_()
        self.font_editor_window.activateWindow()

    def _load_template(self) -> None:
        templates_dir = str(self.template_manager.get_templates_dir())
        path, _ = QFileDialog.getOpenFileName(
            None, self.tr("Load") + " " + self.tr("Preset").lower(), templates_dir,
            self.tr("Paper Presets (*.hwpap);;All Files (*)")
        )
        if not path:
            return
        try:
            tmpl = PaperTemplate.load(path)

            old_settings = copy(self._current_doc.settings)
            old_settings.margins = old_settings.margins.copy()

            new_settings = copy(self._current_doc.settings)
            new_settings.margins = new_settings.margins.copy()

            new_settings.paper_width = tmpl.paper_width
            new_settings.paper_height = tmpl.paper_height
            new_settings.margins = {
                "top": tmpl.margin_top,
                "bottom": tmpl.margin_bottom,
                "left": tmpl.margin_left,
                "right": tmpl.margin_right,
                "top_first": tmpl.margin_top_first
            }

            cmd = SettingsCommand(self, old_settings, new_settings)
            self.undo_stack.push(cmd)

            self.status.showMessage(self.tr("Preset loaded: {}").format(tmpl.name), 4000)
            self._save_settings()
        except Exception as e:
            QMessageBox.critical(self, self.tr("Error"), self.tr('Failed to') + " " + self.tr('Load').lower() + ": " + self.tr('Preset').lower() + f"\n{e}")

    def _save_template(self) -> None:
        templates_dir = str(self.template_manager.get_templates_dir())
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Save") + " " + self.tr("Preset").lower(), templates_dir,
            self.tr("Paper Presets (*.hwpap);;All Files (*)")
        )
        if not path:
            return

        tmpl = PaperTemplate(
            name=Path(path).stem,
            paper_width=self._current_doc.settings.paper_width,
            paper_height=self._current_doc.settings.paper_height,
            margin_top=self._current_doc.settings.margins["top"],
            margin_bottom=self._current_doc.settings.margins["bottom"],
            margin_left=self._current_doc.settings.margins["left"],
            margin_right=self._current_doc.settings.margins["right"],
        )
        tmpl.save(path)
        self.status.showMessage(self.tr("Preset saved: {}").format(path), 4000)

    def _export_svg(self) -> None:
        if not self._current_font:
            QMessageBox.warning(self, self.tr("No font"), self.tr("Load a font first."))
            return
        dlg = ExportDialog(self, mode="svg", doc=self._current_doc)
        if dlg.exec():
            self.doc_editor.export_svg(dlg.output_path)
            self.status.showMessage(self.tr("SVG exported to: {}").format(dlg.output_path), 4000)

    def _export_gcode(self) -> None:
        if not self._current_font:
            QMessageBox.warning(self, self.tr("No font"), self.tr("Load a font first."))
            return
        dlg = ExportDialog(self, mode="gcode", doc=self._current_doc)
        if dlg.exec():
            self._save_settings()
            self.doc_editor.export_gcode(dlg.output_path, self._current_doc.gcode_params)
            self.status.showMessage(self.tr("G-code exported to: {}").format(dlg.output_path), 4000)

    def _toggle_grid(self, checked: bool) -> None:
        self._on_ribbon_settings_changed()

    def open_file_arg(self, filepath: str) -> None:
        if filepath.endswith(".hfont"):
            self._load_font(filepath)
            self._show_font_editor()
        elif filepath.endswith(".hwdoc"):
            self._load_document_from_path(filepath)

    def _update_window_title(self) -> None:
        doc_name = self._current_doc.path.stem if self._current_doc and self._current_doc.path else ""
        font_name = self._current_font.name if self._current_font else ""

        if doc_name:
            if font_name:
                self.setWindowTitle(f"{doc_name} | {font_name} — Handwriter[*]")
            else:
                self.setWindowTitle(f"{doc_name} — Handwriter[*]")
        else:
            self.setWindowTitle("Handwriter[*]")

        self.setWindowModified(self._doc_dirty)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._check_saved():
            event.ignore()
            return

        if not self.font_editor_window.close():
            event.ignore()
            return

        self._save_settings()

        super().closeEvent(event)

    @staticmethod
    def _get_stylesheet() -> str:
        import handwriter.resources_rc
        _ = handwriter.resources_rc
        from PySide6.QtCore import QFile, QTextStream
        file = QFile(":/handwriter/views/main_window.qss")
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
        return qss_template