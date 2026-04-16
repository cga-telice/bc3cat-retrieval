# Sprint LW-06 — Cross-Distribution Failure Analysis

**Date:** 2026-04-16
**Context:** Classifier trained on long text (documents), evaluated on short text (queries).
Val accuracy on long text: 99.6%. Pipeline item Acc@1 on short text: 20.9%.

---

## Root Cause: Surface-Level Formatting Mismatch

The failure is NOT a semantic understanding problem. Both short and long text encode the **same parameter values**, but in **completely incompatible surface formats**.

### Long text (training distribution)

Parameters appear as explicit labeled key-value pairs at the end of the text:

```
... al lugar de empleo trabajo: diurno banda de mantenimiento: i < 3 horas
condiciones de ejecucion: volumen escaso
```

### Short text (evaluation queries)

Parameters appear in compressed parenthetical notation — no axis labels, slash-separated, with inconsistent quoting:

```
... (diurno/i < "3" horas/volumen escaso)
```

### Additional formatting discrepancies

| Axis | Long text | Short text |
|---|---|---|
| BANDA DE MANTENIMIENTO | `3 <= i < 5 horas` | `3 >== i > "5" horas` |
| TIPO DE TERRENO | `en terreno rocoso` | `rocoso` |
| TIPO DE TERRENO | `adosada o superficial` | `adosada` |
| Nº TUBOS | `16 tubos` | `16 t` |
| General | `trabajo: diurno` | `(diurno/...)` |

---

## Per-Axis Accuracy (2,000-query sample)

| Axis | Correct | Total | Accuracy | Transfer? |
|---|---|---|---|---|
| Nº TUBOS | 1,938 | 1,938 | **100.0%** | Numbers transfer |
| PROFUNDIDAD | 42 | 42 | **100.0%** | Numbers transfer |
| DIÁMETROS | 105 | 105 | **100.0%** | Numbers transfer |
| TUBO | 1 | 1 | **100.0%** | Too few samples |
| CONDICIONES DE EJECUCIÓN | 1,912 | 2,000 | **95.6%** | Values identical in both |
| TIPO DE TERRENO | 1,278 | 1,849 | **69.1%** | Short abbreviates |
| BANDA DE MANTENIMIENTO | 1,256 | 1,996 | **62.9%** | Format completely different |
| TRABAJO | 1,048 | 1,996 | **52.5%** | Worst axis — "excepcional" confusion |
| TIPO DE ACCIÓN | 6 | 14 | **42.9%** | Abbreviation issues |
| DIÁMETRO | 1 | 2 | **50.0%** | Too few samples |
| TERRENO | 0 | 2 | **0.0%** | Too few samples |
| PAVIMENTO | 0 | 2 | **0.0%** | Too few samples |

**Key insight:** Axes with numeric values (Nº TUBOS, PROFUNDIDAD, DIÁMETROS) transfer perfectly across distributions. Axes with text-based values that are formatted differently in short vs long text are where the failures concentrate.

---

## Top Confusion Patterns

### TRABAJO (948/1,996 errors = 47.5% error rate)

| Ground Truth | Prediction | Count |
|---|---|---|
| Diurno | Diurno Excepcional | 295 |
| Nocturno Excepcional | Diurno Excepcional | 284 |
| Cualquier franja horaria | Cualquier franja horaria excepcional | 232 |
| Nocturno | Diurno | 61 |
| Nocturno | Diurno Excepcional | 41 |

The classifier learned long-text-specific patterns that associate certain phrasings with "excepcional". These patterns don't exist in the short text format, so the classifier defaults to "excepcional" variants frequently.

### BANDA DE MANTENIMIENTO (740/1,996 errors = 37.1% error rate)

| Ground Truth | Prediction | Count |
|---|---|---|
| i < 3 horas | 3 <= i < 5 horas | 477 |
| 3 <= i < 5 horas | i >= 5 horas | 148 |
| No necesita intervalo | 3 <= i < 5 horas | 54 |
| No necesita intervalo | i >= 5 horas | 29 |

The short text uses different operators and quoting: `i < "3"` vs `i < 3 horas`, `3 >== i > "5"` vs `3 <= i < 5 horas`. The classifier can't parse the short-text formatting.

### TIPO DE TERRENO (571/1,849 errors = 30.9% error rate)

| Ground Truth | Prediction | Count |
|---|---|---|
| Adosada | Normal | 187 |
| Con topo | Normal | 178 |
| Rocoso | Normal | 94 |
| Con topo | Andén | 37 |
| Adosada | Andén | 34 |

The classifier defaults to "Normal" when it doesn't recognize the shortened terreno expression. Long text says "en terreno rocoso" / "adosada o superficial", short text says just "rocoso" / "adosada".

### CONDICIONES DE EJECUCIÓN (88/2,000 errors = 4.4% error rate)

| Ground Truth | Prediction | Count |
|---|---|---|
| Cualquier condición de ejecución | Volumen relevante | 75 |

Mostly correct — values are identical in both formats.

---

## Concrete Examples

### Example 1: OEB040idbcb (OEB040$)

**Short text (query):**
`canalización hormigonada 16 t, polietileno libre de halógenos de 160 mm, en cruce de carretera. (nocturno/i < "3" horas/volumen escaso)`

**Long text (training):**
`canalización hormigonada de 16 tubos de polietileno libre de halógenos de 160 mm de diámetro en cruce de carretera, incluso la demolición y reposición del firme y del pavimento ... trabajo: nocturno banda de mantenimiento: i < 3 horas condiciones de ejecución: volumen escaso`

| Axis | Ground Truth | Pred (short) | Pred (long) |
|---|---|---|---|
| BANDA DE MANTENIMIENTO | i < 3 horas | 3 <= i < 5 horas **MISS** | i < 3 horas OK |
| CONDICIONES DE EJECUCIÓN | Volumen escaso | Volumen escaso OK | Volumen escaso OK |
| Nº TUBOS | 16 | 16 OK | 16 OK |
| TIPO DE TERRENO | Cruce de carretera | Cruce de carretera OK | Cruce de carretera OK |
| TRABAJO | Nocturno | Nocturno OK | Nocturno OK |

**Failure**: BANDA fails because short text uses `i < "3"` (with quotes), long text uses `i < 3 horas`.

### Example 2: OEB290jfeba (OEB290$)

**Short text:**
`canalización hormigonada 18 t, polietileno libre de halógenos de 50 mm, adosada. (cualquier franja horaria/3 <== i < "5" horas/volumen relevante)`

| Axis | Ground Truth | Pred (short) | Pred (long) |
|---|---|---|---|
| TIPO DE TERRENO | Adosada | Normal **MISS** | Adosada OK |
| TRABAJO | Cualquier franja horaria | Cualquier franja horaria excepcional **MISS** | Cualquier franja horaria OK |

**Failures**: "adosada" without "o superficial" → defaults to Normal. "Cualquier franja horaria" without explicit label context → adds "excepcional".

### Example 3: OEB030ceddc (OEB030$)

**Short text:**
`canalización hormigonada 3 t, polietileno libre de halógenos de 110 mm, en andén. (nocturno excepcional/no necesita intervalo/cualquier condición de ejecución)`

| Axis | Ground Truth | Pred (short) | Pred (long) |
|---|---|---|---|
| TRABAJO | Nocturno Excepcional | Diurno Excepcional **MISS** | Nocturno Excepcional OK |

**Failure**: Short text says `nocturno excepcional` but without the `trabajo:` label prefix, the classifier confuses "nocturno" with "diurno".

---

## Conclusions

1. The classifier learns **format-specific pattern matching**, not semantic parameter extraction
2. Numerical axes transfer perfectly across distributions — the numbers themselves are the signal
3. Text-based axes fail because the **surface encoding** is completely different between long and short text
4. The most problematic axes (TRABAJO, BANDA, TIPO DE TERRENO) have the largest formatting gaps
5. The 96.6% from LW-05 was indeed data leakage; the real cross-distribution accuracy is ~21%
