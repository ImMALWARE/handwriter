from random import randint, uniform
from re import compile as recompile
from dataclasses import dataclass, field
from pyphen import Pyphen, LANGUAGES
from handwriter.models.hfont import HFont, GlyphVariant
from handwriter.models.hwdoc import DocumentSettings

@dataclass
class PlacedGlyph:
    char: str
    x: float
    y: float
    scale: float
    glyph_variant: GlyphVariant
    missing: bool = False # True if char was not found in font

@dataclass
class Connector:
    x1: float
    y1: float
    x2: float
    y2: float
    cx1: float | None = None  # First control point for cubic Bezier
    cy1: float | None = None
    cx2: float | None = None  # Second control point for cubic Bezier
    cy2: float | None = None

@dataclass
class PageLayout:
    page_index: int
    width: float
    height: float
    glyphs: list[PlacedGlyph] = field(default_factory=list)
    connectors: list[Connector] = field(default_factory=list)

@dataclass
class LayoutResult:
    pages: list[PageLayout] = field(default_factory=list)
    variant_map: dict[str, int] = field(default_factory=dict)
    missing_chars: set[str] = field(default_factory=set)
    invalid_bbcode_lines: list[int] = field(default_factory=list)

class LayoutEngine:
    _dic_ru: Pyphen | None = None
    _dic_en: Pyphen | None = None
    RE_OPEN_TAG = recompile(r'^\[(center|right)\]')
    RE_CLOSE_TAG = recompile(r'\[/(center|right)\]$')
    RE_INVALID_TAG = recompile(r'\[/?(?:center|right)\]')
    RE_WORD_PARTS = recompile(r"^(\W*)([\w\-]+)(\W*)$")
    RE_RU_CHAR = recompile(r'[а-яА-ЯёЁ]')
    RE_EN_CHAR = recompile(r'[a-zA-Z]')

    @classmethod
    def get_dic_ru(cls) -> Pyphen:
        if cls._dic_ru is None:
            cls._dic_ru = Pyphen(filename=str(LANGUAGES["ru_RU"]), lang="ru_RU")
        return cls._dic_ru

    @classmethod
    def get_dic_en(cls) -> Pyphen:
        if cls._dic_en is None:
            cls._dic_en = Pyphen(filename=str(LANGUAGES["en_US"]), lang="en_US")
        return cls._dic_en

    def __init__(self, font: HFont, settings: DocumentSettings):
        self.font = font
        self.settings = settings

    def layout_text(self, text: str, variant_map: dict[str, int] | None = None, is_cancelled=None) -> LayoutResult:
        s = self.settings
        self._scale = s.letter_size
        self._line_h = s.line_spacing
        self._margin_left = s.margins["left"]
        self._margin_right = s.margins["right"]
        self._margin_top = s.margins["top"]
        self._margin_bottom = s.margins["bottom"]
        self._page_w = s.paper_width
        self._page_h = s.paper_height
        self._right_edge = self._page_w - self._margin_right
        self._result = LayoutResult()
        self._cursor_x = self._margin_left
        self._cursor_y = self._get_first_baseline()

        self._current_page = PageLayout(
            page_index=0,
            width=self._page_w,
            height=self._page_h,
        )
        self._result.pages.append(self._current_page)

        self._variant_map = variant_map or {}
        self._new_variant_map: dict[str, int] = {}
        self._glyph_counter = 0 # global char position counter
        self._word_width_cache: dict[str, float] = {}

        lines = text.split("\n")
        line_info, events, valid_events, invalid_lines = self._parse_bbcode(lines)

        align_stack = []
        for i, info in enumerate(line_info):
            if is_cancelled and is_cancelled():
                break

            for e_idx in info['opens']:
                if e_idx in valid_events:
                    tag = events[e_idx][1]
                    align_stack.append(tag)
                else:
                    invalid_lines.add(i + 1)

            effective_align = align_stack[0] if align_stack else "left"
            clean_line = info['clean']

            if effective_align in ("center", "right"):
                self._layout_aligned_line(clean_line, effective_align)
            else:
                self._layout_line(clean_line)

            for e_idx in info['closes']:
                if e_idx in valid_events:
                    tag = events[e_idx][1]
                    for j in range(len(align_stack)-1, -1, -1):
                        if align_stack[j] == tag:
                            align_stack.pop(j)
                            break
                else:
                    invalid_lines.add(i + 1)

        self._result.invalid_bbcode_lines = sorted(list(invalid_lines))
        self._result.variant_map = self._new_variant_map
        return self._result

    def _get_first_baseline(self) -> float:
        cell = 5.0 # mm, standard notebook cell

        is_first_page = len(self._result.pages) == 0
        top_first = self.settings.margins.get("top_first", 0.0)

        if is_first_page and top_first > 0:
            eff_margin_top = top_first
        else:
            eff_margin_top = self._margin_top

        first_baseline = eff_margin_top + cell
        remainder = first_baseline % cell
        if remainder > 1e-6:
            first_baseline += cell - remainder
        return first_baseline

    def _parse_bbcode(self, lines: list[str]) -> tuple[list[dict], list[tuple], set[int], set[int]]:
        line_info = []
        events = [] # (event_index, e_type, tag_name, line_idx)
        invalid_lines = set()

        for i, line in enumerate(lines):
            opens = []
            closes = []

            while True:
                m_open = self.RE_OPEN_TAG.match(line)
                if m_open:
                    tag = m_open.group(1)
                    events.append(('open', tag, i))
                    opens.append(len(events) - 1)
                    line = line[len(m_open.group(0)):]
                else:
                    break

            found_closes = []
            while True:
                m_close = self.RE_CLOSE_TAG.search(line)
                if m_close:
                    tag = m_close.group(1)
                    found_closes.append((tag, m_close.group(0)))
                    line = line[:-len(m_close.group(0))]
                else:
                    break

            for tag, _ in reversed(found_closes):
                events.append(('close', tag, i))
                closes.append(len(events) - 1)

            invalid = self.RE_INVALID_TAG.findall(line)
            if invalid:
                invalid_lines.add(i + 1)
                line = self.RE_INVALID_TAG.sub('', line)

            line_info.append({
                'clean': line,
                'opens': opens,
                'closes': closes
            })

        stack = []
        valid_events = set()

        for e_idx, (e_type, tag, l_idx) in enumerate(events):
            if e_type == 'open':
                stack.append((e_idx, tag, l_idx))
            else: # close
                for j in range(len(stack)-1, -1, -1):
                    if stack[j][1] == tag:
                        open_e_idx, _, _ = stack.pop(j)
                        valid_events.add(open_e_idx)
                        valid_events.add(e_idx)
                        break

        return line_info, events, valid_events, invalid_lines

    def _check_page_end(self) -> None:
        if self._cursor_y > (self._page_h - self._margin_bottom):
            self._new_page()

    def _new_page(self) -> None:
        page = PageLayout(
            page_index=len(self._result.pages),
            width=self._page_w,
            height=self._page_h,
        )
        self._result.pages.append(page)
        self._current_page = page
        self._cursor_x = self._margin_left
        self._cursor_y = self._get_first_baseline()

    def _newline(self) -> None:
        self._cursor_x = self._margin_left + uniform(-1.5, 2.5)
        self._cursor_y += self._line_h

    def _get_word_width(self, word: str) -> float:
        cached = self._word_width_cache.get(word)
        if cached is not None:
            return cached

        w = 0.0
        for ch in word:
            variants = self.font.get_variants(ch)
            adv = 5.0 if variants else 3.5
            w += adv + 0.5

        w *= self._scale
        self._word_width_cache[word] = w
        return w

    def _pick_variant(self, char: str) -> tuple[int, GlyphVariant, bool]:
        variants = self.font.get_variants(char)
        if not variants:
            self._result.missing_chars.add(char)
            # Return a dummy missing variant
            return 0, GlyphVariant(paths=[]), True

        key = str(self._glyph_counter)
        if key in self._variant_map:
            idx = self._variant_map[key]
            idx = min(idx, len(variants) - 1)
        else:
            idx = randint(0, len(variants) - 1)

        self._new_variant_map[key] = idx
        return idx, variants[idx], False

    def _draw_word(self, word: str) -> None:
        s = self._scale
        prev_end: tuple[float, float] | None = None
        prev_char: str | None = None

        for char in word:
            idx, variant, is_missing = self._pick_variant(char)
            self._glyph_counter += 1

            jit_x = uniform(-0.1, 0.1)

            gx = self._cursor_x + jit_x
            gy = self._cursor_y

            # Connector curve
            is_seq = (prev_char and prev_char.isalpha() and char.isalpha())
            if is_seq and prev_end and variant.start:
                start_x = gx + variant.start[0] * s
                start_y = gy + variant.start[1] * s
                dx = start_x - prev_end[0]
                tension = 0.4
                self._current_page.connectors.append(Connector(
                    x1=prev_end[0], y1=prev_end[1],
                    x2=start_x, y2=start_y,
                    cx1=prev_end[0] + dx * tension, cy1=prev_end[1],
                    cx2=start_x - dx * tension, cy2=start_y,
                ))

            # Place glyph
            self._current_page.glyphs.append(PlacedGlyph(
                char=char,
                x=gx, y=gy,
                scale=s,
                glyph_variant=variant,
                missing=is_missing,
            ))

            if variant.end:
                prev_end = (gx + variant.end[0] * s, gy + variant.end[1] * s)
            else:
                prev_end = None
            prev_char = char

            adv = 5.0 if not is_missing else 3.5
            self._cursor_x += (adv + 0.5) * s

        # Space after word
        self._cursor_x += 4 * self._scale

    def _layout_line(self, line: str) -> None:
        words = line.split(" ")
        for word in words:
            if not word:
                continue
            self._check_page_end()
            ww = self._get_word_width(word)
            if self._cursor_x + ww < self._right_edge:
                self._draw_word(word)
            else:
                self._hyphenate(word)
        self._newline()

    def _layout_aligned_line(self, text: str, align: str) -> None:
        available = self._page_w - self._margin_left - self._margin_right
        words = text.split(" ")
        gap = 4 * self._scale

        # Split words into rows that fit
        rows: list[tuple[list[str], float]] = []
        row: list[str] = []
        row_w = 0.0
        for word in words:
            if not word:
                continue
            ww = self._get_word_width(word)
            if not row:
                row.append(word)
                row_w = ww
            elif row_w + gap + ww <= available:
                row.append(word)
                row_w += gap + ww
            else:
                rows.append((row, row_w))
                row = [word]
                row_w = ww

        if row:
            rows.append((row, row_w))

        if not rows:
            self._newline()
            return

        for row_words, row_width in rows:
            self._check_page_end()

            if align == "center":
                self._cursor_x = max(self._margin_left, self._margin_left + (available - row_width) / 2)
            elif align == "right":
                self._cursor_x = max(self._margin_left, self._page_w - self._margin_right - row_width)
            else:
                self._cursor_x = self._margin_left

            for w in row_words:
                self._draw_word(w)
            self._newline()

    def _fit_word(self, word: str, available: float) -> tuple[str, str]:
        if self._get_word_width(word) <= available:
            return word, ""

        m = self.RE_WORD_PARTS.match(word)
        if m:
            pre, core, suf = m.groups()

            dic = None
            if self.RE_RU_CHAR.search(core):
                dic = self.get_dic_ru()
            elif self.RE_EN_CHAR.search(core):
                dic = self.get_dic_en()

            if dic:
                for p1, p2 in dic.iterate(core):
                    if len(p1) < 2 or len(p2) < 2:
                        continue
                    candidate = f"{pre}{p1}-"
                    if self._get_word_width(candidate) <= available:
                        return candidate, f"{p2}{suf}"

        if self._cursor_x <= self._margin_left + 3.0:
            for i in range(len(word) - 1, 0, -1):
                part = word[:i]
                candidate = part if part[-1] in "-–—" else part + "-"
                if self._get_word_width(candidate) <= available:
                    return candidate, word[i:]

            if len(word) > 1:
                return word[:1] + "-", word[1:]

        return "", word

    def _hyphenate(self, word: str) -> None:
        remaining = self._right_edge - self._cursor_x
        fitted, rem = self._fit_word(word, remaining)

        if fitted:
            self._draw_word(fitted)
            self._newline()
            self._check_page_end()
            if rem:
                if self._cursor_x + self._get_word_width(rem) < self._right_edge:
                    self._draw_word(rem)
                else:
                    self._hyphenate(rem)
        elif self._cursor_x > self._margin_left + 1:
            self._newline()
            self._check_page_end()
            if self._cursor_x + self._get_word_width(word) < self._right_edge:
                self._draw_word(word)
            else:
                self._hyphenate(word)
        else:
            self._draw_word(word)