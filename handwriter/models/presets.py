from __future__ import annotations
from json import load, dump, JSONDecodeError
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from PySide6.QtCore import QStandardPaths

@dataclass(slots=True)
class PaperTemplate:
    name: str = "Untitled"
    paper_width: float = 210.0
    paper_height: float = 297.0
    margin_top: float = 10.0
    margin_bottom: float = 10.0
    margin_left: float = 20.0
    margin_right: float = 10.0
    margin_top_first: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaperTemplate:
        kwargs = {}
        if "name" in data:
            kwargs["name"] = str(data["name"])
        for field in ("paper_width", "paper_height", "margin_top", "margin_bottom", "margin_left", "margin_right", "margin_top_first"):
            if field in data:
                kwargs[field] = float(data[field])
        return cls(**kwargs)

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> PaperTemplate:
        p = Path(path)
        try:
            with p.open("r", encoding="utf-8") as f:
                data = load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Template not found: {p}")
        except JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format in template {p}: {e}")
        return cls.from_dict(data)

DEFAULT_TEMPLATES = [
    PaperTemplate(
        name="A4",
        paper_width=210.0, paper_height=297.0,
        margin_top=1.0, margin_bottom=1.0,
        margin_left=1.0, margin_right=1.0,
        margin_top_first=0.0
    ),
    PaperTemplate(
        name="A4 with plotter borders",
        paper_width=210.0, paper_height=277.0,
        margin_top=5.0, margin_bottom=0.0,
        margin_left=1.0, margin_right=21.0,
        margin_top_first=0.0
    ),
    PaperTemplate(
        name="Notebook sheet",
        paper_width=145.0, paper_height=205.0,
        margin_top=10.0, margin_bottom=0.0,
        margin_left=0.0, margin_right=5.0,
        margin_top_first=0.0
    ),
]

class TemplateManager:
    def __init__(self, templates_dir: Path | None = None):
        if templates_dir:
            self.templates_dir = templates_dir
        else:
            base_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
            self.templates_dir = Path(base_dir) / "templates"
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        for tmpl in DEFAULT_TEMPLATES:
            filename = f"{tmpl.name}.hwpap"
            path = self.templates_dir / filename
            if not path.exists():
                tmpl.save(path)

    def get_templates_dir(self) -> Path:
        return self.templates_dir

    def save_template(self, template: PaperTemplate) -> Path:
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        filename = template.name.translate(str.maketrans('<>:"/\\|?*', '_________')) + ".hwpap"
        path = self.templates_dir / filename
        template.save(path)
        return path