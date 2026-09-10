# Registro de correcciones — AUTCON-D-26-03592

Seguimiento de todos los defectos identificados en el manuscrito enviado a
*Automation in Construction* y de las correcciones aplicadas en la rama
`paper/autcon-r1-revision`.

**Estados:** `pendiente` · `en curso` · `hecho` · `descartado` (con motivo)

**Origen:** `R1`/`R2`/`AE` = señalado por revisor o editor · `informe` = detectado en
`AUTCON_analisis_revision.md` · `sesión` = detectado al verificar el informe contra el
código.

Referencias de línea relativas a `paper/paper_28.tex` tal como se envió
(commit `223a2f0`, idéntico al enviado el 2026-06-24).

---

## Bloque A — Correcciones de texto

| # | Línea | Problema | Corrección | Origen | Estado |
|---|---|---|---|---|---|
| A1 | 158 | Párrafo idéntico al de la 156 | Eliminar L158 y la línea en blanco 157 | R2-8.1 | hecho |
| A2 | 518-520 | `HAS_NUM (24,711, 62%)` / `NO_NUM (15,136, 38%)`: cifras de la versión de 39.847 ítems | `16,561 (99.83%)` / `29 (0.17%)` | R2-2.1 | hecho |
| A3 | 631 | Caption Tabla 4: *"16,076 queries with numbers"* | `16,561` (el 99,83 % sí es correcto) | R2-2.1 | hecho |
| A4 | 530 | *"We apply Bonferroni correction"* | `Holm--Bonferroni` | R2-3.1 | hecho |
| A5 | 587 | *"Bonferroni"* + umbral `p < 0.003` | `Holm--Bonferroni`; reportar los `p_holm` de `eval/bootstrap_lexical/bootstrap_sigtests_pairs.csv` | R2-3.1 | hecho |
| A6 | 534 | *"100 randomly sampled errors from each method family"*: nunca hubo muestreo | Describir el análisis real (todos los fallos, muestra común) | R2-4.2 | hecho |
| A7 | 951 | Ídem + taxonomía de 4 categorías | Unificar con L536-544: cinco categorías, dos con frecuencia cero | R2-4.2 | hecho |
| A8 | 959 | Caption Tabla 14: `$n=100$ per method` | `%` de fallos reales, con los `n` por método | R2-4.2 | hecho |
| A9 | 966-968 | Suman 99,9 % por redondeo a un decimal | Dos decimales + nota de categorías vacías | R2-4.2 | hecho |
| A10 | 989 | Caption Tabla 15 sugiere % sobre errores | Son % sobre *todas* las consultas; categorías mutuamente excluyentes | R2-4.3 | hecho |
| A11 | 991-1000 | Tabla 15 no suma 100 % | Añadir fila *Correct at rank 1* | R2-4.3 | hecho |
| ~~A12~~ | 407 | ~~Prefijo de E5 erróneo~~ | **Descartado**: `src/retrievers/dense_e5.py:101-102` fija `"query: "` a mano e ignora el YAML. El paper es correcto; lo que se corrige es el YAML (→ C7) | informe | descartado |
| A13 | 731, 735, 743, 837, 1080 | "E5-large" / "multilingual-e5-large" | `multilingual-e5-base` | sesión | hecho |
| A14 | 771-772, 776-777, 838 | "GTE-large-en-v1.5", "GTE-Qwen2-instruct": modelos nunca usados, uno de ellos sólo inglés | `GTE-multilingual-base (direct)` / `(instruct)` | sesión | hecho |
| A15 | 927 | `MRR@10 = 1.000` con Acc@1 = 0,869: imposible por definición | `0.898`; R@5 `0.931` → `0.932` | sesión | hecho |
| A16 | 936-937 | Fila híbrida: etiqueta de 3 vías, cifras de la fusión de 5 vías | Etiqueta y baseline correctos del sistema de 3 vías | sesión | hecho |
| A17 | 914 | *"top-100 candidates"* | `top-50` (o ampliar a 20/50/100, → R5) | sesión | hecho |
| A18 | 457 | *"Reranking depth: Top 20, 50, or 100"*: sólo se ejecutó 50 | Declarar las profundidades realmente evaluadas | sesión | hecho |
| A19 | 449 | Rejilla `β_exact ∈ {0.0, 0.05, 0.1}` y selección por MRR@10; el código usa `(0.10, 0.15)` y `acc@1` | Declarar la rejilla y el criterio reales (→ C4, C5) | R2-3.2 | hecho |
| A20 | 857, 861 | *"All optimal configurations converged on β_exact=0.1"*: describe un desempate sobre un parámetro inerte | Eliminar la afirmación; rehacer con el bonus ya operativo (→ C3) | sesión | hecho |
| A21 | 822 | *"ColBERT and sparse achieved perfect accuracy (1.000)"*: se leyó la columna de Recall | Acc@1 reales: 0,759 / 0,759 / 0,655 sobre las 29 consultas no numéricas | sesión | hecho |
| A22 | 849-853, Tabla 12 | `hiiamsid` descrito en Métodos y ausente de resultados | Añadir su fila (item 0,024 / parent 0,395) | sesión | hecho |
| A23 | 662 | *"Six configurations each were evaluated"* | Se evaluaron ocho; se reportan seis | sesión | hecho |
| A24 | 714 vs 1072 | Mejor RM3: `M=10` en Tabla 7, `M=5` en Tabla 16 | Unificar y anotar el empate (ambas 0,8699) | sesión | hecho |
| A25 | 1042 | *"in its embedding space"* aplicado a BM25 | BM25 no tiene espacio de embeddings | sesión | hecho |
| A26 | 1086 | Afirmación sobre R@5/MRR no soportada por la Tabla 16 | Reescribir con lo que la tabla sí muestra | sesión | hecho |
| A27 | 944 | *"the highest overall performance"* para el híbrido+blend | Acotar al ámbito de la Tabla 13 | sesión | hecho |
| A28 | 1073 | `BM25-unigram (default, k1=0.80, b=0.35)` | Es el óptimo del barrido, no un valor por defecto. **Reformulado**: no cabe invocar los defaults de Lucene porque no se usó Lucene (→ N1) | sesión | hecho |
| A29 | 568 | "26.6 percentage point gap" | `26.5` (0,9737 − 0,7083) | sesión | hecho |
| A30 | 195 | "Jacques de Sousa et al." sin `\cite` | Añadir la referencia | R2-8.4 | hecho |
| A31 | 189, 193, 195, 197, 203, 205, 207 | `~\cite{...}` como sujeto gramatical | Anteponer el nombre de los autores | R2-8.3 | hecho |
| A32 | 574, 645-646, 767-770, 773, abstract | Cinco términos para tres conceptos | Fijar **template** / **item-variant** / **parent** | R2-8.3 | hecho |
| A33 | 221-223, 1108 | Alcance del estudio no delimitado | Explicitar subcategoría, plantillas y procedencia de las consultas | R2-1.2 | hecho |
| A34 | 1115 | *"Neural models … consistently fail"* frente a la asimetría admitida en L1094 | Acotar a los modelos zero-shot evaluados en este benchmark | R2-5.2 | hecho |
| A35 | 1085, 1115-1116, abstract | Generalización excesiva | Acotar a este catálogo y a consultas derivadas del propio catálogo | R1-5.2, R2-5.1 | hecho |
| A36 | 1108-1109 | Falta la limitación de validez externa | Añadir que las consultas no son descripciones independientes de profesionales | R2-7.1 | hecho |
| A37 | 169-177 | Contribución sin acotar | Declarar que la aportación es una comparación empírica, no un método nuevo | R1-7.1 | hecho |
| A38 | §4 (555-1086) | Comparaciones numéricas repetidas ya visibles en las tablas | Recortar ~30 %; mover detalle a material suplementario | R2-8.2 | en curso |
| A39 | tras 345 | Falta visión general metodológica | Diagrama de flujo dataset → muestreo → indexación → métodos → fusión → evaluación | R2-4.1 | hecho |
| A40 | §3.1 | Falta cuantificar el solape `resumen`/`texto` | Nueva subsección con la medición (→ Fase 3a) | R2-2.3 | hecho |
| A41 | 1127-1135 | Fortaleza infravalorada | Destacar la liberación de datos, consultas, etiquetas, salidas y configs | R2-6.1 | hecho |
## Bloque N — Defectos detectados al verificar el informe contra el código

| # | Línea | Problema | Evidencia | Estado |
|---|---|---|---|---|
| N1 | 370 | *"We implement BM25 using **Pyserini v0.21.0** … **Lucene** backend"* ~\cite{lin2021pyserini} | Cero ocurrencias de `pyserini`/`lucene` en `src/` y `configs/`. Implementación propia: `sklearn.CountVectorizer` + `scipy.sparse`, idf y saturación k1/b a mano (`src/index_builders/bm25_unigram.py`) | hecho |
| N2 | 511 | *"All metrics are computed using the **ranx** library v0.3.7"* ~\cite{bassani2022ranx} | `ranx` no aparece en ningún fichero del repositorio. Métricas propias en `src/metrics.ipynb` (`dcg_at_k`, `idcg_at_10_for_target`) | hecho |
| N3 | 455, 1109 | CE declarado `ms-marco-MiniLM-L-6-v2` (22M, inglés), y su bajo rendimiento se explica por *"cross-lingual domain mismatch"* | El modelo real es `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, multilingüe, entrenado sobre mMARCO, que incluye español. **El argumento de la Discusión es falso** | hecho |
| N4 | — | `eval/bootstrap_global/` reporta Acc@1 deflactadas | `bootstrap_sigtests.ipynb:107-108` alinea sobre la unión rellenando con 0 (n = 25.321). 0,869 × 16590/25321 = 0,5694, exactamente lo reportado | hecho |
| N5 | README 187-194 | La tabla pública mezcla escalas per-run y deflactadas | 0,974 y 0,411 per-run; 0,569 / 0,294 / 0,088 deflactadas | hecho |
| N6 | 156, 158, 175, 1092, 1108, 1115 | *"nearly forty thousand"* / *"nearly 40,000 items"* | El catálogo son 47.513 ítems; el abstract dice "approximately 47,500". Restos de la versión de 39.847 | hecho |
| N7 | 508 | Declara **MAP** entre las cinco métricas | No se reporta en ninguna tabla ni se calcula en `metrics.ipynb` | hecho |
| N8 | 1076 | Tabla 16 etiqueta la fila 0,799 como *"5-way fusion + Blend"* | Tabla 13 la etiqueta como híbrido de 3 vías; el CE corrió sobre `hyb_bm25_uni__bge_colbert__tfidf_char_3_5` (`metrics_ce_blend.json` = 0,79885). Las dos tablas se contradicen | hecho |
| N9 | 458 | *"Base retrievers: BM25, **E5-large**, and hybrid"* | El CE se aplicó a BM25, híbrido y BGE-M3-ColBERT | hecho |
| N10 | 413-417 | GTE evaluado con `doc_prefix: "passage: "` | `gte-multilingual-base` no usa prefijos estilo E5. Afecta a las dos variantes GTE | hecho |
| N11 | 914 | Paréntesis suelto: `($\lambda=0.6$))` | — | hecho |
| N12 | 771-786, 1109 | **GTE se codificó con *mean pooling***, no con el CLS que el modelo usa. `sentence-transformers` 2.2.2 no admite `trust_remote_code`, así que no puede cargar `gte-multilingual-base`; tanto `index_builders/dense_gte.py:73-98` como `retrievers/dense_gte.py:77-105` caen al camino alternativo `AutoModel` + *mean pooling*. Reproducido al reejecutar. Sumado a los prefijos `query: `/`passage: ` que el modelo nunca vio (N10), el 1,3 % de Acc@1 puede ser un artefacto de configuración. El paper lo presenta (L1109) como prueba de que *"retrieval in technical domains remains an open challenge"* | hecho |
| N15 | 908-909 | Tabla 10, nivel de padre: la negrita marca `BGE-M3-sparse` (0,994) como mejor Acc@1 cuando `BGE-M3-colbert` alcanza 0,997 | Los treinta valores de la tabla coinciden con los artefactos; sólo el énfasis está mal puesto, y sugiere lo contrario de lo que dicen las cifras | hecho |
| N14 | 467, 472 | *"retrieve … from 47,513 candidates"*: los índices densos indexan **47.514** documentos | `index/{dense_e5,dense_gte,dense_es_hiiamsid,dense_bge-m3}/meta.json` declaran `num_docs: 47514`, mientras BM25, TF-IDF y BGE-M3 declaran 47.513. La diferencia es el registro raíz `OEB#` ("ZANJAS, CANALIZACIONES Y TUBOS"), que no es un ítem recuperable: los densos lo llevan como distractor extra y los léxicos no. `dense_gte_instrQ` tiene 47.513, así que ni siquiera es consistente dentro de la misma familia. No altera ninguna conclusión, pero el corpus debe declararse igual para todos los métodos | hecho |
| N16 | — | Las filas «oráculo» de la tabla de baselines estructurados se etiquetaron como *extracción de parámetros perfecta*. `oracle: true` sustituye la etapa 1 (la plantilla), no la etapa 2 | `structured_pipeline.py:97-101`; su Acc@1 de padre es exactamente 1,0000 y el de ítem sube sólo un punto. La afirmación correcta es más fuerte: BM25 gana aun regalándole la plantilla | hecho |
| N17 | — | El clasificador afinado (0,209) y el etiquetador BIO (0,031) parecían modelos rotos frente a su propio 0,996 / 0,974 de validación | No lo están: `data_prep.py:8` los entrena sobre el texto largo y el pipeline los evalúa sobre el corto. Es un test entre distribuciones deliberado. Medido eje a eje en `scripts/probe_stage2_extractors.py` | hecho |
| N18 | — | Los `structured_pipeline*` declaran `text_field: "text_norm"` y consultan un índice denso construido sobre `text` | Es la causa de que su Acc@1 de padre sea 0,9848 y el de `dense_e5` suelto 0,9817. Reejecutado con texto crudo: reproduce 0,9817 exacto y el ítem se mueve 0,29 puntos | hecho (declarado en el manuscrito) |
| N19 | Tabla 1 | *«Single-item templates 25 (0 %)»* son **5**; el factor de expansión medio (1583,8) no representa a ninguna plantilla (mediana 144, máximo 6.336); los porcentajes 99 % / 0 % son 99,8 % / 0,2 % | Recontado sobre `OEB_long_norm.parquet`: 30 `parent_key`, 25 paramétricos con 47.508 ítems, 5 ítems sueltos | hecho |
| N13 | — | `index/*/meta.json` no registra qué backend de codificación se usó | Ni `dense_gte/meta.json` ni los demás guardan si se codificó con sentence-transformers o con el camino alternativo, de modo que N12 no era detectable desde los artefactos. `software.sklearn` es `null` y `corpus_hash` también | hecho |
## Bloque C — Correcciones de código

| # | Cambio | Fichero | Estado |
|---|---|---|---|
| C1 | Persistir la muestra de consultas y cargarla en todos los notebooks | `scripts/build_query_samples.py`, `src/retrieve.ipynb`, `src/hybrid.ipynb` | hecho en `retrieve` e `hybrid`; falta `prf_bm25_orchestrator` |
| C2 | Conjunto de validación disjunto de 5.000 consultas | `scripts/build_query_samples.py` | hecho |
| C3a | `_nums` acepta `np.ndarray` además de `list` | `src/hybrid.ipynb` | hecho |
| C3b | `numbers_long` sobre los 47.513 documentos del corpus, no sobre los muestreados | `src/hybrid.ipynb` | hecho |
| C4 | Ampliar la rejilla a `βe ∈ {0, 0.05, 0.10, 0.15}` | `src/hybrid.ipynb` | hecho |
| C5 | Selección de hiperparámetros en validación, con un único criterio declarado | `src/hybrid.ipynb`, `notebooks/bm25_orchestrator.ipynb` | pendiente |
| C6 | Bootstrap por intersección, no por unión con `fillna(0)`; parametrizar `RUNS_INCLUDE` | `src/bootstrap_sigtests.ipynb` | pendiente |
| C7 | Eliminar el `query_prefix` inerte de `dense_e5.yaml` | `configs/dense_e5.yaml` | hecho |
| C8 | Persistir `base_runs_norm.parquet` y separar el barrido de la recuperación base | `src/hybrid.ipynb` | pendiente |
| C9 | Runners para cualquier método, fusiones y cross-encoder | `scripts/run_method.py`, `run_hybrids.py`, `run_cross_encoder.py` | hecho |
| C10 | `requirements.txt` real; eliminar menciones a `ranx` y Pyserini | `requirements.txt`, `README.md` | hecho |

## Bloque R — Reejecuciones y experimentos

| # | Qué | Coste estimado | Estado |
|---|---|---|---|
| R1 | `dense_e5`, `dense_gte`, `dense_gte_instrQ`, `dense_es_hiiamsid` sobre la muestra canónica | ~10 min c/u | hecho |
| R2 | Barrido `(k1,b)` de BM25 sobre validación (62 configs) | ~1 h | hecho |
| R3 | Híbridos: una pasada base para los 5 rankers + 4 barridos | ~75 min + barridos | hecho |
| R4 | PRF sobre `bm25_unigram_params k1=0.60 b=0.35` (16 runs) | ~40 min | hecho |
| R5 | Cross-encoder a K′ = 20, 50, 100 sobre tres sistemas | ~12 min/sistema | hecho |
| R6 | Métricas parent-level para híbridos y reranking | minutos | hecho (`scripts/eval_dual.py`) |
| R7 | Bootstrap, análisis de errores, leaderboards, distribución de rangos | minutos | hecho (`scripts/bootstrap_sigtests.py`) |
| R8 | *(N10)* GTE sin prefijos | ~10 min | hecho junto con la reejecución de GTE |
| R9 | **A40** — solape léxico y numérico `resumen`/`texto` sobre el corpus completo | ~30 min | hecho |
| R10 | **B6** — baselines estructurados | 1 día | hecho (§3.2.5 y §4.8 redactadas, dos tablas generadas) |
| R12 | Sensibilidad del pipeline estructurado al texto de consulta (N18) | ~15 min | hecho (`*_rawq`) |
| R11 | **B8** — HyDE sobre BM25-params y BGE-M3-ColBERT | ~2 h | pendiente (generador listo, 1,2 s/consulta con 4 en paralelo) |
| R13 | **N20** — qué aporta la firma de parámetros y cuánto cuesta calcularla | ~30 min | hecho |

## Bloque F — Reencuadre y difusión

| # | Qué | Estado |
|---|---|---|
| F1 | Título, abstract y contribuciones: decisión de encuadre pendiente de César | hecho |
| F2 | Introducción: los dos escenarios operativos de L152 que nunca se evalúan | hecho |
| F3 | Conclusiones alineadas con el encuadre elegido | hecho |
| F4 | `README.md`: tabla de resultados, recuento de ítems, URL de clonado, menciones a `ranx`/Pyserini | hecho |
| F5 | Zenodo: nueva versión del depósito `10.5281/zenodo.20277824` | pendiente |

---

## Evidencia acumulada

### Auditoría de la muestra de consultas (C1)

`scripts/check_sample_consistency.py` sobre los 129 ficheros de resultados de `runs/`
(salida completa en `sample_audit_baseline.txt`):

| Huella SHA-256 | n | Runs | Qué contiene |
|---|---|---|---|
| `884deade9d3c` | 16.590 | **109** | BM25, TF-IDF, PRF, BGE-M3 (dense/sparse/ColBERT), el CE sobre ColBERT y **los 13 pipelines estructurados** |
| `7752be12d220` | 16.590 | 16 | Los cuatro híbridos y su cross-encoder |
| `325239c0eff6` | 16.590 | 3 | `dense_e5`, `dense_gte`, `dense_es_hiiamsid` |
| `e3b0c44298fc` | **0** | 1 | `reranked_tiebreak__bm25_unigram__wN-1_0__wP-0_5`: fichero **vacío** |

Tres muestras reales más un fichero vacío, donde el manuscrito afirma una sola
(L557, L727 y todos los captions). Se adopta como canónica la de 109 runs, que es la
que sustenta la conclusión titular y la que ya usan los baselines estructurados.

Hallazgos laterales: el run `hyb_bm25_uni__bge_colbert__tfidf_char_3_5` está duplicado
en `runs/` y en `runs/hybrids/`, y el run `reranked_tiebreak__*` no contiene resultados.

### Bonus numérico (C3)

Verificado sobre 2.000 pares reales de `OEB_{short,long}_feats.parquet`:

```
tipo real de la columna `numbers`: <class 'numpy.ndarray'>
isinstance(v, list) -> False   <- el bug

_nums viejo : numeric_exact=1 en     0/2000   overlap>0 en     0/2000
_nums nuevo : numeric_exact=1 en  1996/2000   overlap>0 en  1996/2000

corpus disponible para el bonus: 47.513 documentos (antes: 16.590 muestreados)
```

El componente que §3.2.4 describe como aportación de diseño no influyó en ningún
resultado publicado: `β_exact` y `β_overlap` multiplicaban cero. La frase L857 sobre
la convergencia en `β_exact = 0,1` describe un desempate por orden de rejilla sobre un
parámetro inerte.

### Solape consulta-objetivo (A40 / R9)

`scripts/analyze_query_target_overlap.py` sobre los **47.513 pares alineados** del
catálogo — no sobre la muestra de 20.000 del informe. Los valores coinciden, así que
la objeción de R2-2.3 queda medida sobre el corpus completo:

| Métrica | Valor |
|---|---|
| Cobertura léxica media (tokens de la consulta presentes en el objetivo) | **94,10 %** |
| Cobertura léxica mediana | 94,74 % |
| Consultas cuyo conjunto completo de tokens está contenido en el objetivo | 7,79 % |
| Consultas con al menos un número | 99,83 % |
| Números por consulta (media) | 2,88 |
| **Cobertura numérica media** | **99,96 %** |
| **Consultas en las que todos sus números aparecen en el objetivo** | **99,96 %** |
| Tokens por consulta (media) | 19,10 |

El objetivo contiene ~94 % de los tokens de la consulta y prácticamente el 100 % de sus
valores numéricos, literalmente. La tarea es en gran medida contención léxica casi
verbatim, lo que explica el 97,4 % de BM25 sin necesidad de atribuirlo a una virtud del
método. Matiz que sí juega a favor: sólo 30 plantillas generan los 47.513 ítems, de
modo que las variantes comparten vocabulario casi idéntico y difieren en parámetros —
por eso TF-IDF se queda en 0,56-0,71 y BGE-M3-dense cae a 0,127. Es un benchmark de
negativos duros legítimo, pero es eso y no una evaluación de consultas de usuario.

### GTE: *pooling* y prefijos (N12)

`scripts/probe_gte_pooling.py` codifica los 47.513 documentos y 2.000 consultas de
la muestra canónica con las cuatro combinaciones de (*pooling*, prefijo) y compara
Acc@1 a nivel de ítem:

| *pooling* | prefijos | Acc@1 |
|---|---|---|
| **mean + `query:`/`passage:`** ← configuración publicada | sí | **0,0000** |
| mean | no | 0,0000 |
| CLS | sí | 0,0525 |
| **CLS, sin prefijos** ← configuración prevista por el modelo | no | **0,0970** |

Con *mean pooling* el sistema no acierta ni una sola consulta de 2.000. Con el CLS
que el modelo usa y sin los prefijos estilo E5 que nunca vio, sube a 0,097.

Contexto adicional: `transformers` 4.26.0 —la versión que fija `requirements.txt` por
compatibilidad con torch 2.2.2 y sentence-transformers 2.2.2— **no puede cargar
`gte-multilingual-base` en absoluto**: la referencia entre repositorios
`Alibaba-NLP/new-impl--configuration.py` no existía en esa versión. Con
`transformers` 4.57 sobre el mismo torch, carga sin problema. El índice publicado se
construyó en 2025-08-21, presumiblemente con otro entorno; `meta.json` no lo registra
(N13), así que no es reconstruible desde los artefactos.

**Reejecución completa** (muestra canónica, CLS, sin prefijos, `transformers` 4.57):

| | Acc@1 ítem | Acc@1 padre |
|---|---|---|
| Publicado (mean + prefijos, n=16.589) | 0,0128 | 0,8367 |
| **Corregido (CLS, sin prefijos, n=16.590)** | **0,0696** | **0,9982** |

El salto a nivel de padre es lo relevante: de 0,837 a **0,998**. Bien configurado,
GTE identifica la familia paramétrica casi perfectamente y la variante concreta casi
nunca — una brecha de **92,9 puntos**. Deja de ser un valor atípico sospechoso y pasa
a ser la instancia más nítida del colapso ítem↔padre, que es el hallazgo que encabeza
la versión revisada.

**Consecuencia:** el 1,3 % de GTE no puede usarse como evidencia sobre modelos densos,
y la frase de L1109 que lo presenta como prueba de que *"retrieval in technical domains
remains an open challenge"* no se sostiene. La conclusión cualitativa sí sobrevive
—incluso bien configurado, GTE se queda en ~0,10 a nivel de ítem—, lo que refuerza el
encuadre elegido: el colapso está en la discriminación de variantes, no en la
localización de la familia.

### El colapso ítem/padre, con todas las cifras sobre la muestra canónica

| Sistema | Acc@1 ítem | Acc@1 padre | Brecha |
|---|---|---|---|
| BM25 + frases de parámetros | 0,9737 | 0,9852 | 1,2 p |
| BM25 unigram | 0,8691 | 0,9729 | 10,4 p |
| TF-IDF frases | 0,7083 | 0,9898 | 28,1 p |
| BGE-M3 ColBERT | 0,4480 | 0,9966 | 54,9 p |
| multilingual-e5-base | 0,1363 | 0,9817 | 84,5 p |
| BGE-M3 dense | 0,1269 | 0,9604 | 83,4 p |
| BGE-M3 sparse | 0,1246 | 0,9943 | 87,0 p |
| **GTE-multilingual-base** | **0,0696** | **0,9982** | **92,9 p** |
| sentence-similarity-spanish | 0,0239 | 0,3954 | 37,1 p |

El patrón es monótono y es el titular de la versión revisada: cuanto mejor localiza un
modelo denso la familia paramétrica, más rotundamente falla al elegir la variante.
Todos los multilingües se sitúan entre 0,96 y 0,998 a nivel de padre y entre 0,07 y
0,14 a nivel de ítem. La única excepción, `hiiamsid`, lo es porque es malo en ambos
niveles: es un modelo monolingüe de similitud semántica, no un recuperador.

### La «degradación inesperada» de GTE-instruct no existe

L783 concluye que *"the instruction-tuned variant unexpectedly degraded to 0.697"*.
Con la configuración corregida y ambas variantes sobre la misma muestra:

| | Ítem | Padre |
|---|---|---|
| GTE directo (publicado) | 0,0128 | 0,8367 |
| GTE instruct (publicado) | 0,0140 | 0,6971 |
| **GTE directo (corregido)** | **0,0696** | **0,9982** |
| **GTE instruct (corregido)** | **0,0728** | **0,9970** |

Las dos formulaciones son indistinguibles. La degradación que el manuscrito interpreta
como que *"explicit prompts introduce noise in structured technical retrieval tasks"*
era el resultado de comparar dos muestras de consultas distintas (§3.1 del informe) con
el *pooling* roto. **El hallazgo desaparece.**

### El bonus numérico, ya operativo: un resultado negativo

Reejecutadas las cuatro fusiones con el bonus arreglado y la rejilla de β ampliada:

| Fusión | Publicado | Nuevo | β_exact | β_overlap |
|---|---|---|---|---|
| BM25 + ColBERT + TF-IDF | 0,8896 | **0,8926** | 0,00 | 0,05 |
| BM25 + dense + TF-IDF | 0,8893 | **0,8920** | 0,00 | 0,05 |
| BM25 + sparse + TF-IDF | 0,8817 | **0,8847** | 0,00 | 0,05 |
| Fusión de cinco vías | 0,5899 | **0,6084** | 0,15 | 0,05 |

Tres de las cuatro **descartan el bonus de contención exacta** (β_exact = 0) y las
cuatro eligen β_overlap = 0,05. El motivo está en el conjunto de candidatos: la
contención exacta se cumple para el documento correcto en el 99,8 % de las consultas,
pero también para el **32,1 % de los distractores recuperados**. Un bonus binario que
se activa para un tercio de la lista los eleva a todos por igual y no separa la
variante correcta de sus hermanas.

Es un resultado negativo sobre un elemento que el manuscrito presentaba como
aportación de diseño, y se reporta como tal. La afirmación de L857 —«todas las
configuraciones óptimas convergieron en β_exact = 0,1 y β_overlap = 0,0»— queda
refutada por partida doble: describía un parámetro inerte, y con el parámetro
operativo el óptimo es prácticamente el contrario.

### PRF sobre el baseline fuerte (R2-2.2)

El Revisor 2 señala que §4.1 declara haber construido el PRF sobre BM25 con parámetros
optimizados (0,9737) mientras los dieciséis runs usan el BM25 débil (0,8691), y pide
corregirlo o rehacerlo. Rehecho: dieciséis runs nuevos sobre el baseline fuerte.

| | Acc@1 | Δ frente al baseline |
|---|---|---|
| BM25 con frases de parámetros (baseline) | 0,9737 | — |
| Mejor RM3 (M=5, N=20, λ=0,7) | 0,9732 | −0,04 pp |
| Mejor Rocchio (M=10, N=20, β=0,7) | 0,9672 | −0,64 pp |

Ninguno mejora. La conclusión del manuscrito —que la expansión de consultas no encaja
en este dominio— se sostiene, y ahora está demostrada sobre el baseline que decía haber
usado y no usaba. Es más informativo así: sobre el baseline débil cabía la duda de si
el resultado nulo era una propiedad del PRF o del poco margen que dejaba una primera
etapa mediocre.

### El vocabulario del catálogo son 337 palabras (N21)

`scripts/probe_vector_collisions.py`. Tras normalizar, los 47.513 ítems se escriben
con **337 tipos de palabra**. Con tan poco vocabulario hay filas de la matriz BM25 que
son exactamente iguales:

| Índice | Vocab | Grupos duplicados | Docs | Consultas afectadas | Techo Acc@1 | Medido |
|---|---|---|---|---|---|---|
| `bm25_unigram` | 337 | 1.602 | 3.276 | 6,94 % | **0,9645** | 0,8691 |
| `bm25_unigram_params` | 398 | 0 | 0 | 0 % | 1,0000 | 0,9737 |
| `bm25_unibigram` | 1.142 | 0 | 0 | 0 % | 1,0000 | 0,8267 |

Para 3.276 documentos el índice unigrama no distingue un ítem de otro: no es que los
ordene mal, es que son el mismo punto. Eso impone un **techo de 0,9645** sobre el
0,8691 medido, o sea que las colisiones se comen un tercio del margen que le queda.

Los 61 tokens de parámetro suben el vocabulario a 398 y eliminan **todas** las
colisiones. Parte de los 10,3 puntos que valen (→ N20) no es mejor ponderación: es que
la representación pasa a distinguir los ítems. Pero la inyectividad no basta —el índice
uni+bigrama tiene 1.142 tipos, tampoco tiene colisiones, y saca 0,8267—: lo que aportan
los tokens no es vocabulario, son las 61 distinciones concretas que organizan el
catálogo.

Verificada de paso la afirmación de §4.7.4 (*«3.276 duplicate documents across 1.602
duplicate groups»*), que estaba sin respaldo en los artefactos: es exacta.

### Dos cifras obsoletas en el análisis de errores (N22)

Restos de la época de la fusión COMBSUM sin pesos, que contradecían la tabla que tenían
encima:

- «6.388 [fallos] for the hybrid» → **1.781**. El 6.388 es 16.590 × (1 − 0,6149), el
  Acc@1 de la fusión sin pesos; la tabla ya decía 1.781.
- Un párrafo entero tras la tabla jerárquica: *«54,3 % of errors»* (la tabla dice
  54,86 % de **todas** las consultas), *«hybrid showed intermediate behavior with
  36,0 % right-parent-wrong-item»* (la tabla dice 8,13 %). Eliminado: el párrafo
  anterior ya lo dice bien y con las cifras de la tabla.

---

### Selección en validación (C5 / R2 / B3)

Las 62 configuraciones de la rejilla, evaluadas sobre las 5.000 consultas de
validación (disjuntas del test, semilla 20260909). `scripts/select_on_validation.py`.

| Familia | Elige validación | Val | Test | Mejor casilla en test | Optimismo |
|---|---|---|---|---|---|
| BM25 uni+bigrama | (0,80 · 0,35) | 0,8296 | 0,8267 | 0,8267 | **+0,00 pp** |
| BM25 unigrama | (1,00 · 0,35) | 0,8776 | 0,8681 | 0,8696 | +0,14 pp |
| BM25 + frases de parámetros | (0,60 · 0,35) | 0,9756 | 0,9737 | 0,9737 | **+0,00 pp** |

**El sistema principal sobrevive intacto.** Validación elige exactamente la
configuración reportada, así que el 0,9737 pasa a ser una cifra fuera de muestra sin
tocar ni un run. Era el riesgo real del plan —«el 0,9737 puede moverse al
seleccionarse en validación»— y no se ha materializado.

Por qué sale tan barato, medido y no supuesto:

- **El orden apenas cambia.** Spearman entre validación y test: 0,995 (uni+bigrama),
  0,993 (unigrama), 0,972 (frases).
- **El nivel sí cambia, y de forma uniforme.** Las 62 casillas puntúan más alto en
  validación, entre +0,10 y +1,16 puntos. El desplazamiento mueve toda la rejilla a la
  vez en lugar de reordenarla. Por eso la partición sirve para elegir y no sirve para
  estimar: las cifras de test se reportan aparte.

Los runs de BM25-unigrama se quedan en (0,80 · 0,35) —0,8691 en test, entre las dos
casillas candidatas— porque es el índice sobre el que están construidas las fusiones
híbridas y las cascadas de reranking. Declarado en el manuscrito.

**Lo que sigue seleccionado en test:** el barrido de fusión de `hybrid.ipynb`. Además
el manuscrito declaraba que el criterio era MRR@10 y el código usa `acc@1`
(`if m["acc@1"] > best_acc`); corregido, y los híbridos se presentan ahora como cota
superior de lo que consigue la fusión, no como estimación fuera de muestra.

---

### Baselines estructurados (B6 / R10)

Los 13 runs `structured_pipeline*` usan la muestra canónica (verificado por
`scripts/leaderboard.py`, que se niega a generar una tabla si los runs no la comparten).
Tabla en `eval/structured/lb_item.tex`:

| Sistema | Acc@1 |
|---|---|
| BM25 con frases de parámetros (mejor léxico) | **0,974** |
| Extracción por reglas + búsqueda estructurada, con extracción oráculo | 0,914 |
| Extracción por reglas + búsqueda estructurada | 0,903 |
| Clasificación por LLM + búsqueda estructurada, con oráculo | 0,886 |
| Clasificación por LLM + búsqueda estructurada | 0,877 |
| Extracción de esquema + búsqueda estructurada, con oráculo | 0,821 |
| Extracción de esquema + búsqueda estructurada | 0,809 |
| BGE-M3 ColBERT (mejor neuronal) | 0,448 |
| Clasificador entrenado + búsqueda estructurada | 0,209 |
| Etiquetador BIO + búsqueda estructurada | 0,031 |

Responde a la última pregunta del Revisor 2 y **sale a favor del trabajo**: la
recuperación textual bien ajustada gana al emparejamiento estructurado por reglas
incluso regalándole la plantilla correcta. Se reportan también los dos pipelines
fallidos (0,209 y 0,031): omitirlos sería la misma selección de resultados que se
reprocha al manuscrito con `hiiamsid`.

**Corrección a la primera versión de esta tabla (N16).** Las filas «oráculo» se
etiquetaron como *extracción de parámetros perfecta*. Es falso: `oracle: true`
sustituye la **etapa 1** (identificar la plantilla) por la verdad de campo y deja la
etapa 2 intacta (`src/retrievers/structured_pipeline.py:97-101`). Se comprueba en que
su Acc@1 de padre es exactamente **1,0000** mientras el ítem sólo sube un punto. La
afirmación correcta es más fuerte y más precisa: el pipeline estructurado no alcanza a
BM25 ni cuando se le dice a qué plantilla pertenece la consulta. Corregido en
`scripts/leaderboard.py`, en la contribución 3 y en el pie de la tabla.

**Las cinco configuraciones comparten Acc@1 de padre: 0,9848 exacto.** Es la prueba
mecánica de la disociación: la etapa 1 decide la familia y las etapas 2-3 la variante,
así que el nivel de padre no distingue a ningún sistema de la familia y el nivel de
ítem los separa de 0,031 a 0,903.

### Qué es de verdad «BM25 + frases de parámetros» (N20)

El índice `bm25_unigram_params` no indexa una variante de tokenización. Indexa el
campo `text_word_params`, que `src/data.ipynb` construye así:

```python
df["param_tokens"]     = df["parameters_norm"].map(build_param_tokens)
df["text_word_params"] = df["text_word"] + " " + " ".join(df["param_tokens"])
```

Los `param_tokens` (`param_terreno_blando`, `param_pavimento_con_reposición`, …) no
salen del texto: salen del campo `parameters` del registro. Y como la consulta y el
objetivo son el mismo ítem, la consulta llega con **la misma firma que su objetivo**:
idéntica en los 47.513 pares, y única dentro de su plantilla en los 47.513 casos.

Es decir: el sistema principal del estudio recibe con cada consulta la tupla de
parámetros ya resuelta contra el esquema — exactamente el paso que el pipeline
estructurado tiene que ejecutar. El manuscrito lo describía como una de tres
«variantes de tokenización».

**Cuánto vale y cuánto cuesta**, medido con `scripts/probe_param_tokens.py` y
`scripts/probe_computed_params.py` sobre el mismo índice, cambiando sólo la consulta:

| Consulta | Ítem Acc@1 | R@5 | Padre Acc@1 |
|---|---|---|---|
| Sólo el texto | 0,8706 | 0,9343 | 0,9733 |
| Sólo la firma | 0,2193 | 0,7602 | 0,2193 |
| Texto + firma **leída del registro** (lo publicado) | 0,9737 | 0,9849 | 0,9852 |
| Texto + firma **extraída del texto de la consulta** | **0,9744** | 0,9843 | 0,9860 |

Las dos primeras filas acotan el problema: la firma vale 10,3 puntos y por sí sola no
vale nada, porque el vocabulario de ejes se repite entre plantillas.

La cuarta fila lo resuelve. Calcular la tupla en vez de leerla —plantilla propuesta por
E5, valores asignados por el extractor por reglas, las etapas 1 y 2 del pipeline
estructurado— da **0,9744**, ligeramente por encima de lo publicado. La tupla calculada
coincide con la del registro en el 93,5 % de las consultas y la diferencia no cuesta
nada en agregado. **La cifra publicada no es un artefacto**: es reproducible por un
sistema realizable.

Lo que sí había que corregir es la descripción, y lo que sale de corregirla es un
resultado mejor que el que había:

> Los dos sistemas necesitan la misma tupla y la obtienen igual. Se diferencian sólo en
> qué hacen con ella. Usada como evidencia de consulta da 0,974; usada como filtro
> exacto da 0,903. Los siete puntos son el precio de la restricción dura.

La recomendación deja de ser «usa recuperación léxica en vez de emparejamiento
estructurado» y pasa a ser «extrae los atributos, y luego ordena con ellos en vez de
filtrar por ellos», que es más estrecha y más útil.

Verificación del propio script: `probe_computed_params.py` reconstruye los
`param_tokens` almacenados desde `parameters_norm` en los 47.513 ítems antes de medir
nada, y la formulación `stored` reproduce exactamente el run oficial (0,9737 / 0,9852).

Corregido en §3.2.1 (qué son los tokens y de dónde salen), §4.8 (la comparación y la
tabla), la Discusión (la asimetría de la comparación) y las Conclusiones.

### La etapa 2, medida por separado (N17)

`scripts/probe_stage2_extractors.py` (n=500, semilla 20260910) compara lo que extrae
la etapa 2 contra la tupla de parámetros que generó el ítem consultado, y lo cruza con
el tamaño del conjunto que devuelve la etapa 3, leído de los runs persistidos:

| Etapa 2 | Ejes correctos | Sin resolver | Erróneos | Conjunto medio | Contiene el objetivo |
|---|---|---|---|---|---|
| Reglas | 98,0 % | 1,4 % | 0,5 % | 1,32 | 96,7 % |
| Clasificador afinado | 76,1 % | 0,0 % | 23,9 % | 0,98 | 20,9 % |
| Etiquetador BIO | 45,4 % | 54,1 % | 0,4 % | 65,54 | 69,5 % |

Tres cosas que no se veían en el Acc@1:

1. **Los dos modelos supervisados no están rotos.** El *checkpoint* carga entero
   (194/194 tensores de cabeza, verificado) y sus valores son sensatos. Su
   `training_log.json` declara 0,996 de acierto por consulta y 0,974 de F1 de span
   porque `src/pipeline/training/data_prep.py:8` los entrena sobre el **texto largo** y
   el pipeline los aplica sobre el **texto corto**. Es un test entre distribuciones,
   deliberado y documentado en el propio código. Lo que mide es que un modelo que lee
   los parámetros en una redacción no los lee en la otra, aunque la larga contenga el
   94,1 % de los tokens de la corta.
2. **Los dos modos de fallo tienen consecuencias opuestas**, porque la etapa 3 filtra y
   no puntúa. Un eje sin resolver es un comodín y el objetivo sigue en el conjunto; un
   eje erróneo lo saca y no lo recupera ninguna profundidad. Se ve en la tabla de
   resultados: el clasificador tiene Recall@10 0,213 contra Acc@1 0,209 (no hay nada
   que recuperar) y el etiquetador BIO 0,258 contra 0,031 (ocho veces).
3. **Un filtro no es un ranking.** Con reglas el conjunto contiene el objetivo el
   96,7 % de las veces y el Acc@1 es 0,903: los 6,4 puntos de diferencia son consultas
   en las que el objetivo está en el conjunto pero no primero, porque dentro del
   conjunto sólo queda el orden del catálogo. Es la imagen especular del fallo
   neuronal, alcanzada desde el otro lado.

### El texto de consulta de los pipelines estructurados (N18)

Los `structured_pipeline*` declaran `text_field: "text_norm"` y por tanto alimentan la
etapa 1 con el texto normalizado, mientras el índice denso que consultan (`dense_e5`)
se construyó sobre `text`. Es la única forma en que esta familia no corre exactamente
como el resto del estudio, y explica la diferencia de 0,3 puntos entre el Acc@1 de
padre del pipeline (0,9848) y el del `dense_e5` suelto (0,9817), que hasta ahora no
tenía explicación.

Medido, no supuesto: `structured_pipeline_rules_rawq` es el mismo pipeline con
`text_field: "text"`.

| Run | Ítem Acc@1 | Recall@5 | Padre Acc@1 |
|---|---|---|---|
| `structured_pipeline_rules` (texto normalizado) | 0,9033 | 0,9667 | 0,9848 |
| `structured_pipeline_rules_rawq` (texto crudo) | 0,9004 | 0,9637 | **0,9817** |
| `structured_pipeline_oracle_rules` (normalizado) | 0,9136 | 0,9773 | 1,0000 |
| `structured_pipeline_oracle_rules_rawq` (crudo) | 0,9136 | 0,9773 | 1,0000 |

El padre reproduce exactamente el 0,9817 del `dense_e5` suelto, lo que confirma el
diagnóstico, y el ítem se mueve 0,29 puntos. Con la plantilla dada, los dos runs son
idénticos a cuatro decimales en todas las métricas: la sensibilidad está en la etapa 1
y sólo en ella, porque el extractor por reglas normaliza el texto por su cuenta. Se mantienen los runs normalizados en la
tabla (la familia es internamente consistente) y se declara la sensibilidad medida en
el manuscrito, en vez de absorberla.

### Estadísticas del dataset: dos cifras mal (N19)

- Tabla 1, fila *«Single-item templates ($=$1 variants) 25 (0 %)»*: son **5**, no 25.
  El 25 es el número de plantillas **paramétricas**, mal etiquetado. De los 30
  `parent_key` del corpus, 25 acaban en `$` y generan 47.508 ítems; los otros 5
  (`OEB060`, `OEB210`, `OEB220`, `OEB260`, `OEB270`) son ítems sueltos que son su
  propio padre.
- El *«factor de expansión medio 1583,8»* es 47.513/30 y no representa a ninguna
  plantilla: la mediana de variantes por plantilla paramétrica es **144** y el máximo
  **6.336**. Sustituido por media/mediana/mín/máx sobre las 25 paramétricas.
- «Queries with numeric parameters 47.430 (99 %)» → 99,8 %; «83 (0 %)» → 0,2 %.

---

---

## Cómo reanudar

Todo el estado vive en el repositorio, no en ninguna sesión: la rama
`paper/autcon-r1-revision` y este registro bastan para retomar el trabajo.

### Entorno

```bash
# Desde el worktree de la revisión
docker compose up -d jupyter-pytorch bge-m3
```

`docker-compose.override.yml` **no está versionado** porque contiene rutas
absolutas de la máquina. Monta `data/`, `index/`, `runs/`, `models/` y
`hf-cache/` desde el checkout principal, y fija `HF_HOME=/hf-cache` para que los
modelos no se descarguen en una caché efímera. Si se pierde, hay que recrearlo.

En el host, esos mismos directorios se resuelven mediante junctions de Windows
creados en el worktree; Docker no los atraviesa, de ahí los montajes explícitos.

`bge-m3` es necesario para cualquier cosa que toque BGE-M3: los rankers se
sirven por HTTP en `host.docker.internal:8800`. Sin él, los híbridos fallan con
«Network is unreachable».

GTE necesita un entorno aparte, ya creado dentro del contenedor
(`/opt/gtevenv`), con `transformers` 4.57 sobre el mismo torch. Si se recrea el
contenedor hay que rehacerlo:

```bash
python -m venv --system-site-packages /opt/gtevenv
/opt/gtevenv/bin/pip install -U "transformers>=4.44,<5"
```

### Comandos

```bash
python scripts/build_paper.py                      # compila el manuscrito
python scripts/check_citations.py                  # citas y duplicados
python scripts/check_sample_consistency.py         # ¿todos los runs, una muestra?
python scripts/check_query_sources.py              # ¿las fuentes cubren la muestra?
python scripts/apply_code_corrections.py --check   # ¿siguen aplicados los parches?
python scripts/leaderboard.py --preset dissociation --dual   # tabla central
```

Dentro del contenedor:

```bash
docker exec jupyter-pytorch python /work/scripts/run_method.py <método>
docker exec jupyter-pytorch python /work/scripts/run_hybrids.py
```

### Qué se puede perder

Nada del repositorio. Lo único vulnerable es **el trabajo en vuelo**: un
`run_hybrids.py` a medias no se reanuda por partes, hay que relanzarlo. La
recuperación base de ColBERT cuesta ~20 min de codificación más el MaxSim, y el
barrido otros ~35 min por fusión.

Los resultados publicados están respaldados en `runs/_as_published/` y en
`index/_as_published_*`, así que toda cifra nueva puede contrastarse con la
antigua en cualquier momento.

## Fuera de alcance (decisión explícita)

- **B7 — Consultas realistas** (perturbaciones controladas de los `resumen`; consultas
  de estimadores). Es el eje del rechazo del Editor Asociado y de R1-3, R2-1.1 y R2-7.1.
  El reencuadre (F1) evita prometer lo que no se evalúa, pero la validación con
  consultas reales sigue sin existir y debe declararse en Limitaciones.
- Elección de revista destino.
- Edición lingüística profesional (R2-9; R1 opinaba lo contrario).
