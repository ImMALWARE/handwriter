from __future__ import annotations
from json import load, dump, JSONDecodeError
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

DEFAULT_MARGINS = {"top": 20.0, "bottom": 10.0, "left": 20.0, "right": 20.0, "top_first": 0.0}

@dataclass(slots=True)
class DocumentSettings:
    paper_width: float = 210.0
    paper_height: float = 297.0
    margins: dict[str, float] = field(default_factory=lambda: DEFAULT_MARGINS.copy())
    letter_size: float = 0.75
    line_spacing: float = 10.0
    show_grid: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentSettings:
        kwargs = {}
        for key in ("paper_width", "paper_height", "letter_size", "line_spacing"):
            if (val := data.get(key)) is not None:
                kwargs[key] = float(val)

        if (val := data.get("show_grid")) is not None:
            kwargs["show_grid"] = bool(val)

        if (val := data.get("margins")) is not None:
            margins = {**DEFAULT_MARGINS, **val}
            kwargs["margins"] = {str(k): float(v) for k, v in margins.items()}

        return cls(**kwargs)

@dataclass(slots=True)
class GCodeParams:
    feed: int = 6600                # XY movement speed
    passing_feed: int = 5000        # XY rapid move speed (G00)
    penetration_feed: int = 3000    # Z-axis speed
    z_up: int = 5                   # Travel height
    z_down: int = -1                # Drawing height

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GCodeParams:
        kwargs = {}
        for key in ("feed", "passing_feed", "penetration_feed", "z_up", "z_down"):
            if (val := data.get(key)) is not None:
                kwargs[key] = int(val)
        return cls(**kwargs)


@dataclass(slots=True)
class HWDoc:
    version: int = 1
    font_path: str = ""
    text: str = ""
    variant_map: dict[str, int] = field(default_factory=dict)
    settings: DocumentSettings = field(default_factory=DocumentSettings)
    gcode_params: GCodeParams = field(default_factory=GCodeParams)
    path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("path", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HWDoc:
        kwargs = {}
        if (val := data.get("version")) is not None:
            kwargs["version"] = int(val)
        if (val := data.get("font_path")) is not None:
            kwargs["font_path"] = str(val)
        if (val := data.get("text")) is not None:
            kwargs["text"] = str(val)
        if (val := data.get("variant_map")) is not None:
            kwargs["variant_map"] = {str(k): int(v) for k, v in val.items()}
        if (val := data.get("settings")) is not None:
            kwargs["settings"] = DocumentSettings.from_dict(val)
        if (val := data.get("gcode_params")) is not None:
            kwargs["gcode_params"] = GCodeParams.from_dict(val)

        return cls(**kwargs)

    @classmethod
    def load(cls, path: str | Path) -> HWDoc:
        p = Path(path)
        try:
            with p.open("r", encoding="utf-8") as f:
                data = load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {p}")
        except JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format in document {p}: {e}")

        doc = cls.from_dict(data)
        doc.path = p
        return doc

    def save(self, path: str | Path | None = None) -> None:
        p = Path(path) if path else self.path
        if p is None:
            raise ValueError("No path specified for saving")

        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        self.path = p