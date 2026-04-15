# Error Analysis — Structured Pipeline (Sprint D1)

Analysis of 13110 failed queries across 6 Tier 1 conditions.

## Table A — Error Category Breakdown

| error_type         |   structured_pipeline_rules |   structured_pipeline_oracle_rules |   structured_pipeline |   structured_pipeline_oracle |   structured_pipeline_phi4_classify |   structured_pipeline_oracle_phi4_classify |
|:-------------------|----------------------------:|-----------------------------------:|----------------------:|-----------------------------:|------------------------------------:|-------------------------------------------:|
| E1-WRONG_CONCEPT   |                         252 |                                  0 |                   252 |                            0 |                                 252 |                                          0 |
| E2-PARTIAL_EXTRACT |                        1352 |                               1434 |                     0 |                            0 |                                   0 |                                          0 |
| E2-WRONG_VALUE     |                           0 |                                  0 |                     0 |                            0 |                                   0 |                                          0 |
| E2-ALL_NULL        |                           0 |                                  0 |                     0 |                            0 |                                   0 |                                          0 |
| E2-UNSPECIFIED     |                           0 |                                  0 |                  2918 |                         2976 |                                1787 |                                       1887 |
| E3-SCHEMA_MISMATCH |                           0 |                                  0 |                     0 |                            0 |                                   0 |                                          0 |
| TOTAL              |                        1604 |                               1434 |                  3170 |                         2976 |                                2039 |                                       1887 |


## Table B — Errors by Concept Group (Rules Pipeline, Top 10)

| parent_key   | concept                                                |   num_items |   num_axes |   total_queries |   errors |   error_rate |
|:-------------|:-------------------------------------------------------|------------:|-----------:|----------------:|---------:|-------------:|
| OEB030$      | CANALIZACIÓN HORMIGONADA DE TUBO DE POLIETILENO 110mm  |        6336 |          5 |            6336 |      397 |   0.0626578  |
| OEB040$      | CANALIZACIÓN HORMIGONADA DE TUBO DE POLIETILENO 160mm  |        6336 |          5 |            6336 |      364 |   0.0574495  |
| OEB020$      | CANALIZACIÓN HORMIGONADA DE TUBO DE PVC 110 mm         |        4608 |          5 |            4608 |      265 |   0.0575087  |
| OEB190$      | ZANJA PARA CABLES DE 0,60 M DE ANCHURA A MANO          |         648 |          5 |             648 |      232 |   0.358025   |
| OEB200$      | ZANJA PARA CABLES DE 0,60 M DE ANCHURA A MÁQUINA       |         432 |          5 |             432 |      145 |   0.335648   |
| OEB230$      | CANALIZACIÓN HORMIGONADA DE TUBO DE POLIETILENO 200mm  |        6336 |          5 |            6336 |       72 |   0.0113636  |
| OEB250$      | TRANSICIÓN DE CANALIZACIONES CMS PARA OBRAS DE FÁBRICA |         270 |          5 |             270 |       54 |   0.2        |
| OEB290$      | CANALIZACIÓN HORMIGONADA DE TUBO DE POLIETILENO 50mm   |        6336 |          5 |            6336 |       33 |   0.00520833 |
| OEB130$      | ENTRONQUE DE TUBOS EN ARQUETA O CÁMARA EXISTENTE       |          72 |          3 |              72 |       19 |   0.263889   |
| OEB300$      | CANALIZACIÓN HORMIGONADA DE TUBO DE POLIETILENO 90mm   |        6336 |          5 |            6336 |        9 |   0.00142045 |


## Table C — Per-Axis Accuracy (Rules Oracle)

| axis_label               |   total_occurrences |   correct |   wrong_value |   null_when_present |   accuracy |   accuracy_has_numbers |   accuracy_no_numbers |
|:-------------------------|--------------------:|----------:|--------------:|--------------------:|-----------:|-----------------------:|----------------------:|
| CONDICIONES DE EJECUCIÓN |               16580 |     16546 |             0 |                  34 |     0.9979 |                 0.9979 |                     1 |
| TRABAJO                  |               16571 |     15554 |             0 |                1017 |     0.9386 |                 0.9385 |                     1 |
| BANDA DE MANTENIMIENTO   |               16571 |     16543 |             0 |                  28 |     0.9983 |                 0.9983 |                     1 |
| Nº TUBOS                 |               15986 |     15986 |             0 |                   0 |     1      |                 1      |                     0 |
| TIPO DE TERRENO          |               15259 |     15259 |             0 |                   0 |     1      |                 1      |                     0 |
| DIÁMETROS                |                 888 |       888 |             0 |                   0 |     1      |                 1      |                     0 |
| PROFUNDIDAD              |                 377 |       377 |             0 |                   0 |     1      |                 1      |                     0 |
| TIPO DE ACCIÓN           |                 102 |       102 |             0 |                   0 |     1      |                 1      |                     0 |
| TUBO                     |                  43 |        35 |             0 |                   8 |     0.814  |                 0.814  |                     0 |
| TERRENO                  |                  13 |        13 |             0 |                   0 |     1      |                 1      |                     0 |
| PAVIMENTO                |                  13 |        13 |             0 |                   0 |     1      |                 1      |                     0 |
| MATERIAL                 |                   9 |         9 |             0 |                   0 |     1      |                 1      |                     1 |
| DIÁMETRO                 |                   3 |         3 |             0 |                   0 |     1      |                 1      |                     0 |


## has_numbers vs no_numbers Breakdown

| Condition | has_num errors | has_num rate | no_num errors | no_num rate |
|---|---|---|---|---|
| structured_pipeline | 3167/16561 | 19.1% | 3/29 | 10.3% |
| structured_pipeline_oracle | 2973/16561 | 17.9% | 3/29 | 10.3% |
| structured_pipeline_oracle_phi4_classify | 1886/16561 | 11.4% | 1/29 | 3.5% |
| structured_pipeline_oracle_rules | 1434/16561 | 8.7% | 0/29 | 0.0% |
| structured_pipeline_phi4_classify | 2038/16561 | 12.3% | 1/29 | 3.5% |
| structured_pipeline_rules | 1604/16561 | 9.7% | 0/29 | 0.0% |


## Rules vs LLM Comparison (Oracle Conditions)

| comparison              |   both_correct |   both_fail |   rules_wrong_llm_right |   rules_right_llm_wrong |   total_queries |
|:------------------------|---------------:|------------:|------------------------:|------------------------:|----------------:|
| Rules vs Llama extract  |          12727 |         547 |                     887 |                    2429 |           16590 |
| Rules vs Phi-4 classify |          13899 |         630 |                     804 |                    1257 |           16590 |


## Qualitative Error Examples


### E1-WRONG_CONCEPT

**Example 1:** `OEB200baedb`
- Query: *zanja para cables de 0.80 a 1.00 m de profundidad a máquina, normal, en material normal. (cualquier franja horaria/no ne*
- Concept: ZANJA PARA CABLES DE 0,60 M DE ANCHURA A MÁQUINA
- GT params: `{"PROFUNDIDAD": "0,80 a 1,00 m", "TIPO DE TERRENO": "normal", "TRABAJO": "Cualquier franja horaria", "BANDA DE MANTENIMIENTO": "No necesita intervalo", "CONDICIONES DE EJECUCIÓN": "Volumen escaso"}`
- Predicted parent: OEB190$ (ZANJA PARA CABLES DE 0,60 M DE ANCHURA A MANO)

**Example 2:** `OEB290ihabc`
- Query: *canalización hormigonada 16 t, polietileno libre de halógenos de 50 mm, con topo. (diurno/3 <== i < "5" horas/cualquier *
- Concept: CANALIZACIÓN HORMIGONADA DE TUBO DE POLIETILENO 50mm
- GT params: `{"Nº TUBOS": "16", "TIPO DE TERRENO": "Con topo", "TRABAJO": "Diurno", "BANDA DE MANTENIMIENTO": "3 <= i < 5 horas", "CONDICIONES DE EJECUCIÓN": "Cualquier condición de ejecución"}`
- Predicted parent: OEB040$ (CANALIZACIÓN HORMIGONADA DE TUBO DE POLIETILENO 160mm)

**Example 3:** `OEB030ibabc`
- Query: *canalización hormigonada 16 t, polietileno libre de halógenos de 110 mm, bajo vías. (diurno/3 >== i > "5" horas/cualquie*
- Concept: CANALIZACIÓN HORMIGONADA DE TUBO DE POLIETILENO 110mm
- GT params: `{"Nº TUBOS": "16", "TIPO DE TERRENO": "Bajo vías", "TRABAJO": "Diurno", "BANDA DE MANTENIMIENTO": "3 <= i < 5 horas", "CONDICIONES DE EJECUCIÓN": "Cualquier condición de ejecución"}`
- Predicted parent: OEB040$ (CANALIZACIÓN HORMIGONADA DE TUBO DE POLIETILENO 160mm)


### E2-PARTIAL_EXTRACT

**Example 1:** `OEB250acbdb`
- Query: *suministro de canalización de 6 tubos de acero galvanizado de 100mm de diámetro para instalaciones cms en transiciones e*
- Concept: TRANSICIÓN DE CANALIZACIONES CMS PARA OBRAS DE FÁBRICA
- GT params: `{"TIPO DE ACCIÓN": "Suministro", "Nº TUBOS": "6", "TRABAJO": "Nocturno Excepcional", "BANDA DE MANTENIMIENTO": "No necesita intervalo", "CONDICIONES DE EJECUCIÓN": "Volumen escaso"}`
- Extracted: `{"TIPO DE ACCIÓN": "Suministro", "Nº TUBOS": "6", "TRABAJO": "Nocturno Excepcional", "BANDA DE MANTENIMIENTO": "No necesita intervalo", "CONDICIONES DE EJECUCIÓN": null}`
- Mismatched axes: ['CONDICIONES DE EJECUCIÓN']

**Example 2:** `OEB030bgedb`
- Query: *canalización hormigonada 2 t, polietileno libre de halógenos de 110 mm, en balasto. (cualquier frana horaria/no necesita*
- Concept: CANALIZACIÓN HORMIGONADA DE TUBO DE POLIETILENO 110mm
- GT params: `{"Nº TUBOS": "2", "TIPO DE TERRENO": "Balasto", "TRABAJO": "Cualquier franja horaria", "BANDA DE MANTENIMIENTO": "No necesita intervalo", "CONDICIONES DE EJECUCIÓN": "Volumen escaso"}`
- Extracted: `{"Nº TUBOS": "2", "TIPO DE TERRENO": "Balasto", "TRABAJO": null, "BANDA DE MANTENIMIENTO": "No necesita intervalo", "CONDICIONES DE EJECUCIÓN": "Volumen escaso"}`
- Mismatched axes: ['TRABAJO']

**Example 3:** `OEB020abeda`
- Query: *canalización hormigonada de 2 t, pvc 110 mm, bajo vías. (cualquier frana horaria/no necesita intervalo/volumen relevante*
- Concept: CANALIZACIÓN HORMIGONADA DE TUBO DE PVC 110 mm
- GT params: `{"Nº TUBOS": "2", "TIPO DE TERRENO": "Bajo vías", "TRABAJO": "Cualquier franja horaria", "BANDA DE MANTENIMIENTO": "No necesita intervalo", "CONDICIONES DE EJECUCIÓN": "Volumen relevante"}`
- Extracted: `{"Nº TUBOS": "2", "TIPO DE TERRENO": "Bajo vías", "TRABAJO": null, "BANDA DE MANTENIMIENTO": "No necesita intervalo", "CONDICIONES DE EJECUCIÓN": "Volumen relevante"}`
- Mismatched axes: ['TRABAJO']


## Key Findings

1. **Stage 1 errors (E1) account for 252 (15.7%) of rules pipeline errors** — the pipeline→oracle gap.
2. **E2-PARTIAL_EXTRACT**: 1434 (100.0%) of rules oracle errors

---
*Generated by `scripts/error_analysis.py`*
