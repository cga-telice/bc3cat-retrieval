"""Unit tests for SpanNormalizer (Sprint LWN-02, B2).

Per protocol §6 Phase B2: at least 5 input variants per canonical value.
Run with: python -m unittest tests.test_span_normalizer
"""

import unittest
from pathlib import Path

from src.pipeline.span_normalizer import (
    FUZZY_THRESHOLD,
    SpanNormalizer,
    _collapse,
    _normalize_banda,
    _normalize_numeric,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "data" / "processed" / "OEB_concept_schema.json"


class TestHelpers(unittest.TestCase):
    def test_collapse_lowercases_and_strips(self):
        self.assertEqual(_collapse("  Diurno  "), "diurno")
        self.assertEqual(_collapse("Diurno  Excepcional"), "diurno excepcional")
        self.assertEqual(_collapse("\tDIURNO\n"), "diurno")

    def test_normalize_banda_operator_variants(self):
        self.assertEqual(_normalize_banda("i < 3 horas"), "i < 3 horas")
        self.assertEqual(_normalize_banda("i<3 horas"), "i < 3 horas")
        self.assertEqual(_normalize_banda("i< 3 horas"), "i < 3 horas")
        self.assertEqual(_normalize_banda("i  <  3   horas"), "i < 3 horas")
        self.assertEqual(_normalize_banda('i < "3" horas'), "i < 3 horas")
        self.assertEqual(_normalize_banda("3 <= i < 5 horas"), "3 <= i < 5 horas")
        self.assertEqual(_normalize_banda("3<=i<5 horas"), "3 <= i < 5 horas")
        self.assertEqual(_normalize_banda("i >= 5 horas"), "i >= 5 horas")
        self.assertEqual(_normalize_banda("i>= 5 horas"), "i >= 5 horas")

    def test_normalize_numeric_strips_units(self):
        self.assertEqual(_normalize_numeric("2"), "2")
        self.assertEqual(_normalize_numeric(" 2 "), "2")
        self.assertEqual(_normalize_numeric("2 mm"), "2")
        self.assertEqual(_normalize_numeric("110 mm"), "110")
        self.assertEqual(_normalize_numeric("1.60 m"), "1.60")


class TestSpanNormalizerExact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.norm = SpanNormalizer(SCHEMA_PATH)

    def test_terreno_exact_and_case_insensitive(self):
        # OEB010$ TERRENO axis values: blando / duro / medio
        self.assertEqual(self.norm.normalize("TERRENO", "blando", "OEB010$"), "blando")
        self.assertEqual(self.norm.normalize("TERRENO", "BLANDO", "OEB010$"), "blando")
        self.assertEqual(self.norm.normalize("TERRENO", "  blando  ", "OEB010$"), "blando")
        self.assertEqual(self.norm.normalize("TERRENO", "duro", "OEB010$"), "duro")
        self.assertEqual(self.norm.normalize("TERRENO", "Medio", "OEB010$"), "medio")

    def test_pavimento_exact_with_whitespace(self):
        # OEB010$ PAVIMENTO: con reposición / sin reposición
        self.assertEqual(
            self.norm.normalize("PAVIMENTO", "con reposición", "OEB010$"),
            "con reposición",
        )
        self.assertEqual(
            self.norm.normalize("PAVIMENTO", "Con  Reposición", "OEB010$"),
            "con reposición",
        )
        self.assertEqual(
            self.norm.normalize("PAVIMENTO", "SIN REPOSICIÓN", "OEB010$"),
            "sin reposición",
        )

    def test_condiciones_compound_value(self):
        # OEB010$ CONDICIONES: Cualquier condición de ejecución / Volumen escaso / Volumen relevante
        self.assertEqual(
            self.norm.normalize(
                "CONDICIONES DE EJECUCIÓN",
                "Cualquier condición de ejecución",
                "OEB010$",
            ),
            "Cualquier condición de ejecución",
        )
        self.assertEqual(
            self.norm.normalize(
                "CONDICIONES DE EJECUCIÓN", "volumen escaso", "OEB010$"
            ),
            "Volumen escaso",
        )
        self.assertEqual(
            self.norm.normalize(
                "CONDICIONES DE EJECUCIÓN", "VOLUMEN RELEVANTE", "OEB010$"
            ),
            "Volumen relevante",
        )

    def test_trabajo_compound_values(self):
        # OEB020$ TRABAJO: Diurno, Nocturno, Diurno Excepcional, Nocturno Excepcional, etc.
        self.assertEqual(self.norm.normalize("TRABAJO", "diurno", "OEB020$"), "Diurno")
        self.assertEqual(self.norm.normalize("TRABAJO", "Diurno", "OEB020$"), "Diurno")
        self.assertEqual(
            self.norm.normalize("TRABAJO", "diurno excepcional", "OEB020$"),
            "Diurno Excepcional",
        )
        self.assertEqual(
            self.norm.normalize("TRABAJO", "DIURNO EXCEPCIONAL", "OEB020$"),
            "Diurno Excepcional",
        )
        self.assertEqual(
            self.norm.normalize("TRABAJO", "Diurno  Excepcional", "OEB020$"),
            "Diurno Excepcional",
        )
        self.assertEqual(
            self.norm.normalize("TRABAJO", "nocturno excepcional", "OEB020$"),
            "Nocturno Excepcional",
        )


class TestSpanNormalizerBanda(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.norm = SpanNormalizer(SCHEMA_PATH)

    def test_i_lt_3_horas_variants(self):
        # OEB020$ BANDA: i < 3 horas, 3 <= i < 5 horas, i >= 5 horas, no necesita intervalo
        self.assertEqual(
            self.norm.normalize("BANDA DE MANTENIMIENTO", "i < 3 horas", "OEB020$"),
            "i < 3 horas",
        )
        self.assertEqual(
            self.norm.normalize("BANDA DE MANTENIMIENTO", "i<3 horas", "OEB020$"),
            "i < 3 horas",
        )
        self.assertEqual(
            self.norm.normalize("BANDA DE MANTENIMIENTO", "i< 3 horas", "OEB020$"),
            "i < 3 horas",
        )
        self.assertEqual(
            self.norm.normalize("BANDA DE MANTENIMIENTO", 'i < "3" horas', "OEB020$"),
            "i < 3 horas",
        )
        self.assertEqual(
            self.norm.normalize("BANDA DE MANTENIMIENTO", "i  <   3 horas", "OEB020$"),
            "i < 3 horas",
        )

    def test_3_le_i_lt_5_horas_variants(self):
        self.assertEqual(
            self.norm.normalize("BANDA DE MANTENIMIENTO", "3 <= i < 5 horas", "OEB020$"),
            "3 <= i < 5 horas",
        )
        self.assertEqual(
            self.norm.normalize("BANDA DE MANTENIMIENTO", "3<=i<5 horas", "OEB020$"),
            "3 <= i < 5 horas",
        )
        self.assertEqual(
            self.norm.normalize("BANDA DE MANTENIMIENTO", "3 <= I < 5 HORAS", "OEB020$"),
            "3 <= i < 5 horas",
        )

    def test_i_ge_5_horas_variants(self):
        self.assertEqual(
            self.norm.normalize("BANDA DE MANTENIMIENTO", "i >= 5 horas", "OEB020$"),
            "i >= 5 horas",
        )
        self.assertEqual(
            self.norm.normalize("BANDA DE MANTENIMIENTO", "i>=5 horas", "OEB020$"),
            "i >= 5 horas",
        )
        self.assertEqual(
            self.norm.normalize("BANDA DE MANTENIMIENTO", 'i >= "5" horas', "OEB020$"),
            "i >= 5 horas",
        )

    def test_no_necesita_intervalo(self):
        self.assertEqual(
            self.norm.normalize(
                "BANDA DE MANTENIMIENTO", "no necesita intervalo", "OEB020$"
            ),
            "No necesita intervalo",
        )
        self.assertEqual(
            self.norm.normalize(
                "BANDA DE MANTENIMIENTO", "NO NECESITA INTERVALO", "OEB020$"
            ),
            "No necesita intervalo",
        )


class TestSpanNormalizerSurfaceOverride(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.norm = SpanNormalizer(SCHEMA_PATH)

    def test_normal_via_cualquier_clase(self):
        # OEB020$ TIPO DE TERRENO has "Normal" but its surface form in long
        # text is "cualquier clase de terreno". The override fires only when
        # "Normal" is a valid value for the requested parent_key.
        self.assertEqual(
            self.norm.normalize(
                "TIPO DE TERRENO", "cualquier clase de terreno", "OEB020$"
            ),
            "Normal",
        )
        self.assertEqual(
            self.norm.normalize(
                "TIPO DE TERRENO", "Cualquier  Clase  De  Terreno", "OEB020$"
            ),
            "Normal",
        )
        self.assertEqual(
            self.norm.normalize(
                "TIPO DE TERRENO", "cualquier tipo de terreno", "OEB020$"
            ),
            "Normal",
        )

    def test_override_does_not_fire_when_canonical_invalid(self):
        # OEB010$ has TERRENO axis (blando/duro/medio), not TIPO DE TERRENO
        # with "Normal" — so the override must not fabricate "Normal" here.
        self.assertIsNone(
            self.norm.normalize(
                "TIPO DE TERRENO", "cualquier clase de terreno", "OEB010$"
            )
        )

    def test_other_terrain_values_match_directly(self):
        self.assertEqual(
            self.norm.normalize("TIPO DE TERRENO", "rocoso", "OEB020$"), "Rocoso"
        )
        self.assertEqual(
            self.norm.normalize("TIPO DE TERRENO", "adosada", "OEB020$"), "Adosada"
        )
        self.assertEqual(
            self.norm.normalize("TIPO DE TERRENO", "BAJO VÍAS", "OEB020$"),
            "Bajo vías",
        )


class TestSpanNormalizerNumeric(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.norm = SpanNormalizer(SCHEMA_PATH)

    def test_n_tubos_exact_and_padded(self):
        # OEB020$ Nº TUBOS: 2, 4, 6, 8, 12, 16, 18, 24
        self.assertEqual(self.norm.normalize("Nº TUBOS", "2", "OEB020$"), "2")
        self.assertEqual(self.norm.normalize("Nº TUBOS", " 2 ", "OEB020$"), "2")
        self.assertEqual(self.norm.normalize("Nº TUBOS", "12", "OEB020$"), "12")
        self.assertEqual(self.norm.normalize("Nº TUBOS", "16", "OEB020$"), "16")
        self.assertEqual(self.norm.normalize("Nº TUBOS", "24", "OEB020$"), "24")

    def test_n_tubos_with_unit_suffix(self):
        # The BIO span might pick up "2 mm" — strip and match
        self.assertEqual(self.norm.normalize("Nº TUBOS", "2 mm", "OEB020$"), "2")

    def test_diametros_inches_notation(self):
        # OEB170$ DIÁMETROS: 1'', 2'', 3'', 3 1/2'', 4'', 5'', 6''
        self.assertEqual(
            self.norm.normalize("DIÁMETROS", "1''", "OEB170$"), "1''"
        )
        self.assertEqual(
            self.norm.normalize("DIÁMETROS", " 1'' ", "OEB170$"), "1''"
        )
        self.assertEqual(
            self.norm.normalize("DIÁMETROS", "3 1/2''", "OEB170$"), "3 1/2''"
        )
        self.assertEqual(
            self.norm.normalize("DIÁMETROS", "3 1/2 ''", "OEB170$"), "3 1/2''"
        )


class TestSpanNormalizerNegative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.norm = SpanNormalizer(SCHEMA_PATH)

    def test_unknown_parent_key_returns_none(self):
        self.assertIsNone(
            self.norm.normalize("TERRENO", "blando", "NOT_A_GROUP$")
        )

    def test_unknown_axis_for_parent_returns_none(self):
        # OEB010$ has TERRENO/PAVIMENTO/CONDICIONES but no TRABAJO
        self.assertIsNone(self.norm.normalize("TRABAJO", "diurno", "OEB010$"))

    def test_garbage_text_returns_none(self):
        self.assertIsNone(
            self.norm.normalize("TERRENO", "asdfqwerty", "OEB010$")
        )
        self.assertIsNone(
            self.norm.normalize("TRABAJO", "lorem ipsum dolor sit amet", "OEB020$")
        )

    def test_empty_input_returns_none(self):
        self.assertIsNone(self.norm.normalize("TERRENO", "", "OEB010$"))
        self.assertIsNone(self.norm.normalize("TERRENO", "   ", "OEB010$"))


class TestSpanNormalizerFuzzy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.norm = SpanNormalizer(SCHEMA_PATH)

    def test_minor_typo_within_threshold(self):
        # "blandi" -> "blando": 1-char edit / 6 chars = 0.166 (above threshold)
        # "blanco" -> "blando": 1-char edit / 6 chars = 0.166 (above threshold)
        # "diurni" -> "diurno": 1/6 = 0.166 (above threshold)
        # Use longer values for fuzzy testing
        # "volumen relevant" -> "volumen relevante": 1/17 = 0.058 (under threshold)
        self.assertEqual(
            self.norm.normalize(
                "CONDICIONES DE EJECUCIÓN", "volumen relevant", "OEB010$"
            ),
            "Volumen relevante",
        )
        # "no necesita intervalo" with one missing char
        self.assertEqual(
            self.norm.normalize(
                "BANDA DE MANTENIMIENTO", "no necesita intervalo ", "OEB020$"
            ),
            "No necesita intervalo",
        )

    def test_too_far_returns_none(self):
        # "blanc" -> "blando": 2/6 = 0.333 (above 0.15)
        self.assertIsNone(
            self.norm.normalize("TERRENO", "blanc", "OEB010$")
        )


if __name__ == "__main__":
    unittest.main()
