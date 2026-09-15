# AUTCON-D-26-03592 — Análisis de los comentarios de revisión

**Paper:** *A Systematic Comparative Study of Retrieval Methods for Parametric Construction Catalogs*
**Estado:** rechazado (Automation in Construction)
**Fecha del análisis:** 2026-09-09
**Fuentes verificadas:** `docs/reviews/paper_28.tex`, `src/*.ipynb`, `configs/*.yaml`, `runs/**`, `eval/**`, `data/processed/OEB_{resumen,texto}.json`

---

## 0. Estado del repositorio (comprobación previa)

| Comprobación | Resultado |
|---|---|
| Rama del árbol de trabajo | **`research/synthetic-oe`**, HEAD `fc30a16` (2026-09-08, *"INTAKE: OE corpus files in place and validated"*) |
| `git diff --stat bc3-ir-paper-v1.0.0 HEAD -- src configs eval` | **Vacío.** El código de `src/`, `configs/` y `eval/` es idéntico al del tag. No hace falta `git show`: lo leído es lo del paper. |
| Modificaciones sin commitear | `MethodsX_BC3CAT.docx` (M), `docs/reviews/` y `.serena/` sin trackear |

**Fechas de los directorios ignorados** (envío = 2026-06-24):

| Directorio | Fichero más reciente | ¿Posterior al envío? |
|---|---|---|
| `runs/` | 2026-04-30 | No |
| `eval/` | 2025-10-15 | No |
| `evals/` | 2025-08-19 | No |
| `analysis/` | 2026-04-30 | No |
| `data/` | **2026-09-08** | **Sí — pero no afecta** |

Sobre `data/`: los seis ficheros posteriores al envío son `OE_resumen.json`, `OE_texto.json`, `OE_concept_schema.json`, `OE_single_texto.json`, `OE_stacked_texto.json` y `OE_handoff_README.md` — todos de la línea `synthetic-oe` de ayer. Los ficheros del paper (`OEB_*`) son de 2025-06-08 a 2026-03-09, muy anteriores. **No hay contaminación.**

Confirmado también lo que indicabas: `analysis/` (abr-2026) pertenece a `lightweight-extraction-ner`. Añado un matiz relevante: dentro de `runs/` hay **13 directorios `structured_pipeline*`** fechados entre 2026-03-11 y 2026-04-30, de esa misma línea de trabajo. No forman parte del paper, pero **responden directamente a la última pregunta del Revisor #2** (§4.3 de este informe).

---

## 1. Clasificación de los comentarios

### A. Defectos corregibles (26 puntos) — no cuestionan el trabajo, sólo su ejecución

Inconsistencias numéricas, errores de etiquetado, terminología, formato de citas, redacción. Todos verificados abajo. **Ninguno requiere reejecutar nada** salvo dos (baseline PRF y selección en test).

### B. Objeciones al objetivo del benchmark (7 puntos) — sustantivas

| # | Quién | Objeción |
|---|---|---|
| B1 | R1-2, R1-3, R2-1.1, R2-7.1 | Query y target salen del mismo registro de catálogo → el escenario no es el del *Introduction* |
| B2 | R1-1, AE | Sin método nuevo; contribución = benchmarking |
| B3 | R1-4 | Falta comparar con HyDE / reescritura de consultas |
| B4 | R2-final | Si los atributos son estructurados, ¿por qué no un baseline de filtrado por reglas? |
| B5 | R1-2, R2-5.1 | El diseño favorece a los métodos léxicos; las conclusiones se generalizan de más |
| B6 | R2-1.2 | El alcance de la "guía para profesionales" no está delimitado |
| B7 | R2-2.3 | Falta cuantificar cuánta información comparten `resumen` y `texto` |

**B1, B5, B6 y B7 son la misma objeción vista desde cuatro ángulos, y tienen razón.** La evidencia está en §2.6. B2 es parcialmente rebatible. B3 y B4 son peticiones de experimento adicional; B4 ya lo tienes casi hecho.

### C. Decisión editorial (2 puntos) — no accionables por corrección

- **AE:** *"limited alignment with the domain of construction (practical impact), little novelty"*. Es un juicio de encaje con la revista, no un defecto. Un benchmark puro sin propuesta metodológica tiene difícil encaje en AiC salvo que el aporte de dominio sea muy visible.
- **R2-9:** *"Could the manuscript benefit from language editing? Yes"* (R1 dice No). Discrepancia entre revisores; edición profesional resuelve.

---

## 2. Verificación de cada objeción metodológica

> Criterio: no se acepta ni se rechaza ninguna objeción sin contrastarla contra paper, código y datos. Se indica **la cifra correcta y el fichero del que sale**.

### 2.1 R2-2.1 — Conteos de consultas inconsistentes ✅ **EL REVISOR TIENE RAZÓN**

| Cifra en el paper | Dónde | Veredicto | Cifra correcta | Fuente |
|---|---|---|---|---|
| 16.590 consultas muestreadas | §3.3.1 L471 | ✅ Correcta | 16.590 | `hybrid.ipynb` CFG `sample_size: 16590, seed: 1337`; todos los `metrics_dual.json` |
| **24.711 HAS_NUM / 15.136 NO_NUM** | §3.3.4 L518-520 | ❌ **Falsa** | **16.561 / 29** | `runs/*/metrics_dual.json`, campo `queries` por `scope` |
| **16.076 numéricas / 29 no numéricas** | Tabla 4, caption L631 | ❌ El "29" es correcto, **el 16.076 no** | **16.561** / 29 | ídem |
| 16.589 en resultados neuronales | Tablas 8/12 | ✅ **Correcta y reveladora** | 16.589 | `runs/dense_e5/metrics_dual.json` |

**Origen del error 24.711/15.136:** `24.711 + 15.136 = 39.847` — exactamente el tamaño del dataset de la **versión anterior del estudio** (`papers/paper1/paper_vf.tex`). Son cifras huérfanas arrastradas de la versión de 39.847 ítems / 117 configuraciones. No corresponden a ningún experimento de este paper.

**Sobre el 16.076:** el porcentaje asociado (99,83 %) sí es correcto — `16.561 / 16.590 = 99,825 %`. Es un error de transcripción del numerador, no de cálculo. **El cuerpo de la Tabla 4 es correcto**; sólo falla el caption.

**Sobre el 16.589:** no es un error de redondeo. Es la punta de un problema mucho mayor, descrito en §3.1.

### 2.2 R2-2.2 — Baseline del PRF ✅ **EL REVISOR TIENE RAZÓN**

- §4.1 L653: *"BM25 with optimized parameters (k1=0.60, b=0.35) was selected as the best-performing lexical method for subsequent pseudo-relevance feedback experiments"*
- §4.2 L658: *"Both methods leveraged BM25-unigram (k1=0.80, b=0.35) as their base retriever, which achieved Acc@1 of 0.869"*

**Verificado:** los 16 runs de PRF existentes son `prf_{rm3,rocchio}__bm25_unigram__M*__N*__beta*` — todos sobre `bm25_unigram`, **ninguno sobre `bm25_unigram_params`**. El baseline realmente usado es el **débil (0,8691)**, no el óptimo (0,9737).

| | Acc@1 | Fuente |
|---|---|---|
| BM25-unigram k1=0,80 b=0,35 (baseline usado) | **0,8691** | `runs/bm25_unigram__k1-0.80__b-0.35/metrics_dual.json` |
| BM25-unigram-params k1=0,60 b=0,35 (baseline declarado) | **0,9737** | `runs/bm25_unigram_params__k1-0.60__b-0.35/metrics_dual.json` |

La conclusión del PRF (*"query expansion is ill-suited for this domain"*) se sostiene lógicamente — si RM3 no mejora sobre un baseline de 0,869, menos aún sobre uno de 0,974 — pero **la frase L653 es simplemente falsa** y el revisor pide, con razón, o corregirla o reejecutar. Reejecutar es barato (16 runs) y elimina la objeción por completo.

### 2.3 R2-3.1 — Corrección por comparaciones múltiples ✅ **EL REVISOR TIENE RAZÓN**

- §3.3.5 L530: *"We apply **Bonferroni** correction"*
- §4.1 L587: *"(10,000 iterations, **Bonferroni** correction)"*
- Tabla 3, caption L593 y nota L622: *"**Holm-Bonferroni**"*

**Verificado en el código:** `src/bootstrap_sigtests.ipynb` implementa `def holm_bonferroni(pvals)` (L118-142) y Benjamini–Hochberg; **nunca Bonferroni simple**. `N_BOOT = 10000`, `ALPHA = 0.05`.

**Correcto: Holm–Bonferroni.** Es sólo edición de texto (2 líneas). Matiz adicional: el umbral citado *"p < 0.003"* (L587, L593) es `0,05/17 ≈ 0,0029`, que es el umbral **de Bonferroni** para 17 comparaciones — mezcla la nomenclatura de una corrección con los p-valores de otra. Conviene reportar los `p_holm` que ya están en `eval/bootstrap_lexical/bootstrap_sigtests_pairs.csv`.

### 2.4 R2-3.2 — ¿Conjunto de validación separado? ✅ **EL REVISOR TIENE RAZÓN, Y SE QUEDA CORTO**

**No existe ningún split de validación.** `src/hybrid.ipynb` (L529-570) ejecuta el barrido y selecciona con:

```python
m = metrics_at_k(fused_s, ks=(5, 10))     # sobre el MISMO set evaluado
if m["acc@1"] > best_acc:                 # selección por acc@1
    best_acc = m["acc@1"]; best_row = (...)
```

Tres hallazgos, no uno:

1. **Selección sobre el conjunto de test.** Confirmado. Aplica igualmente al barrido `(k1, b)` de BM25: el 0,9737 titular es el máximo de una rejilla de 62 configuraciones evaluadas y seleccionadas sobre las mismas 16.590 consultas.
2. **La métrica de selección no es la declarada.** §3.2.4 L449 dice *"selected based on **MRR@10**"*. El código selecciona por **`acc@1`**.
3. **La rejilla de β no es la declarada.** §3.2.4 L449 dice `β_exact ∈ {0.0, 0.05, 0.1}`. El código (L536-537) usa `beta_exact_grid = (0.10, 0.15)`, `beta_overlap_grid = (0.00, 0.05)`. **β_exact = 0,0 y 0,05 nunca se probaron.** Por eso "todas las configuraciones convergieron en β_exact = 0,1" (L857): 0,1 es el extremo inferior de la rejilla real. (Y hay una razón más profunda — §3.2.)

### 2.5 R2-4.2 y R2-4.3 — Tablas 14 y 15 ✅ **EL REVISOR TIENE RAZÓN EN AMBAS**

**Tabla 14 (distribución de tipos de error).** El paper afirma en §3.3.6 L534 y §4.6 L951 que analiza *"100 randomly sampled errors from each method"*. **Falso.** `src/error_analysis.ipynb` (L588-621) itera sobre **todos** los errores y calcula `100 * x / x.sum()` sobre el total. No hay muestreo de 100 en ninguna parte; `N_EXAMPLES = 5` es sólo el número de ejemplos ilustrativos escritos a disco.

Cifras exactas, de `eval/error_analysis/error_distribution.csv`:

| Tipo | BM25-unigram | BGE-M3-ColBERT | Híbrido |
|---|---|---|---|
| Numeric Mismatch | 98,148 % | 97,901 % | — |
| Lexical Confusion | 0,529 % | 0,501 % | — |
| Other | 1,323 % | 1,598 % | 100,0 % |

Suman 100,000 % exactos. **El "no suman 100" del revisor viene del redondeo a un decimal (98,1 + 0,5 + 1,3 = 99,9).** El clasificador (L565-577) define **cinco** categorías —`Numeric Mismatch`, `Near-Duplicate Error`, `Lexical Confusion`, `Ranking Failure`, `Other`— pero sólo tres aparecen porque las otras dos tienen frecuencia cero. Además esas cinco categorías **no coinciden** con las cuatro de §3.3.6 (que lista `Ranking Failure` pero no `Near-Duplicate`) ni con las cuatro de §4.6 L951 (que lista `Near-Duplicate` pero no `Ranking Failure`).

**Tabla 15 (errores jerárquicos).** De `eval/error_analysis/diagnostics_parent_item.csv`:

```
method,n_queries,acc1,right_parent_wrong_item_rate,parent_wrong_rate,no_parent_in_topK_rate
bm25_unigram,5844,0.8706,0.10352,0.02584,0.00103
hyb_bm25_uni__bge_colbert__tfidf_char_3_5,5844,0.6105,0.35986,0.02960,0.0
bge_m3_colbert,5844,0.4538,0.54295,0.00325,0.0
```

**Los porcentajes son sobre el total de consultas, no sobre los errores.** Por eso no suman 100: suman la **tasa de error** de cada método (`1 − Acc@1`). BM25: 10,4+2,6+0,1 = 13,1 % ≈ 1−0,8706. ColBERT: 54,3+0,3+0,0 = 54,6 % ≈ 1−0,4538. Las categorías **sí** son mutuamente excluyentes; lo que falta es el 86,9 % / 45,4 % de aciertos. Respuesta al revisor: reetiquetar el encabezado y añadir una fila "Correcto en rango 1".

**Y un tercer problema que el revisor no vio:** `n_queries = **5.844**`, no 16.590. El análisis de errores se hizo sobre la **intersección** de consultas de los tres métodos (`error_analysis.ipynb` L295-304, *"Intersect query universe across selected methods"*). El paper no lo menciona. Ver §3.1.

### 2.6 R2-2.3 / R1-2 / R2-1.1 — Solape entre `resumen` y `texto` ✅ **LOS REVISORES TIENEN RAZÓN**

Ésta es la objeción central y hay que medirla, no argumentarla. Calculado sobre 20.000 pares alineados de `data/processed/OEB_resumen.json` y `OEB_texto.json`:

| Métrica | Valor |
|---|---|
| Cobertura léxica media (tokens de la query presentes literalmente en el target) | **94,09 %** |
| Cobertura léxica mediana | 94,74 % |
| Queries cuyo conjunto **completo** de tokens está contenido en el target | 7,72 % |
| **Cobertura numérica media** (números de la query presentes en el target) | **99,93 %** |
| **Queries en las que *todos* sus números aparecen en el target** | **99,93 %** |
| Queries con al menos un número | 99,81 % |
| Números por query (media) | 2,88 |

**Interpretación honesta:** el target contiene ~94 % de los tokens de la query y **prácticamente el 100 % de sus valores numéricos, literalmente**. El 97,4 % de BM25 no es sorprendente: la tarea es, en gran medida, contención léxica casi verbatim. Los revisores han identificado correctamente el problema.

**Matiz que sí juega a favor del paper:** que el target contenga los números no hace la tarea trivial, porque ~1.584 variantes por plantilla comparten vocabulario casi idéntico y difieren sólo en parámetros — de ahí que TF-IDF se quede en 0,56-0,71 y que BGE-M3-dense caiga a 0,127. Es un benchmark de *hard negatives* legítimo. **Pero es eso, y no un benchmark de consultas de usuario**, y el paper debe decirlo desde el título y el abstract, no en la última línea de las limitaciones.

### 2.7 R2-8.1 — Párrafo duplicado ✅ **CONFIRMADO**

Líneas **156 y 158** de `paper_28.tex` son **byte-idénticas** (verificado por comparación exacta). Corresponden a las líneas 106-123 del PDF.

### 2.8 R2-8.3 / 8.4 — Terminología y citas ✅ **CONFIRMADO**

- **Terminología** (recuentos en `paper_28.tex`): `variant` ×50, `family` ×25, `parent level` ×14, `template` ×11, `parent category` ×4, `parent document` ×2, `parent identification` ×1. Cinco términos para tres conceptos.
- **Citas como sujeto gramatical:** L189, L193, L195, L197, L203, L205, L207 (`~\cite{...} developed/applied/demonstrated...`).
- **Jacques de Sousa sin referencia:** L195. Confirmado, no hay `\cite` asociado.

---

## 3. Errores NO detectados por los revisores

Ordenados por gravedad. Los tres primeros son, en mi opinión, más serios que cualquier cosa que los revisores señalaron.

### 3.1 🔴 CRÍTICO — Se usaron **tres muestras de consultas distintas** presentadas como una sola

El paper afirma repetidamente que todo se evalúa sobre el mismo conjunto: L557 *"Both evaluations used the same test set of 16,590 queries"*, L727 *"evaluated in zero-shot mode on the same test set of 16,590 queries"*, y **todos** los captions de tabla dicen `n=16,590`.

Comparando los `query_item_key` de los ficheros `results_top100.jsonl.gz` (hash MD5 del conjunto ordenado de claves):

| Muestra | md5 | n | Runs |
|---|---|---|---|
| **A** | `efeae04c` | 16.590 | BM25 (×3 familias), TF-IDF (×5), PRF (×16), BGE-M3 dense/sparse/colbert, `dense_gte_instrQ` |
| **B** | `4a606808` | 16.590 | **`dense_e5`, `dense_gte`, `dense_es_hiiamsid`** |
| **C** | `5e8f55e5` | 16.590 | **ambos híbridos** (`hyb_bm25_uni__bge_colbert__tfidf_char_3_5`, `hyb_bm25_uni__bge_multi__tfidf_char_3_5`) |

Solapes: **A∩B = 7.859** (47 %), **A∩C = 5.844** (35 %), **B∩C = 5.748**, **A∩B∩C = 2.741**.

Consecuencias concretas:

- ✅ **La conclusión titular sobrevive.** BM25-params (0,9737) vs BGE-M3-ColBERT (0,4480) están **ambos en la muestra A**. La comparación léxico-vs-neuronal principal es válida.
- ❌ **E5 (0,134) está en la muestra B.** Todas las comparaciones BM25↔E5, y la Tabla 12, cruzan muestras.
- ❌ **Tabla 9 es inválida tal como se interpreta.** `GTE-direct` está en B y `GTE-instruct` en A. El paper concluye (L783) que *"the instruction-tuned variant unexpectedly degraded to 0.697"* comparando **dos conjuntos de consultas diferentes**.
- ❌ **Todos los resultados híbridos y de reranking (Tablas 11, 13, 14, 15, 16) están en la muestra C** y no son comparables con los de A.
- ❌ El `n_queries = 5.844` del análisis de errores (§2.5) es exactamente `A∩C` — es la consecuencia visible de este problema, y nadie lo interpretó como tal.

Es también la explicación del `16.589` que detectó el revisor: la muestra B pierde una consulta al calcular métricas y su split numérico es `16.557/32` en vez de `16.561/29`.

**Este es el hallazgo que habría hundido el paper en una segunda ronda aunque se hubiera corregido todo lo que pidieron los revisores.**

### 3.2 🔴 CRÍTICO — El *numeric parameter bonus* nunca se aplicó: es código muerto

§3.2.4 (L439) describe el bonus numérico como componente de diseño del híbrido, y la Tabla 11 lo parametriza (`β_exact = 0.1`, `β_overlap = 0.0`). Verificación directa sobre los ficheros `numeric_features.parquet` de **los 9 runs híbridos**:

```
numeric_exact  : min=0 max=0 mean=0.0  nonzero=0
numeric_overlap: min=0 max=0 mean=0.0  nonzero=0
```

**Causa raíz.** En `hybrid.ipynb` L323-324:

```python
def _nums(v):
    return [float(x) for x in v] if isinstance(v, list) else []
```

La columna `numbers` de `OEB_short_feats.parquet` / `OEB_long_feats.parquet` se almacena como **`numpy.ndarray`**, no como `list` (verificado: `type(...) = <class 'numpy.ndarray'>`, `isinstance(v, list) = False`). Por tanto `_nums()` devuelve siempre `[]`, `qset` siempre vacío, y `exact = 1 if (len(qset) > 0 and ...)` es **siempre 0**.

Consecuencias:

- El bonus numérico **no influyó en ningún resultado publicado**. β_exact y β_overlap multiplican cero.
- La frase L857 (*"All optimal configurations converged on β_exact=0.1 and β_overlap=0.0"*) no describe una convergencia: describe el desempate por orden de rejilla sobre un parámetro inerte.
- El paper presenta como aportación de diseño ("exact numeric matching as a complementary retrieval signal", L341) algo que nunca se ejecutó.

**Y hay un segundo bug latente detrás.** `numbers_long` se construye sólo desde `long_s`, los **16.590 ítems muestreados** (L185), no desde los 47.513 del corpus. El documento *gold* de cada consulta está siempre en esa muestra; el **65,2 %** de los distractores candidatos no (verificado sobre 3.976.273 pares: `doc_in_sample = False` en 0,6497). Si se arregla el bug de `list`/`ndarray` sin arreglar también esto, el bonus se concedería preferentemente al gold → **fuga de información del conjunto de test**. Hay que corregir los dos a la vez.

### 3.3 🔴 GRAVE — El baseline híbrido de la Tabla 13 procede de otro sistema

Tabla 13, fila *"Hybrid (BM25 + BGE-ColBERT + TF-IDF) — Baseline"*: `0.590 / 0.928 / 0.963 / 0.730`.

Esas cuatro cifras son, exactamente, el contenido de `runs/hybrids/**hyb_bm25_uni__bge_multi__tfidf_char_3_5**/best_from_sweep.json` — la fusión de **cinco vías**:

```json
{"acc@1": 0.5899336949969861, "recall@5": 0.9279083785412899,
 "recall@10": 0.9633514165159734, "mrr@10": 0.7295208913382583}
```

Pero las filas *Replace* y *Blend* de esa misma tabla se calcularon sobre `runs/hybrids/**hyb_bm25_uni__bge_colbert__tfidf_char_3_5**/` — la fusión de **tres vías** (verificado en `metrics_ce_replace.json` / `metrics_ce_blend.json`). **El baseline y las filas reranqueadas son de sistemas distintos.**

El baseline correcto para esas filas, calculado por mí directamente desde `runs/hybrids/hyb_bm25_uni__bge_colbert__tfidf_char_3_5/results_top100.jsonl.gz` (16.590 consultas):

| | Acc@1 | R@5 | R@10 | MRR@10 |
|---|---|---|---|---|
| **Baseline correcto** | **0,6077** | **0,8530** | **0,9613** | **0,7178** |
| Publicado (erróneo) | 0,590 | 0,928 | 0,963 | 0,730 |

Nota adicional: ese fichero persistido es la fusión **COMBSUM sin pesos** (`meta.fusion = "combsum"`, `beta_exact = 0.15`, `beta_overlap = 0.05`), **no** la configuración óptima ponderada de la Tabla 11 (`BM25 0,879 / ColBERT 0,012 / TF-IDF 0,110`, cuyo Acc@1 es 0,8896). Es decir: **el cross-encoder se aplicó sobre el híbrido sin optimizar**, mientras la Tabla 11 reporta el optimizado. Dos sistemas, un mismo nombre.

**Impacto en las conclusiones.** L944 afirma *"The hybrid system with blend reranking achieved the highest overall performance: 0.799 Acc@1"*. Frente al híbrido de 3 vías **optimizado** (0,8896), el reranking **degrada** el sistema en −0,091. Y frente a BM25-params (0,9737) está 17,5 puntos por debajo. La afirmación sólo es cierta dentro de la Tabla 13.

### 3.4 🟠 GRAVE — E5 se ejecutó con el prefijo equivocado

§3.2.3 L407: *"Following the model documentation, queries receive the prefix `query: ` and documents receive `passage: `"*.

`configs/dense_e5.yaml`:

```yaml
model_name: intfloat/multilingual-e5-base
add_query_prefix: true
query_prefix: "query: Busca el documento que más se parezca a la siguiente consulta: "
```

**El prefijo real es la instrucción larga en español**, idéntica a la de `dense_gte_instrQ.yaml` — un copy-paste evidente. Los modelos E5 son notoriamente sensibles al prefijo `query: ` exacto durante el preentrenamiento asimétrico. El 0,134 de E5 está medido con una configuración que el propio paper declara no haber usado, y el paper concluye a partir de ahí (L1094) que *"dense retrievers generalize poorly without fine-tuning"*.

Esto es exactamente el tipo de fallo que un revisor de una revista de IR encontraría y que convertiría el rechazo en algo mucho peor. Hay que reejecutar E5 con `query_prefix: "query: "`.

### 3.5 🟠 Nombres de modelos incorrectos en tres tablas

| Paper | Config real | Fuente |
|---|---|---|
| "E5-large" (Tabla 8, filas), "multilingual-e5-large" (Tabla 12) | **`intfloat/multilingual-e5-base`** | `configs/dense_e5.yaml` |
| "GTE-large-en-v1.5" (Tablas 9, 12) | **`Alibaba-NLP/gte-multilingual-base`** | `configs/dense_gte.yaml` |
| "GTE-Qwen2-instruct" (Tabla 9) | **`Alibaba-NLP/gte-multilingual-base`** + prefijo instruct | `configs/dense_gte_instrQ.yaml` |

Ninguno de los modelos `gte-large-en-v1.5` ni `gte-Qwen2-instruct` se usó en ningún experimento. Además **§3.2.3 L407 dice `-base` correctamente mientras las tablas dicen `-large`**: el paper se contradice consigo mismo. Y `gte-large-en-v1.5` es un modelo **sólo inglés**: un lector concluiría razonablemente que el 1,3 % de Acc@1 se debe a haber aplicado un modelo inglés a texto español, lo cual no es lo que ocurrió.

### 3.6 🟠 Tabla 13: MRR@10 del baseline BM25 = 1.000

Fila *BM25 (unigram) — Baseline*: `0.869 / 0.931 / 0.950 / **1.000**`. Un MRR@10 de 1,000 con Acc@1 de 0,869 es imposible por definición.

**Valor correcto: 0,8978** (`runs/bm25_unigram__k1-0.80__b-0.35/metrics_dual.json`; 0,8957 recalculado desde el fichero top-100). Además R@5 debería ser **0,932** (0,9322), no 0,931.

### 3.7 🟠 Profundidad de reranking: se declara 100 (y "20, 50 o 100"), se ejecutó 50

- §3.2.4 L457: *"Reranking depth: Top 20, 50, or 100 candidates"*
- §4.5 L914: *"applied to the top-100 candidates"*

**Real: K′ = 50, y sólo 50.** `cross_encoder.ipynb` log: `[CANDS] Loaded 829,500 pairs across 16,590 queries at K'=50` (829.500 / 16.590 = 50). Todos los ficheros de salida son `results_top**50**_ce_{replace,blend}.jsonl.gz`. No existe ningún run a 20 ni a 100.

### 3.8 🟡 Precisión no numérica de BGE-M3 mal leída de la tabla

L822: *"On non-numeric queries, ColBERT and sparse modes achieved perfect accuracy (1.000)"*.

**Falso.** De `runs/*/metrics_dual.json`, `scope = no_numbers` (n=29):

| Modo | Acc@1 real | El 1,000 del paper es… |
|---|---|---|
| BGE-M3-colbert | **0,7586** | su Recall@5 y Recall@10 |
| BGE-M3-dense | **0,7586** | ídem |
| BGE-M3-sparse | **0,6552** | ídem |

Se leyó la columna equivocada. (En cambio L754 —E5 no numérico 0,875— **sí es correcto**: `dense_e5`, `no_numbers`, n=32, Acc@1 = 0,8750. Pero es la muestra B, con 32 consultas no numéricas en lugar de 29 — otra manifestación de §3.1.)

### 3.9 🟡 Un modelo neuronal descrito y nunca reportado

§3.2.3 L409-410 describe `hiiamsid/sentence_similarity_spanish_es` como una de las siete configuraciones neuronales (y el 7 de la Tabla 2 sólo cuadra contándolo). **No aparece en ninguna tabla de resultados.**

Existe y está evaluado: `runs/dense_es_hiiamsid/metrics_dual.json` → **item Acc@1 = 0,0244**, parent Acc@1 = 0,3952. Es el peor modelo de todos. Omitirlo sin decirlo es selección de resultados; incluirlo refuerza el argumento del paper.

### 3.10 🟡 PRF: 16 configuraciones ejecutadas, 12 reportadas, "seis" declaradas

- Tabla 2: `Pseudo-Relevance Feedback — 16`
- §3.2.2 L395: *"yielding 8 configurations each (the two weakest β=0.7, N=40 variants are omitted for brevity)"*
- §4.2.1 L662: *"**Six** configurations each were evaluated"* ← incorrecto: se **evaluaron** ocho, se **reportan** seis

Verificado: existen los 16 runs en disco (8 RM3 + 8 Rocchio). Las dos ausentes de cada tabla son `M=5,N=40,β=0.7` y `M=10,N=40,β=0.7`, coherente con L395.

### 3.11 🟡 Inconsistencia en la mejor configuración de RM3

Tabla 7 la identifica como `M=10, N=20, λ=0.5`; Tabla 16 como `M=5, N=20, λ=0.5`. Ambas tienen Acc@1 = 0,8699 en la Tabla 6 (empate real), pero deben nombrarse igual.

### 3.12 🟡 "Duplicados en el espacio de embeddings" de BM25

L1042: *"BM25 produced 3,276 duplicate documents across 1,602 duplicate groups **in its embedding space**"*.

Las cifras son correctas (`eval/error_analysis/duplicates_summary.csv`: `bm25_unigram,47513,1602,3276`), pero BM25 no tiene espacio de embeddings. Es duplicación de representaciones dispersas / textos indexados. Error conceptual visible para cualquier revisor de IR.

### 3.13 🟡 Afirmación sin soporte sobre Recall@5 y MRR

L1086: *"under those metrics, hybrid configurations show comparatively stronger performance relative to the lexical baseline, **as reflected in Table 16**"*.

La Tabla 16 **no contiene Recall@5**, y en MRR el orden es el mismo que en Acc@1: BM25-params 0,979 > mejor híbrido 0,908. La tabla citada no respalda la afirmación. (Sí es cierto que el híbrido+blend alcanza R@5 = 0,985 frente a 0,932 de BM25-unigram — pero frente a BM25-**params** es 0,985 vs 0,985. Empate, no ventaja.)

### 3.14 🟢 Menores

- L1073 llama *"default"* a `k1=0.80, b=0.35`. Los valores por defecto de Lucene son `k1=1.2, b=0.75`; ésos son los **seleccionados** por el barrido.
- L568: "26.6 percentage point gap" → 0,9737 − 0,7083 = **26,5 pp**.
- `OEB_resumen.json` / `OEB_texto.json` contienen **47.514** registros; el paper dice 47.513. La diferencia es el registro raíz `OEB#` ("ZANJAS, CANALIZACIONES Y TUBOS"), que no es un ítem. La cifra del paper es correcta pero conviene documentar el filtrado.
- Título de sección repetido: §4.5 y §4.6 usan *"Cross-Encoder Reranking"* y *"Error Analysis"* también como subsecciones del apéndice.

---

## 4. Qué piden, por qué lo piden, y cómo corregirlo

### 4.1 El eje del rechazo

El Editor Asociado resume: *"limited alignment with the domain of construction (practical impact), little novelty, and several technical concerns"*. Los tres apuntan al mismo sitio:

> El paper vende una **evaluación de recuperación con consultas de profesional** y entrega una **evaluación de emparejamiento catálogo-a-catálogo**. Lo segundo es defendible y útil; lo primero no está evaluado en ningún sitio.

La Introducción (L152) construye dos escenarios operativos —estimación de costes y partes de obra— con terminología variable, abreviaturas y parámetros omitidos. Ninguno se evalúa. La query es el campo `resumen` del **mismo registro** que el target, con **94 % de solape léxico y 99,93 % de solape numérico** (§2.6). Los revisores llegaron a esta conclusión por intuición; los datos les dan la razón con más fuerza de la que ellos supusieron.

### 4.2 Estrategia de corrección: dos caminos

**Camino 1 — Reencuadrar (rápido, riesgo medio).** Reposicionar el paper como *benchmark controlado de recuperación con negativos duros en catálogos paramétricos*, no como evaluación de búsqueda por profesionales. Cambiar título, abstract, contribuciones y conclusiones. Añadir §2.6 como caracterización explícita del benchmark. Corregir todos los defectos de §2 y §3. **No resuelve la objeción de novedad del AE**, y AiC probablemente lo siga viendo fuera de alcance.

**Camino 2 — Añadir el eslabón que falta (lento, riesgo bajo).** Todo lo anterior **más** un conjunto de consultas realistas. Tres opciones por coste creciente:

1. **Perturbaciones controladas** de los `resumen`: eliminar parámetros, abreviar (`polietileno`→`PE`), parafrasear, reordenar, introducir sinónimos de obra. Barato, reproducible, y convierte la crítica en una contribución (curva de degradación por tipo de perturbación). Es lo que pide R1-3 literalmente.
2. **Consultas generadas por LLM** con el estilo de un parte de obra, validadas por muestreo manual.
3. **Consultas reales de estimadores** de Telice (n = 200-500 basta). Es lo que pide R2-7.1 y lo que daría al paper el *practical impact* que reclama el AE.

Con (1) + (3), el paper pasa de "benchmark que favorece a BM25" a "benchmark que mide **cuándo** BM25 deja de ganar" — que es un resultado publicable en AiC.

### 4.3 R2-final (baseline estructurado): **ya lo tienes casi hecho**

El Revisor #2 pregunta si un filtrado por reglas sobre los atributos estructurados no sería un baseline fuerte. En `runs/` hay 13 pipelines de ese tipo (de la línea `lightweight-extraction-ner`, marzo-abril 2026, **anteriores al envío**), sobre las **mismas 16.590 consultas**:

| Pipeline | Acc@1 | R@10 | MRR | Fecha |
|---|---|---|---|---|
| `structured_pipeline_oracle_rules` | 0,9136 | 0,9777 | 0,9272 | 2026-03-11 |
| `structured_pipeline_rules` | **0,9033** | 0,9670 | 0,9168 | 2026-03-11 |
| `structured_pipeline_oracle_phi4_classify` | 0,8863 | 0,8876 | 0,8867 | 2026-03-13 |
| `structured_pipeline_phi4_classify` | 0,8771 | 0,8781 | 0,8774 | 2026-03-13 |
| `structured_pipeline_oracle` | 0,8206 | 0,9866 | 0,8695 | 2026-03-12 |
| `structured_pipeline` | 0,8089 | 0,9719 | 0,8566 | 2026-03-12 |
| `structured_pipeline_classifier` | 0,2093 | 0,2125 | 0,2107 | 2026-04-16 |
| `structured_pipeline_bio_tagger` | 0,0310 | 0,2575 | 0,1029 | 2026-04-30 |

**Es una respuesta excelente:** el mejor pipeline estructurado por reglas alcanza 0,9033 (0,9136 con oráculo de extracción) frente a **0,9737 de BM25-params**. Es decir: *"lo hemos hecho, y la recuperación textual gana al emparejamiento estructurado por reglas incluso dándole extracción perfecta"*. Eso convierte una objeción en una sección de resultados.

⚠️ **Antes de usarlo**: verificar que esos runs usan la muestra A (§3.1) y que su código está en un tag reproducible — pertenecen a otra línea de trabajo y **no** están cubiertos por `bc3-ir-paper-v1.0.0`.

### 4.4 R1-4 (HyDE): pendiente, pero barato

No hay ningún run de HyDE ni de reescritura de consultas. Con el corpus ya indexado, añadir HyDE sobre BM25 y sobre BGE-M3-ColBERT es un experimento de un día. Y hay una predicción clara que hacer: **en un benchmark con 94 % de solape léxico, HyDE debería perjudicar**, porque introduce texto generado que diluye la coincidencia exacta. Reportarlo con esa explicación es más fuerte que omitirlo.

### 4.5 R1-1 / AE (novedad): qué se puede argumentar

R1 admite que *"benchmarking studies can be valuable"*. Lo defendible: primer benchmark de recuperación ítem a ítem sobre catálogo paramétrico de construcción, en español, con datos y código abiertos (R2-6.1 lo señala explícitamente como fortaleza). Lo no defendible con el manuscrito actual: llamarlo "guía empírica para profesionales". La novedad hay que apoyarla en (a) el recurso liberado, (b) el hallazgo del colapso ítem↔padre en modelos densos —que es genuino y está bien medido—, y (c) los baselines estructurados de §4.3, que sí constituyen una comparación que nadie ha hecho en este dominio.

---

## 5. Recomendación

1. **No reenviar a AiC sin el experimento de consultas realistas.** El rechazo del AE es de encaje, y una segunda versión que sólo corrija números recibirá el mismo veredicto.
2. **Corregir §3.1 y §3.2 antes que nada.** Son defectos que invalidan tablas, no erratas. Si el paper se reenvía a cualquier revista con revisores de IR y siguen ahí, el resultado será peor que este rechazo.
3. **Reejecutar la evaluación completa sobre una única muestra de consultas**, con semilla y fichero de IDs versionado en el repo. Es la corrección de mayor impacto por unidad de esfuerzo.
4. **Incorporar los baselines estructurados** (§4.3): convierte la objeción más difícil del Revisor #2 en un resultado a favor.
5. Considerar revistas alternativas si el reencuadre como benchmark se consolida: *Advanced Engineering Informatics*, *Journal of Computing in Civil Engineering*, o un track de recursos/benchmarks.

---

# Anexo — Parches referenciados a `docs/reviews/paper_28.tex`

Dos bloques: **A. Sólo edición de texto** (aplicable de inmediato) y **B. Exige reejecutar**.

## A. Sólo edición de texto

| # | Línea(s) | Problema | Corrección | Origen |
|---|---|---|---|---|
| A1 | **158** | Párrafo idéntico al de la L156 | **Eliminar la línea 158 completa** (y la 157 en blanco) | R2-8.1 |
| A2 | **518-520** | `HAS_NUM (24,711, 62%)` / `NO_NUM (15,136, 38%)` — cifras de la versión de 39.847 ítems | `HAS\_NUM (16,561 queries, 99.83\%)` / `NO\_NUM (29 queries, 0.17\%)` | R2-2.1 |
| A3 | **631** | Caption Tabla 4: *"16,076 queries with numbers (99.83%)"* | `16,561 queries with numbers (99.83\%) and 29 queries without numbers (0.17\%)` | R2-2.1 |
| A4 | **530** | *"We apply Bonferroni correction"* | `We apply Holm--Bonferroni correction` | R2-3.1 |
| A5 | **587** | *"(10,000 iterations, Bonferroni correction)"* + *"p < 0.003"* | `(10,000 iterations, Holm--Bonferroni correction)`; sustituir `p<0.003` por los `p_holm` de `eval/bootstrap_lexical/bootstrap_sigtests_pairs.csv` | R2-3.1 |
| A6 | **534** | *"we analyze 100 randomly sampled errors from each method family"* | `we analyze all failed queries for each of three representative methods (BM25-unigram, BGE-M3-ColBERT and the hybrid), restricted to the 5,844 queries common to the three runs` | R2-4.2 |
| A7 | **951** | *"error analysis on 100 randomly sampled failures per method"* + 4 categorías | Igual que A6. Unificar el taxón con L536-544: **cinco** categorías (`Numeric Mismatch`, `Near-Duplicate Error`, `Lexical Confusion`, `Ranking Failure`, `Other`), señalando que dos tienen frecuencia cero | R2-4.2 |
| A8 | **959** | Caption Tabla 14: *"$n=100$ per method"* | `(\% of all failed queries; BM25 $n{=}756$, ColBERT $n{=}3{,}192$, Hybrid $n{=}2{,}276$ over the 5,844 common queries)` — recalcular los $n$ desde `diagnostics_parent_item.csv` | R2-4.2 |
| A9 | **966-968** | Suman 99,9 % por redondeo | Usar dos decimales (98,15 / 0,53 / 1,32 y 97,90 / 0,50 / 1,60) y añadir nota de que las categorías vacías se omiten | R2-4.2 |
| A10 | **989** | Caption Tabla 15 sugiere % de errores | `Hierarchical error patterns as a percentage of \emph{all} queries ($n=5{,}844$ common to the three methods). Categories are mutually exclusive; the complement of their sum is the rank-1 accuracy.` | R2-4.3 |
| A11 | **991-1000** | Tabla 15 sin fila de aciertos | Añadir fila `Correct at rank 1 & 87.1\% & 45.4\% & 61.1\%` (de `diagnostics_parent_item.csv`) para que sume 100 % | R2-4.3 |
| A12 | **407** | *"queries receive the prefix `query: `"* — falso para el run realizado | Ver **B4**. Si no se reejecuta, sustituir por el prefijo real y discutirlo como limitación | **No detectado** |
| A13 | **731, 735, 743, 837, 1080** | "E5-large" / "multilingual-e5-large" | `multilingual-e5-base` en todas | **No detectado** |
| A14 | **771-772, 776-777, 838** | "GTE-large-en-v1.5", "GTE-Qwen2-instruct" | `GTE-multilingual-base (direct)` y `GTE-multilingual-base (instruct)` | **No detectado** |
| A15 | **927** | `MRR@10 = 1.000` para el baseline BM25 | **`0.898`**. Corregir también R@5: `0.931` → **`0.932`** | **No detectado** |
| A16 | **936-937** | Fila híbrida: etiqueta de 3 vías, cifras de 5 vías | Etiqueta: `Hybrid (unweighted COMBSUM: BM25 + BGE-ColBERT + TF-IDF char)`. Baseline: **`0.608 / 0.853 / 0.961 / 0.718`** | **No detectado** |
| A17 | **914** | *"top-100 candidates"* | `top-50 candidates` | **No detectado** |
| A18 | **457** | *"Reranking depth: Top 20, 50, or 100"* | `Reranking depth: top 50 candidates` | **No detectado** |
| A19 | **449** | Rejilla `β_exact ∈ {0.0, 0.05, 0.1}`, selección por MRR@10 | `\beta_{exact} \in \{0.10, 0.15\}`, `\beta_{overlap} \in \{0.00, 0.05\}`; selección por **Acc@1**. Ver **B2**/**B5** | R2-3.2 |
| A20 | **857, 861** | *"All optimal configurations converged on β_exact=0.1"* | Eliminar la afirmación de convergencia. Ver **B2** | **No detectado** |
| A21 | **822** | *"ColBERT and sparse achieved perfect accuracy (1.000)"* | `ColBERT and dense reached Acc@1 = 0.759 and sparse 0.655 on the 29 non-numeric queries (their Recall@5 and Recall@10 are 1.000)` | **No detectado** |
| A22 | **849-853, Tabla 12** | `hiiamsid` descrito y no reportado | Añadir fila `hiiamsid/sentence_similarity_spanish_es & 0.024 & 0.395` (item / parent) | **No detectado** |
| A23 | **662** | *"Six configurations each were evaluated"* | `Eight configurations each were evaluated; the six best are reported (the two \beta=0.7, N=40 variants are omitted, see Section 3.2.2)` | **No detectado** |
| A24 | **714 vs 1072** | Mejor RM3: `M=10` en Tabla 7, `M=5` en Tabla 16 | Unificar (empate en 0,8699; elegir uno y anotar el empate) | **No detectado** |
| A25 | **1042** | *"in its embedding space"* aplicado a BM25 | `among its indexed sparse representations` | **No detectado** |
| A26 | **1086** | Afirmación sobre R@5/MRR no soportada por la Tabla 16 | Reescribir: en MRR el orden no cambia; en R@5 el híbrido+blend (0,985) iguala a BM25-params (0,985) y supera a BM25-unigram (0,932) | **No detectado** |
| A27 | **944** | *"the hybrid system with blend reranking achieved the highest overall performance"* | Acotar a *"the highest performance among the reranked systems evaluated in Table 13"* | **No detectado** |
| A28 | **1073** | `BM25-unigram (default, k1=0.80, b=0.35)` | `(swept optimum, k1=0.80, b=0.35)` — los defaults de Lucene son k1=1,2 / b=0,75 | **No detectado** |
| A29 | **568** | "26.6 percentage point gap" | `26.5` | **No detectado** |
| A30 | **195** | "Jacques de Sousa et al." sin `\cite` | Añadir la referencia | R2-8.4 |
| A31 | **189, 193, 195, 197, 203, 205, 207** | `~\cite{...} developed/applied...` como sujeto | Anteponer el nombre de autor: `Wu et al.~\cite{...} developed…` | R2-8.3 |
| A32 | **574, 645, 646, 767-770, 773 + abstract** | 5 términos para 3 conceptos | Fijar: **template** (definición paramétrica), **item/variant** (instancia), **parent** (nivel de agrupación). Eliminar "family" o declararlo sinónimo único de "parent" en el glosario | R2-8.3 |
| A33 | **221-223, 1108** | Alcance no delimitado | Explicitar en Métodos: subcategoría OEB, 30 plantillas, dominio homogéneo, consultas derivadas del catálogo | R2-1.2 |
| A34 | **1115** | *"Neural models … consistently fail"* vs L1094 (comparación asimétrica) | `the tested zero-shot neural models performed substantially worse than the domain-tuned BM25 model on this benchmark` | R2-5.2 |
| A35 | **1085, 1115-1116, abstract** | Generalización excesiva | Acotar a "este catálogo ferroviario español, con consultas derivadas del propio catálogo" | R1-5.2, R2-5.1 |
| A36 | **1108-1109** | Falta la limitación de validez externa | Añadir: *"queries are derived from the same catalog as the retrieval targets and are not independent descriptions written by estimators, engineers or field staff"* | R2-7.1 |
| A37 | **169-177** | Falta acotar la contribución | Añadir: *"the primary contribution is an empirical comparison within the selected benchmark rather than a new retrieval method"* | R1-7.1 |
| A38 | **§4 completo (555-1086)** | Comparaciones numéricas repetidas ya visibles en tablas | Recortar ~30 %; mover detalle de configuraciones a material suplementario | R2-8.2 |
| A39 | **Nueva figura tras L345** | Falta visión general metodológica | Diagrama de flujo alineado con §3.1-§3.4: dataset → muestreo → indexación → familias de métodos → fusión/reranking → evaluación dual | R2-4.1 |
| A40 | **Nueva subsección en §3.1** | Falta cuantificar el solape `resumen`/`texto` | Insertar la tabla de §2.6 de este informe (94,09 % léxico / 99,93 % numérico) | R2-2.3 |
| A41 | **1127-1135** | Fortaleza infravalorada | Destacar la liberación de datos, queries, etiquetas, salidas y configs como contribución de benchmark | R2-6.1 |

## B. Exige reejecutar

| # | Qué | Por qué | Alcance | Prioridad |
|---|---|---|---|---|
| **B1** | **Unificar la muestra de consultas.** Reejecutar `dense_e5`, `dense_gte`, `dense_es_hiiamsid` y **ambos híbridos** (y el cross-encoder sobre ellos) con el conjunto de IDs de la **muestra A**. Versionar el fichero de IDs en el repo | Hoy conviven 3 muestras distintas (§3.1); Tablas 8, 9, 11, 12, 13, 14, 15, 16 y Fig. `acc1_by_family` mezclan poblaciones | 5 runs neuronales + 4 híbridos + 3 CE | 🔴 **Máxima** |
| **B2** | **Arreglar el bonus numérico y reejecutar el barrido híbrido.** (a) `_nums()`: aceptar `np.ndarray` además de `list`; (b) construir `numbers_long` sobre los **47.513** documentos, no sobre los 16.590 muestreados | Hoy `numeric_exact ≡ numeric_overlap ≡ 0` en los 9 runs (§3.2): el componente está descrito en el paper y nunca se ejecutó. Arreglar sólo (a) introduciría fuga de test | `hybrid.ipynb` L185, L323-324; 4 barridos | 🔴 **Máxima** |
| **B3** | **Split de validación.** Partir las 16.590 en validación (p.ej. 30 %) y test (70 %). Seleccionar `(k1,b)` de BM25, pesos de fusión y β **en validación**; reportar **sólo test** | Hoy toda la selección de hiperparámetros es sobre el conjunto reportado (§2.4). Afecta al 0,9737 titular | `hybrid.ipynb` L529-570 + barridos BM25 | 🔴 **Alta** — R2-3.2 |
| **B4** | **Reejecutar E5** con `query_prefix: "query: "` y `doc_prefix: "passage: "` | `configs/dense_e5.yaml` usa el prefijo instruct en español (§3.4); el paper afirma lo contrario y concluye sobre modelos densos a partir de ese número | 1 config + 1 run | 🟠 **Alta** |
| **B5** | **PRF sobre el baseline fuerte.** Reejecutar los 16 runs de PRF con `bm25_unigram_params k1=0.60 b=0.35` | El revisor lo pide explícitamente; hoy L653 es falsa (§2.2) | 16 runs (baratos) | 🟠 **Alta** — R2-2.2 |
| **B6** | **Baseline estructurado.** Integrar los `structured_pipeline*` (§4.3), verificando que usan la muestra A y fijando un tag reproducible | Responde a la pregunta final de R2; el resultado (0,9033 vs 0,9737) favorece al paper | Ya ejecutado; falta verificar e integrar | 🟠 **Alta** — R2-final |
| **B7** | **Consultas realistas.** Perturbaciones controladas de los `resumen` (supresión de parámetros, abreviaturas, paráfrasis, sinónimos) + idealmente un conjunto de consultas reales de estimadores | Es la objeción central de R1-3, R2-1.1 y R2-7.1, y el eje del rechazo del AE (§4.1-§4.2) | Nuevo experimento | 🔴 **Máxima si se reenvía a AiC** |
| **B8** | **HyDE / reescritura de consultas** sobre BM25 y BGE-M3-ColBERT | R1-4. Barato con los índices ya construidos; predicción defendible incluso si empeora (§4.4) | 2-4 runs | 🟡 Media — R1-4 |
| **B9** | **Reranking a profundidades 20 y 100** | Sólo se ejecutó K′=50 (§3.7). O se ejecutan, o se corrige la declaración (A17/A18) | 4 runs | 🟡 Baja |
| **B10** | **Parent-level para híbridos y reranking** | Hoy aparecen como "n/a" en Fig. `acc1_by_family` (L1049) | Recalcular métricas, sin re-retrieval | 🟡 Baja |

---

### Nota de reproducibilidad

Antes de tocar el manuscrito conviene crear una rama desde `bc3-ir-paper-v1.0.0` y aplicar allí las correcciones de código (B1-B5), para que los números nuevos sean trazables frente a los publicados. El árbol actual está en `research/synthetic-oe`, cuya `data/` ya contiene el corpus OE de otra línea de trabajo.

**Fuentes principales:** `docs/reviews/paper_28.tex` · `src/{hybrid,error_analysis,bootstrap_sigtests,cross_encoder,eval}.ipynb` · `configs/dense_{e5,gte,gte_instrQ,es_hiiamsid}.yaml` · `runs/*/metrics_dual.json` · `runs/hybrids/*/{best_from_sweep.json,numeric_features.parquet,results_top100.jsonl.gz}` · `runs/*/metrics_ce_{replace,blend}.json` · `eval/error_analysis/{error_distribution.csv,diagnostics_parent_item.csv,duplicates_summary.csv}` · `data/processed/OEB_{resumen,texto}.json` · `data/processed/OEB_{short,long}_feats.parquet`
