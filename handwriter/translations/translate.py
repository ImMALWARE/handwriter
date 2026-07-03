translations = {
    'Add variant': 'Добавить вариант',
    'Align center': 'По центру',
    'Align left': 'По левому краю',
    'Align right': 'По правому краю',
    'Alignment': 'Выравнивание',
    'As': 'Как',
    'Bottom': 'Нижнее',
    'Browse': 'Обзор',
    'Cancel': 'Отмена',
    'Characters': 'Символы',
    'Clear': 'Очистить',
    'Clipboard': 'Буфер обмена',
    'Close': 'Закрыть',
    'Connection points': 'Точки соединения',
    'Copy': 'Копировать',
    'Cut': 'Вырезать',
    'Delete': 'Удалить',
    'Yes': 'Да',
    'No': 'Нет',
    'Delete variant': 'Удалить вариант',
    'Document': 'Документ',
    'End: {}': 'Конец: {}',
    'Enter or paste text': 'Введите или вставьте текст',
    'Error': 'Ошибка',
    'Export': 'Экспорт',
    'Export to G-code': 'Экспорт в G-code',
    'Export to SVG': 'Экспорт в SVG',
    'Failed to': 'Не удалось',
    'Feed:': 'Рабочая подача:',
    'File': 'Файл',
    'First Top': 'Перв. верхнее',
    'Fit': 'Вместить',
    'Font Editor': 'Редактор шрифтов',
    'Handwriter Font Editor': 'Редактор шрифтов Handwriter',
    'Font Size': 'Размер шрифта',
    'Font': 'Шрифт',
    'Font loaded: {} ({} characters)': 'Шрифт загружен: {} ({} символов)',
    'G-code exported to: {}': 'G-code экспортирован в: {}',
    'G-code Parameters': 'Параметры G-code',
    'Handwriter Documents (*.hwdoc);;All Files (*)': 'Документы Handwriter (*.hwdoc);;Все файлы (*)',
    'Handwriter Fonts (*.hfont);;All Files (*)': 'Шрифты Handwriter (*.hfont);;Все файлы (*)',
    'Handwriter Fonts (*.hfont)': 'Шрифты Handwriter (*.hfont)',
    'Height': 'Высота',
    'History': 'История',
    'Home': 'Главная',
    'In cells': 'В клетках',
    'Invalid bbcode tags on line {}': 'Некорректные bbcode-теги в строке {}',
    'Left': 'Левое',
    'Load a font first.': 'Сначала загрузите шрифт.',
    'Load': 'Загрузить',
    'Margins': 'Поля',
    'Missing characters: {}': 'Отсутствующие символы: {}',
    'New document created': 'Создан новый документ',
    'New font': 'Новый шрифт',
    'New': 'Создать',
    'No font loaded': 'Шрифт не загружен',
    'No font': 'Нет шрифта',
    'Open': 'Открыть',
    'Opened font:\n{}\n{} characters': 'Открытый шрифт:\n{}\n{} символов',
    'Opened: {}': 'Открыт: {}',
    'Output directory:': 'Каталог вывода:',
    'Paper Presets (*.hwpap);;All Files (*)': 'Шаблоны бумаги (*.hwpap);;Все файлы (*)',
    'Paper size': 'Размер бумаги',
    'Paper': 'Бумага',
    'Passing Feed:': 'Скорость перемещения:',
    'Paste': 'Вставить',
    'Penetration Feed:': 'Скорость опускания:',
    'Preset loaded: {}': 'Шаблон загружен: {}',
    'Preset saved: {}': 'Шаблон сохранён: {}',
    'Preset': 'Шаблон',
    'Preview': 'Превью',
    'Redo': 'Повторить',
    'Right': 'Правое',
    'Save': 'Сохранить',
    'Saved: {}': 'Сохранено: {}',
    'Search': 'Поиск',
    'Select a font to get started': 'Для начала работы выберите шрифт',
    'Select or create a character': 'Выберите или создайте символ',
    'Select output directory...': 'Выберите каталог вывода...',
    'Select Output Directory': 'Выберите каталог вывода',
    'Set start point': 'Установить точку начала',
    'Set end point': 'Установить точку конца',
    'Size': 'Размер',
    'Spacing': 'Интервал',
    'Start: {}': 'Начало: {}',
    'SVG exported to: {}': 'SVG экспортирован в: {}',
    'Toggle grid': 'Показать клетки',
    'Top': 'Верхнее',
    'Undo': 'Отменить',
    'Unsaved changes': 'Несохранённые изменения',
    'Width': 'Ширина',
    'You have unsaved changes. Do you want to save them?': 'У вас есть несохранённые изменения. Сохранить?',
    'Z-Down (Draw):': 'Z-Down (Рисование):',
    'Z-Up (Travel):': 'Z-Up (Перемещение):',
    'Character "{}" already exists.': 'Символ "{}" уже существует.',
    '(right-click to add)': '(правый клик для добавления)',
    'Zoom in': 'Увеличить',
    'Zoom out': 'Уменьшить',
    'font': 'шрифт',
    'cl': 'кл',
    'mm': 'мм',
    'mm/min': 'мм/мин',
    'Could not create directory:\n{e}': 'Не удалось создать каталог:\n{e}',
    'Layout error: {}': 'Ошибка макета: {}',
    'Please select an output directory.': 'Пожалуйста, выберите каталог вывода.',
    'The specified path is not a directory.': 'Указанный путь не является каталогом.',
    'Warning': 'Внимание'
}

if __name__ == "__main__":
    import sys
    import os
    from pathlib import Path
    from subprocess import run, CalledProcessError
    from xml.etree import ElementTree as ET

    cur_dir = Path(__file__).resolve().parent
    src_dir = cur_dir.parent
    project_root = src_dir.parent

    paths = [str(Path(sys.executable).parent)]
    for venv_dir in [project_root / ".venv" / "bin", project_root / ".venv" / "Scripts"]:
        if venv_dir.is_dir():
            paths.append(str(venv_dir))

    os.environ["PATH"] = f"{os.pathsep.join(paths)}{os.pathsep}{os.environ.get('PATH', '')}"

    ts_file = cur_dir / "ru.ts"
    qm_file = cur_dir / "ru.qm"

    try:
        run(
            ["pyside6-lupdate", "-no-obsolete", "-extensions", "py", str(src_dir), "-ts", str(ts_file), "-target-language", "ru_RU"],
            check=True, capture_output=True, text=True
        )
    except CalledProcessError as e:
        print(f"Error running lupdate:\n{e.stderr}", file=sys.stderr)
        sys.exit(1)

    tree = ET.parse(ts_file)
    used_sources = set()
    untranslated = set()
    modified = False

    for msg in tree.getroot().findall(".//message"):
        src = msg.find("source")
        tr = msg.find("translation")

        if src is not None and src.text is not None:
            text = src.text
            used_sources.add(text)

            if text in translations:
                if tr is None:
                    tr = ET.SubElement(msg, "translation")

                if tr.text != translations[text] or "type" in tr.attrib:
                    tr.text = translations[text]
                    tr.attrib.pop("type", None)
                    modified = True
            else:
                untranslated.add(text)

    unused = set(translations.keys()) - used_sources

    if modified:
        if hasattr(ET, 'indent'):
            ET.indent(tree, space="    ")
        with open(ts_file, 'wb') as f:
            f.write(b'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>\n')
            tree.write(f, encoding="utf-8", xml_declaration=False)

    if unused or untranslated:
        if unused:
            print("\nUnused translations:", file=sys.stderr)
            for s in sorted(unused):
                print(f"  - {s!r}", file=sys.stderr)
        if untranslated:
            print("\nUntranslated strings:", file=sys.stderr)
            for s in sorted(untranslated):
                print(f"  - {s!r}", file=sys.stderr)

        sys.exit(1)

    try:
        run(["pyside6-lrelease", str(ts_file), "-qm", str(qm_file)], check=True, capture_output=True, text=True)
        print("Translations updated successfully.")
    except CalledProcessError as e:
        print(f"Error running lrelease:\n{e.stderr}", file=sys.stderr)
        sys.exit(1)