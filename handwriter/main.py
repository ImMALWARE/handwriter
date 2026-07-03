import sys
from os import environ
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import QTranslator, QLocale, QLibraryInfo

from handwriter.views.main_window import MainWindow

if sys.platform.startswith("linux"):
    environ.setdefault("QT_QPA_PLATFORMTHEME", "xdgdesktopportal")

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setApplicationName("Handwriter")
app.setOrganizationName("malw.link")
app.setApplicationVersion("1.0")

if sys.platform != "darwin":
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        icon_dir = str(Path(sys._MEIPASS) / "img")
    elif "__compiled__" in globals():
        icon_dir = str(Path(sys.executable).parent / "img")
    else:
        icon_dir = str(Path(__file__).parent.parent / "img")
    app.setWindowIcon(QIcon(str(Path(icon_dir) / "handwriter.png")))

translator = QTranslator()

locale = QLocale.system().name()
if sys.platform == "darwin":
    from subprocess import run
    result = run(["defaults", "read", ".GlobalPreferences", "AppleLanguages"], capture_output=True, text=True)
    for line in result.stdout.split('\n'):
        line = line.strip().strip('"').strip('",')
        if line and line not in ('(', ')'):
            locale = line.replace("-", "_")
            break

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    translations_dir = str(Path(sys._MEIPASS) / "handwriter" / "translations")
elif "__compiled__" in globals():
    translations_dir = str(Path(sys.executable).parent / "translations")
else:
    translations_dir = str(Path(__file__).parent / "translations")

qt_translator = QTranslator()
qt_translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
if not qt_translator.load("qt_" + locale, qt_translations_path):
    qt_translator.load("qt_" + locale.split('_')[0], qt_translations_path)
app.installTranslator(qt_translator)

if not translator.load(locale, translations_dir):
    translator.load(locale.split('_')[0], translations_dir)
app.installTranslator(translator)

window = MainWindow()

if len(sys.argv) > 1:
    filepath = sys.argv[1]
    if Path(filepath).is_file():
        window.open_file_arg(filepath)

window.show()
sys.exit(app.exec())