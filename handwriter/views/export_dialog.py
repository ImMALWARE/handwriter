from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QGroupBox, QFileDialog, QFormLayout,
    QMessageBox, QWidget
)

from handwriter.models.hwdoc import HWDoc, GCodeParams
from handwriter.views.theme import (
    COL_BASE, COL_TEXT, COL_SURFACE0, COL_SURFACE1, COL_SURFACE2,
    COL_BLUE, COL_BLUE_TEXT, COL_BLUE_HOVER
)

_QSS_TEMPLATE: str | None = None


class ExportDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, mode: str = "svg", doc: HWDoc | None = None):
        super().__init__(parent)
        self.mode = mode
        self._doc = doc or HWDoc()
        self.output_path = ""
        self.setWindowTitle(self.tr("Export to SVG") if mode == "svg" else self.tr("Export to G-code"))
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self) -> None:
        global _QSS_TEMPLATE

        layout = QVBoxLayout(self)

        if _QSS_TEMPLATE is None:
            import handwriter.resources_rc
            _ = handwriter.resources_rc
            from PySide6.QtCore import QFile, QTextStream
            file = QFile(":/handwriter/views/export_dialog.qss")
            if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
                _QSS_TEMPLATE = QTextStream(file).readAll()
                file.close()
            else:
                _QSS_TEMPLATE = ""

        self.setStyleSheet(
            _QSS_TEMPLATE
            .replace("{COL_BASE}", COL_BASE)
            .replace("{COL_TEXT}", COL_TEXT)
            .replace("{COL_SURFACE0}", COL_SURFACE0)
            .replace("{COL_SURFACE1}", COL_SURFACE1)
            .replace("{COL_SURFACE2}", COL_SURFACE2)
            .replace("{COL_BLUE}", COL_BLUE)
            .replace("{COL_BLUE_TEXT}", COL_BLUE_TEXT)
            .replace("{COL_BLUE_HOVER}", COL_BLUE_HOVER)
        )

        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel(self.tr("Output directory:")))
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText(self.tr("Select output directory..."))
        dir_layout.addWidget(self.dir_input)
        browse_btn = QPushButton(self.tr("Browse"))
        browse_btn.setObjectName("BrowseButton")
        browse_btn.clicked.connect(self._browse)
        dir_layout.addWidget(browse_btn)
        layout.addLayout(dir_layout)

        if self.mode == "gcode":
            gcode_group = QGroupBox(self.tr("G-code Parameters"))
            form = QFormLayout(gcode_group)

            params = self._doc.gcode_params

            self.feed_spin = QSpinBox()
            self.feed_spin.setRange(100, 20000)
            self.feed_spin.setValue(params.feed)
            self.feed_spin.setSuffix(" " + self.tr("mm/min"))
            form.addRow(self.tr("Feed:"), self.feed_spin)

            self.travel_spin = QSpinBox()
            self.travel_spin.setRange(100, 20000)
            self.travel_spin.setValue(params.passing_feed)
            self.travel_spin.setSuffix(" " + self.tr("mm/min"))
            form.addRow(self.tr("Passing Feed:"), self.travel_spin)

            self.plunge_spin = QSpinBox()
            self.plunge_spin.setRange(100, 10000)
            self.plunge_spin.setValue(params.penetration_feed)
            self.plunge_spin.setSuffix(" " + self.tr("mm/min"))
            form.addRow(self.tr("Penetration Feed:"), self.plunge_spin)

            self.z_up_spin = QSpinBox()
            self.z_up_spin.setRange(-10, 50)
            self.z_up_spin.setValue(params.z_up)
            self.z_up_spin.setSuffix(" " + self.tr("mm"))
            form.addRow(self.tr("Z-Up (Travel):"), self.z_up_spin)

            self.z_down_spin = QSpinBox()
            self.z_down_spin.setRange(-20, 10)
            self.z_down_spin.setValue(params.z_down)
            self.z_down_spin.setSuffix(" " + self.tr("mm"))
            form.addRow(self.tr("Z-Down (Draw):"), self.z_down_spin)

            layout.addWidget(gcode_group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(self.tr("Cancel"))
        cancel_btn.setObjectName("CancelButton")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.export_btn = QPushButton(self.tr("Export"))
        self.export_btn.setObjectName("ExportButton")
        self.export_btn.clicked.connect(self._do_export)
        self.export_btn.setEnabled(False)
        self.dir_input.textChanged.connect(lambda text: self.export_btn.setEnabled(bool(text.strip())))
        btn_layout.addWidget(self.export_btn)

        layout.addStretch()
        layout.addLayout(btn_layout)

    def _browse(self) -> None:
        start_dir = self.dir_input.text().strip() or str(Path.home())
        d = QFileDialog.getExistingDirectory(self, self.tr("Select Output Directory"), start_dir)
        if d:
            self.dir_input.setText(d)

    def _do_export(self) -> None:
        self.output_path = self.dir_input.text().strip()
        if not self.output_path:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Please select an output directory."))
            return

        path = Path(self.output_path)
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, self.tr("Error"), self.tr(f"Could not create directory:\n{e}"))
                return
        elif not path.is_dir():
            QMessageBox.critical(self, self.tr("Error"), self.tr("The specified path is not a directory."))
            return

        if self.mode == "gcode":
            self._doc.gcode_params = GCodeParams(
                feed=self.feed_spin.value(),
                passing_feed=self.travel_spin.value(),
                penetration_feed=self.plunge_spin.value(),
                z_up=self.z_up_spin.value(),
                z_down=self.z_down_spin.value(),
            )

        self.accept()