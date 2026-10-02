"""The canonicaliser, transform C — S9 work item 2.

Deterministic. Three steps, applied in order to a query's text:

1. **Number words → digits.** Spanish cardinals (0 to 999,999), decimals read with "coma"
   ("uno coma cinco" → 1,5), "N y medio" → N,5, and "N por M" between two numbers → "NxM". Before a unit
   a number is always digits. Before any other word, the corpus decides: a number word becomes digits only
   if the corpus writes digits before that word more often than a number word ("cuatro tubos" → "4
   tubos"; "un tubo" and "dos tapas" stay, because the catalogue writes them so). With no evidence, a lone
   "un / una / uno" stays an article and any other number becomes digits.
2. **Unit spellings → the catalogue's spelling.** A generic lexicon groups every spelling of a unit
   ("mm", "milímetro", "milímetros"); after a number, any of them is replaced by the variant the
   corpus uses most. A unit the corpus never writes is left alone: there is no catalogue evidence for it.
3. **Unit conversion, snapped.** A quantity (one number, or numbers joined by "x", then a unit) is
   converted into each other unit of its dimension; it is replaced only if the converted value is a
   quantity the corpus writes in that unit, and then by the corpus's own surface for it ("0,03x0,015 m"
   → "30x15 mm" if the corpus writes "30x15 mm"). Dimensions written with a unit on every factor ("0,9 m x
   0,81 m x 0,7 m") are read in the dimension's base unit and snapped the same way. A quantity already in the inventory, or with no
   converted form in it, is left alone and counted as declined.

**What it knows** (S9 design, Design constraints). Generic Spanish (numerals, unit names) and the indexed
corpus — which form it writes before a word, the unit spellings and the quantity inventory are read from `OE_texto.json`,
which a deployed system has as its index. It never reads upstream's rewrite menus, a modifications
sidecar, a query's `parameters`, `modification_types`, gold or concept, and it does not see which query
set a text comes from. `synonym_label` rewrites are not targeted: they have no generic inverse.

Its rules were written on dev, so its dev figures are in-sample; S12 reads it held out.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "data" / "processed" / "OE_texto.json"

# --------------------------------------------------------------------------- generic Spanish numerals


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


_UNITS = {
    "cero": 0, "uno": 1, "un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14,
    "quince": 15, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20,
    "veintiuno": 21, "veintiun": 21, "veintiuna": 21, "veintidos": 22, "veintitres": 23,
    "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28,
    "veintinueve": 29,
}
_TENS = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80,
         "noventa": 90}
_HUNDREDS = {"cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200, "trescientos": 300,
             "trescientas": 300, "cuatrocientos": 400, "cuatrocientas": 400, "quinientos": 500,
             "quinientas": 500, "seiscientos": 600, "seiscientas": 600, "setecientos": 700,
             "setecientas": 700, "ochocientos": 800, "ochocientas": 800, "novecientos": 900,
             "novecientas": 900}
_ARTICLES = {"un", "una", "uno"}


def _value(word: str) -> int | None:
    w = _strip_accents(word.lower())
    return _UNITS.get(w, _TENS.get(w, _HUNDREDS.get(w)))


def _parse_int(words: list[str]) -> tuple[int, int] | None:
    """Longest prefix of `words` that reads as one cardinal: (value, words consumed)."""
    total, current, used, last = 0, 0, 0, None
    i = 0
    while i < len(words):
        w = _strip_accents(words[i].lower())
        if w == "mil":
            total += (current or 1) * 1000
            current, used, last = 0, i + 1, "mil"
            i += 1
            continue
        if w == "y" and last == "tens" and i + 1 < len(words):
            nxt = _strip_accents(words[i + 1].lower())
            if nxt in _UNITS and 1 <= _UNITS[nxt] <= 9:
                current += _UNITS[nxt]
                used, last = i + 2, "unit"
                i += 2
                continue
            break
        v = _value(w)
        if v is None:
            break
        kind = "hundreds" if w in _HUNDREDS else "tens" if w in _TENS else "unit"
        # A cardinal is read high to low; a word that cannot follow the previous one ends it.
        if last == "unit" or (last == "tens" and kind != "unit") or (last == "hundreds" and kind == "hundreds"):
            break
        current += v
        used, last = i + 1, kind
        i += 1
    if not used:
        return None
    return total + current, used


def _fmt(value: float) -> str:
    """Catalogue style: integers bare, decimals with a comma, no trailing zeros."""
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.6f}".rstrip("0").replace(".", ",")


_WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+|\d+(?:[.,]\d+)?|\S", re.UNICODE)


# --------------------------------------------------------------------------- generic unit lexicon

#: unit id -> (dimension, factor to the dimension's base, spellings). Generic Spanish and SI; nothing
#: here comes from the catalogue. Which spelling is written is decided by the corpus (step 2).
UNITS: dict[str, tuple[str, float, tuple[str, ...]]] = {
    "mm": ("length", 0.001, ("mm", "milímetro", "milímetros", "milimetro", "milimetros")),
    "cm": ("length", 0.01, ("cm", "centímetro", "centímetros", "centimetro", "centimetros")),
    "dm": ("length", 0.1, ("dm", "decímetro", "decímetros", "decimetro", "decimetros")),
    "m": ("length", 1.0, ("m", "metro", "metros", "mts", "mt")),
    "km": ("length", 1000.0, ("km", "kilómetro", "kilómetros", "kilometro", "kilometros")),
    "mm2": ("area", 1e-6, ("mm2", "mm²", "milímetro cuadrado", "milímetros cuadrados",
                           "milimetro cuadrado", "milimetros cuadrados")),
    "cm2": ("area", 1e-4, ("cm2", "cm²", "centímetro cuadrado", "centímetros cuadrados")),
    "m2": ("area", 1.0, ("m2", "m²", "metro cuadrado", "metros cuadrados")),
    "m3": ("volume", 1.0, ("m3", "m³", "metro cúbico", "metros cúbicos", "metro cubico", "metros cubicos")),
    "l": ("volume", 0.001, ("l", "litro", "litros")),
    "g": ("mass", 0.001, ("g", "gramo", "gramos")),
    "kg": ("mass", 1.0, ("kg", "kilogramo", "kilogramos", "kilo", "kilos")),
    "tn": ("mass", 1000.0, ("tonelada", "toneladas")),
    "min": ("time", 1 / 60, ("min", "minuto", "minutos")),
    "h": ("time", 1.0, ("h", "hora", "horas", "hr", "hrs")),
    "V": ("voltage", 1.0, ("V", "voltio", "voltios")),
    "kV": ("voltage", 1000.0, ("kV", "kv", "kilovoltio", "kilovoltios")),
    "N/mm2": ("pressure", 1.0, ("N/mm2", "N/mm²", "MPa", "megapascal", "megapascales",
                                "newton por milímetro cuadrado", "newtons por milímetro cuadrado")),
    "%": ("ratio", 1.0, ("%", "por ciento", "por cien")),
}

#: Spellings that are only units after a number when written exactly so: single letters are common words.
_CASE_SENSITIVE = {"m", "g", "h", "l", "V", "min"}


@dataclass
class Report:
    """What C did to one text."""
    numbers: int = 0
    units: int = 0
    converted: int = 0
    declined: int = 0

    def touched(self) -> bool:
        return bool(self.numbers or self.units or self.converted)


@dataclass
class Canonicaliser:
    """Built once from the corpus; `apply` is then a pure function of the text."""

    corpus_texts: list[str]
    digit_before: Counter = field(init=False)
    word_before: Counter = field(init=False)
    spelling: dict[str, str] = field(init=False)
    inventory: dict[tuple[str, tuple[float, ...]], Counter] = field(init=False)

    def __post_init__(self) -> None:
        self._unit_re = self._build_unit_re()
        self._build_compound_re()
        self.digit_before, self.word_before = self._number_contexts()
        self.spelling = self._spellings()
        self.inventory = self._inventory()

    # ---- corpus knowledge

    def _number_contexts(self) -> tuple[Counter, Counter]:
        """For each word, how often the corpus writes a digit right before it ("4 tubos") and how often a
        number word ("un tubo", "dos tapas"). The catalogue writes both, so which form a query should
        take before a given word is read from the catalogue, not assumed."""
        digit, word = Counter(), Counter()
        number_words = "|".join(sorted({*_UNITS, *_TENS, *_HUNDREDS}, key=len, reverse=True))
        word_re = re.compile(r"\b(?:" + number_words + r")\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)", re.IGNORECASE)
        for t in self.corpus_texts:
            for m in re.finditer(r"\d\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)", t):
                digit[m.group(1).lower()] += 1
            for m in word_re.finditer(_strip_accents(t)):
                word[m.group(1).lower()] += 1
        return digit, word

    def _digits_preferred(self, nxt: str, lone_article: bool) -> bool:
        """Whether a number word before `nxt` is written as digits. A unit or a decimal always is; else
        the corpus decides by which form it writes more often before `nxt`; with no evidence, a lone
        "un / una / uno" stays an article and any other number becomes digits."""
        w = _strip_accents(nxt.lower())
        if self._unit_of(nxt) is not None or w == "coma":
            return True
        d, n = self.digit_before[w], self.word_before[w]
        if d or n:
            return d > n
        return not lone_article

    def _spellings(self) -> dict[str, str]:
        """unit id -> the spelling the corpus writes most after a number. Absent if it never does."""
        out = {}
        for uid, (_, _, spellings) in UNITS.items():
            counts = Counter()
            for s in spellings:
                pat = re.compile(r"\d\s*" + re.escape(s) + r"(?![A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9²³])",
                                 0 if s in _CASE_SENSITIVE else re.IGNORECASE)
                counts[s] = sum(len(pat.findall(t)) for t in self.corpus_texts)
            best, n = counts.most_common(1)[0]
            if n:
                out[uid] = best
        return out

    def _build_compound_re(self) -> None:
        alts = sorted({x for _, _, sp in UNITS.values() for x in sp}, key=len, reverse=True)
        body = "|".join(re.escape(a) for a in alts)
        end = r"(?![A-Za-zÀ-ÿ0-9²³])"
        factor = r"(\d+(?:[.,]\d+)?)\s*(" + body + r")" + end
        self._factor_re = re.compile(factor, re.IGNORECASE)
        self._compound_re = re.compile(factor + r"(?:\s*x\s*" + factor + r")+", re.IGNORECASE)

    def _build_unit_re(self) -> re.Pattern:
        alts = sorted({s for _, _, sp in UNITS.values() for s in sp}, key=len, reverse=True)
        body = "|".join(re.escape(a) for a in alts)
        return re.compile(r"(?P<num>\d+(?:[.,]\d+)?(?:\s*x\s*\d+(?:[.,]\d+)?)*)(?P<sp>\s*)(?P<unit>" + body
                          + r")(?![A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9²³])", re.IGNORECASE)

    def _unit_of(self, spelling: str) -> str | None:
        for uid, (_, _, spellings) in UNITS.items():
            for s in spellings:
                if s in _CASE_SENSITIVE:
                    if spelling == s:
                        return uid
                elif spelling.lower() == s.lower():
                    return uid
        return None

    @staticmethod
    def _numbers(num: str) -> tuple[float, ...]:
        parts = re.split(r"\s*x\s*", num, flags=re.IGNORECASE)
        out = []
        for p in parts:
            p = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", p).replace(",", ".")
            out.append(round(float(p), 6))
        return tuple(out)

    def _inventory(self) -> dict[tuple[str, tuple[float, ...]], Counter]:
        """(unit id, values) -> Counter of the corpus's surface strings for that quantity."""
        inv: dict = defaultdict(Counter)
        for t in self.corpus_texts:
            for m in self._unit_re.finditer(t):
                uid = self._unit_of(m.group("unit"))
                if uid:
                    inv[(uid, self._numbers(m.group("num")))][m.group(0)] += 1
        return dict(inv)

    # ---- the three steps

    def numbers_to_digits(self, text: str, report: Report) -> str:
        tokens = [(m.group(0), m.start(), m.end()) for m in _WORD_RE.finditer(text)]
        out, pos, i = [], 0, 0
        while i < len(tokens):
            words = [t[0] for t in tokens[i:i + 12]]
            parsed = _parse_int(words) if _value(words[0]) is not None or words[0].lower() == "mil" else None
            if parsed:
                value, used = parsed
                nxt = tokens[i + used][0] if i + used < len(tokens) else ""
                lone_article = used == 1 and _strip_accents(words[0].lower()) in _ARTICLES
                if not self._digits_preferred(nxt, lone_article):
                    i += 1
                    continue
                end = tokens[i + used - 1][2]
                rendered = str(value)
                # "coma" decimals: "uno coma cinco" → 1,5; "cero coma treinta" → 0,30 read as 0,3.
                if nxt.lower() == "coma" and i + used + 1 < len(tokens):
                    frac = _parse_int([t[0] for t in tokens[i + used + 1:i + used + 13]])
                    if frac:
                        rendered = _fmt(float(f"{value}.{frac[0]}"))
                        end = tokens[i + used + frac[1]][2]
                        used += 1 + frac[1]
                elif nxt.lower() == "y" and i + used + 1 < len(tokens) and tokens[i + used + 1][0].lower() == "medio":
                    rendered = _fmt(value + 0.5)
                    end = tokens[i + used + 1][2]
                    used += 2
                out.append(text[pos:tokens[i][1]] + rendered)
                pos = end
                report.numbers += 1
                i += used
                continue
            i += 1
        out.append(text[pos:])
        text = "".join(out)
        # "30 por 15" → "30x15", only between two numbers.
        return re.sub(r"(?<=\d)\s+por\s+(?=\d)", "x", text)

    def unit_spellings(self, text: str, report: Report) -> str:
        def repl(m: re.Match) -> str:
            spelling = m.group("unit")
            uid = self._unit_of(spelling)
            if uid is None or uid not in self.spelling:
                return m.group(0)
            canonical = self.spelling[uid]
            if spelling == canonical:
                return m.group(0)
            report.units += 1
            return m.group("num") + (m.group("sp") or " ") + canonical
        return self._unit_re.sub(repl, text)

    def _snap(self, base_values: tuple[float, ...], dim: str, exclude: str | None) -> str | None:
        """The corpus's surface for a quantity of dimension `dim`, given in the dimension's base unit, in
        any unit but `exclude`. None if no unit has it in the inventory, or if two tie."""
        candidates = []
        for other, (odim, ofactor, _) in UNITS.items():
            if other == exclude or odim != dim:
                continue
            converted = tuple(round(v / ofactor, 6) for v in base_values)
            if (other, converted) in self.inventory:
                surface, n = self.inventory[(other, converted)].most_common(1)[0]
                candidates.append((n, surface))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            return None
        return candidates[0][1]

    def convert_compounds(self, text: str, report: Report) -> str:
        """Dimensions written with a unit on every factor ("0,9 m x 0,81 m x 0,7 m", "1,5 m x 90 cm"): read
        in the dimension's base unit and snapped to the corpus's surface, as `convert` does."""
        def repl(m: re.Match) -> str:
            factors = self._factor_re.findall(m.group(0))
            units = [self._unit_of(u) for _, u in factors]
            if None in units or len({UNITS[u][0] for u in units}) != 1:
                return m.group(0)
            dim = UNITS[units[0]][0]
            base = tuple(round(self._numbers(n)[0] * UNITS[u][1], 9) for (n, _), u in zip(factors, units))
            surface = self._snap(base, dim, None)
            if surface is None:
                report.declined += 1
                return m.group(0)
            report.converted += 1
            return surface
        return self._compound_re.sub(repl, text)

    def convert(self, text: str, report: Report) -> str:
        def repl(m: re.Match) -> str:
            uid = self._unit_of(m.group("unit"))
            if uid is None:
                return m.group(0)
            values = self._numbers(m.group("num"))
            if (uid, values) in self.inventory:
                return m.group(0)
            dim, factor, _ = UNITS[uid]
            surface = self._snap(tuple(v * factor for v in values), dim, uid)
            if surface is None:
                report.declined += 1
                return m.group(0)
            report.converted += 1
            return surface
        return self._unit_re.sub(repl, text)

    def apply(self, text: str) -> tuple[str, Report]:
        report = Report()
        text = self.numbers_to_digits(text, report)
        text = self.unit_spellings(text, report)
        text = self.convert_compounds(text, report)
        text = self.convert(text, report)
        return text, report


def from_corpus(path: Path = CORPUS) -> Canonicaliser:
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    return Canonicaliser([r["text"] for r in records])
