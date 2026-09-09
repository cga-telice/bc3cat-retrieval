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
| A2 | 518-520 | `HAS_NUM (24,711, 62%)` / `NO_NUM (15,136, 38%)`: cifras de la versión de 39.847 ítems | `16,561 (99.83%)` / `29 (0.17%)` | R2-2.1 | pendiente |
| A3 | 631 | Caption Tabla 4: *"16,076 queries with numbers"* | `16,561` (el 99,83 % sí es correcto) | R2-2.1 | pendiente |
| A4 | 530 | *"We apply Bonferroni correction"* | `Holm--Bonferroni` | R2-3.1 | hecho |
| A5 | 587 | *"Bonferroni"* + umbral `p < 0.003` | `Holm--Bonferroni`; reportar los `p_holm` de `eval/bootstrap_lexical/bootstrap_sigtests_pairs.csv` | R2-3.1 | hecho |
| A6 | 534 | *"100 randomly sampled errors from each method family"*: nunca hubo muestreo | Describir el análisis real (todos los fallos, muestra común) | R2-4.2 | pendiente |
| A7 | 951 | Ídem + taxonomía de 4 categorías | Unificar con L536-544: cinco categorías, dos con frecuencia cero | R2-4.2 | pendiente |
| A8 | 959 | Caption Tabla 14: `$n=100$ per method` | `%` de fallos reales, con los `n` por método | R2-4.2 | pendiente |
| A9 | 966-968 | Suman 99,9 % por redondeo a un decimal | Dos decimales + nota de categorías vacías | R2-4.2 | pendiente |
| A10 | 989 | Caption Tabla 15 sugiere % sobre errores | Son % sobre *todas* las consultas; categorías mutuamente excluyentes | R2-4.3 | pendiente |
| A11 | 991-1000 | Tabla 15 no suma 100 % | Añadir fila *Correct at rank 1* | R2-4.3 | pendiente |
| ~~A12~~ | 407 | ~~Prefijo de E5 erróneo~~ | **Descartado**: `src/retrievers/dense_e5.py:101-102` fija `"query: "` a mano e ignora el YAML. El paper es correcto; lo que se corrige es el YAML (→ C7) | informe | descartado |
| A13 | 731, 735, 743, 837, 1080 | "E5-large" / "multilingual-e5-large" | `multilingual-e5-base` | sesión | pendiente |
| A14 | 771-772, 776-777, 838 | "GTE-large-en-v1.5", "GTE-Qwen2-instruct": modelos nunca usados, uno de ellos sólo inglés | `GTE-multilingual-base (direct)` / `(instruct)` | sesión | pendiente |
| A15 | 927 | `MRR@10 = 1.000` con Acc@1 = 0,869: imposible por definición | `0.898`; R@5 `0.931` → `0.932` | sesión | pendiente |
| A16 | 936-937 | Fila híbrida: etiqueta de 3 vías, cifras de la fusión de 5 vías | Etiqueta y baseline correctos del sistema de 3 vías | sesión | pendiente |
| A17 | 914 | *"top-100 candidates"* | `top-50` (o ampliar a 20/50/100, → R5) | sesión | pendiente |
| A18 | 457 | *"Reranking depth: Top 20, 50, or 100"*: sólo se ejecutó 50 | Declarar las profundidades realmente evaluadas | sesión | pendiente |
| A19 | 449 | Rejilla `β_exact ∈ {0.0, 0.05, 0.1}` y selección por MRR@10; el código usa `(0.10, 0.15)` y `acc@1` | Declarar la rejilla y el criterio reales (→ C4, C5) | R2-3.2 | pendiente |
| A20 | 857, 861 | *"All optimal configurations converged on β_exact=0.1"*: describe un desempate sobre un parámetro inerte | Eliminar la afirmación; rehacer con el bonus ya operativo (→ C3) | sesión | pendiente |
| A21 | 822 | *"ColBERT and sparse achieved perfect accuracy (1.000)"*: se leyó la columna de Recall | Acc@1 reales: 0,759 / 0,759 / 0,655 sobre las 29 consultas no numéricas | sesión | pendiente |
| A22 | 849-853, Tabla 12 | `hiiamsid` descrito en Métodos y ausente de resultados | Añadir su fila (item 0,024 / parent 0,395) | sesión | pendiente |
| A23 | 662 | *"Six configurations each were evaluated"* | Se evaluaron ocho; se reportan seis | sesión | hecho |
| A24 | 714 vs 1072 | Mejor RM3: `M=10` en Tabla 7, `M=5` en Tabla 16 | Unificar y anotar el empate (ambas 0,8699) | sesión | pendiente |
| A25 | 1042 | *"in its embedding space"* aplicado a BM25 | BM25 no tiene espacio de embeddings | sesión | hecho |
| A26 | 1086 | Afirmación sobre R@5/MRR no soportada por la Tabla 16 | Reescribir con lo que la tabla sí muestra | sesión | pendiente |
| A27 | 944 | *"the highest overall performance"* para el híbrido+blend | Acotar al ámbito de la Tabla 13 | sesión | pendiente |
| A28 | 1073 | `BM25-unigram (default, k1=0.80, b=0.35)` | Es el óptimo del barrido, no un valor por defecto. **Reformulado**: no cabe invocar los defaults de Lucene porque no se usó Lucene (→ N1) | sesión | hecho |
| A29 | 568 | "26.6 percentage point gap" | `26.5` (0,9737 − 0,7083) | sesión | hecho |
| A30 | 195 | "Jacques de Sousa et al." sin `\cite` | Añadir la referencia | R2-8.4 | pendiente |
| A31 | 189, 193, 195, 197, 203, 205, 207 | `~\cite{...}` como sujeto gramatical | Anteponer el nombre de los autores | R2-8.3 | pendiente |
| A32 | 574, 645-646, 767-770, 773, abstract | Cinco términos para tres conceptos | Fijar **template** / **item-variant** / **parent** | R2-8.3 | pendiente |
| A33 | 221-223, 1108 | Alcance del estudio no delimitado | Explicitar subcategoría, plantillas y procedencia de las consultas | R2-1.2 | pendiente |
| A34 | 1115 | *"Neural models … consistently fail"* frente a la asimetría admitida en L1094 | Acotar a los modelos zero-shot evaluados en este benchmark | R2-5.2 | pendiente |
| A35 | 1085, 1115-1116, abstract | Generalización excesiva | Acotar a este catálogo y a consultas derivadas del propio catálogo | R1-5.2, R2-5.1 | pendiente |
| A36 | 1108-1109 | Falta la limitación de validez externa | Añadir que las consultas no son descripciones independientes de profesionales | R2-7.1 | pendiente |
| A37 | 169-177 | Contribución sin acotar | Declarar que la aportación es una comparación empírica, no un método nuevo | R1-7.1 | pendiente |
| A38 | §4 (555-1086) | Comparaciones numéricas repetidas ya visibles en las tablas | Recortar ~30 %; mover detalle a material suplementario | R2-8.2 | pendiente |
| A39 | tras 345 | Falta visión general metodológica | Diagrama de flujo dataset → muestreo → indexación → métodos → fusión → evaluación | R2-4.1 | pendiente |
| A40 | §3.1 | Falta cuantificar el solape `resumen`/`texto` | Nueva subsección con la medición (→ Fase 3a) | R2-2.3 | pendiente |
| A41 | 1127-1135 | Fortaleza infravalorada | Destacar la liberación de datos, consultas, etiquetas, salidas y configs | R2-6.1 | pendiente |

## Bloque N — Defectos detectados al verificar el informe contra el código

| # | Línea | Problema | Evidencia | Estado |
|---|---|---|---|---|
| N1 | 370 | *"We implement BM25 using **Pyserini v0.21.0** … **Lucene** backend"* ~\cite{lin2021pyserini} | Cero ocurrencias de `pyserini`/`lucene` en `src/` y `configs/`. Implementación propia: `sklearn.CountVectorizer` + `scipy.sparse`, idf y saturación k1/b a mano (`src/index_builders/bm25_unigram.py`) | hecho |
| N2 | 511 | *"All metrics are computed using the **ranx** library v0.3.7"* ~\cite{bassani2022ranx} | `ranx` no aparece en ningún fichero del repositorio. Métricas propias en `src/metrics.ipynb` (`dcg_at_k`, `idcg_at_10_for_target`) | hecho |
| N3 | 455, 1109 | CE declarado `ms-marco-MiniLM-L-6-v2` (22M, inglés), y su bajo rendimiento se explica por *"cross-lingual domain mismatch"* | El modelo real es `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, multilingüe, entrenado sobre mMARCO, que incluye español. **El argumento de la Discusión es falso** | hecho |
| N4 | — | `eval/bootstrap_global/` reporta Acc@1 deflactadas | `bootstrap_sigtests.ipynb:107-108` alinea sobre la unión rellenando con 0 (n = 25.321). 0,869 × 16590/25321 = 0,5694, exactamente lo reportado | pendiente |
| N5 | README 187-194 | La tabla pública mezcla escalas per-run y deflactadas | 0,974 y 0,411 per-run; 0,569 / 0,294 / 0,088 deflactadas | pendiente |
| N6 | 156, 158, 175, 1092, 1108, 1115 | *"nearly forty thousand"* / *"nearly 40,000 items"* | El catálogo son 47.513 ítems; el abstract dice "approximately 47,500". Restos de la versión de 39.847 | hecho |
| N7 | 508 | Declara **MAP** entre las cinco métricas | No se reporta en ninguna tabla ni se calcula en `metrics.ipynb` | hecho |
| N8 | 1076 | Tabla 16 etiqueta la fila 0,799 como *"5-way fusion + Blend"* | Tabla 13 la etiqueta como híbrido de 3 vías; el CE corrió sobre `hyb_bm25_uni__bge_colbert__tfidf_char_3_5` (`metrics_ce_blend.json` = 0,79885). Las dos tablas se contradicen | pendiente |
| N9 | 458 | *"Base retrievers: BM25, **E5-large**, and hybrid"* | El CE se aplicó a BM25, híbrido y BGE-M3-ColBERT | hecho |
| N10 | 413-417 | GTE evaluado con `doc_prefix: "passage: "` | `gte-multilingual-base` no usa prefijos estilo E5. Afecta a las dos variantes GTE | pendiente |
| N11 | 914 | Paréntesis suelto: `($\lambda=0.6$))` | — | hecho |
| N12 | 771-786, 1109 | **GTE se codificó con *mean pooling***, no con el CLS que el modelo usa. `sentence-transformers` 2.2.2 no admite `trust_remote_code`, así que no puede cargar `gte-multilingual-base`; tanto `index_builders/dense_gte.py:73-98` como `retrievers/dense_gte.py:77-105` caen al camino alternativo `AutoModel` + *mean pooling*. Reproducido al reejecutar. Sumado a los prefijos `query: `/`passage: ` que el modelo nunca vio (N10), el 1,3 % de Acc@1 puede ser un artefacto de configuración. El paper lo presenta (L1109) como prueba de que *"retrieval in technical domains remains an open challenge"* | **verificado**: mean+prefijos = 0,0000 · CLS sin prefijos = 0,0970 (ver Evidencia). Falta decidir si se reejecuta con la configuración correcta |
| N13 | — | `index/*/meta.json` no registra qué backend de codificación se usó | Ni `dense_gte/meta.json` ni los demás guardan si se codificó con sentence-transformers o con el camino alternativo, de modo que N12 no era detectable desde los artefactos. `software.sklearn` es `null` y `corpus_hash` también | pendiente |

## Bloque C — Correcciones de código

| # | Cambio | Fichero | Estado |
|---|---|---|---|
| C1 | Persistir la muestra de consultas y cargarla en todos los notebooks en lugar de re-muestrear en memoria | `scripts/build_query_samples.py`, `src/retrieve.ipynb` | parcial — hecho en `retrieve.ipynb`; faltan `prf_bm25_orchestrator`, `hybrid` y `bm25_orchestrator` |
| C2 | Conjunto de validación disjunto de 5.000 consultas | `scripts/build_query_samples.py` | hecho |
| C3a | `_nums` acepta `np.ndarray` además de `list` | `src/hybrid.ipynb` | hecho |
| C3b | `numbers_long` sobre los 47.513 documentos del corpus, no sobre los muestreados | `src/hybrid.ipynb` | hecho |
| C4 | Ampliar la rejilla a `βe ∈ {0, 0.05, 0.10, 0.15}` | `src/hybrid.ipynb` | hecho |
| C5 | Selección de hiperparámetros en validación, con un único criterio declarado | `src/hybrid.ipynb`, `notebooks/bm25_orchestrator.ipynb` | pendiente |
| C6 | Bootstrap por intersección, no por unión con `fillna(0)`; parametrizar `RUNS_INCLUDE` | `src/bootstrap_sigtests.ipynb` | pendiente |
| C7 | Eliminar el `query_prefix` inerte de `dense_e5.yaml` | `configs/dense_e5.yaml` | pendiente |
| C8 | Persistir `base_runs_norm.parquet` y separar el barrido de la recuperación base | `src/hybrid.ipynb` | pendiente |
| C9 | Runner completo build → retrieve → metrics para cualquier config | `scripts/run_all.py` | pendiente |
| C10 | `requirements.txt` real; eliminar menciones a `ranx` y Pyserini | `requirements.txt`, `README.md` | hecho en `requirements.txt`; falta el README |

## Bloque R — Reejecuciones y experimentos

| # | Qué | Coste estimado | Estado |
|---|---|---|---|
| R1 | `dense_e5`, `dense_gte`, `dense_es_hiiamsid` sobre la muestra canónica | ~10 min c/u | `dense_e5` y `dense_es_hiiamsid` hechos; `dense_gte` bloqueado por N12 |
| R2 | Barrido `(k1,b)` de BM25 sobre validación (62 configs) | ~1 h | pendiente |
| R3 | Híbridos: una pasada base para los 5 rankers + 4 barridos | ~75 min + barridos | pendiente |
| R4 | PRF sobre `bm25_unigram_params k1=0.60 b=0.35` (16 runs) | ~40 min | pendiente |
| R5 | Cross-encoder a K′ = 20, 50, 100 sobre tres sistemas | ~12 min/sistema | pendiente |
| R6 | Métricas parent-level para híbridos y reranking | minutos | pendiente |
| R7 | Bootstrap, análisis de errores, leaderboards, distribución de rangos | minutos | pendiente |
| R8 | *(opcional, N10)* GTE sin prefijos | ~10 min | pendiente |
| R9 | **A40** — solape léxico y numérico `resumen`/`texto` sobre el corpus completo | ~30 min | hecho |
| R10 | **B6** — integrar los baselines estructurados (ya sobre la muestra canónica) | 1 día | hecho (código + tabla); falta redactar la sección |
| R11 | **B8** — HyDE sobre BM25-params y BGE-M3-ColBERT | ~2 h | pendiente |

## Bloque F — Reencuadre y difusión

| # | Qué | Estado |
|---|---|---|
| F1 | Título, abstract y contribuciones: decisión de encuadre pendiente de César | pendiente |
| F2 | Introducción: los dos escenarios operativos de L152 que nunca se evalúan | pendiente |
| F3 | Conclusiones alineadas con el encuadre elegido | pendiente |
| F4 | `README.md`: tabla de resultados, recuento de ítems, URL de clonado, menciones a `ranx`/Pyserini | pendiente |
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

**Consecuencia:** el 1,3 % de GTE no puede usarse como evidencia sobre modelos densos,
y la frase de L1109 que lo presenta como prueba de que *"retrieval in technical domains
remains an open challenge"* no se sostiene. La conclusión cualitativa sí sobrevive
—incluso bien configurado, GTE se queda en ~0,10 a nivel de ítem—, lo que refuerza el
encuadre elegido: el colapso está en la discriminación de variantes, no en la
localización de la familia.

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
incluso concediéndole extracción de parámetros perfecta. Se reportan también los dos
pipelines fallidos (0,209 y 0,031): omitirlos sería la misma selección de resultados
que se reprocha al manuscrito con `hiiamsid`.

---

## Fuera de alcance (decisión explícita)

- **B7 — Consultas realistas** (perturbaciones controladas de los `resumen`; consultas
  de estimadores). Es el eje del rechazo del Editor Asociado y de R1-3, R2-1.1 y R2-7.1.
  El reencuadre (F1) evita prometer lo que no se evalúa, pero la validación con
  consultas reales sigue sin existir y debe declararse en Limitaciones.
- Elección de revista destino.
- Edición lingüística profesional (R2-9; R1 opinaba lo contrario).
