# Examples — Gold parent not in top-10

## bm25_unigram

- **query** `OEB200cacab`: zanja para cables de 1.10 m de profundidad a máquina normal en material normal diurno excepcional i 5 horas volumen escaso
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190cccab` | gold item: `OEB200cacab`
  - top5: ['OEB190cccab', 'OEB190cccbb', 'OEB190ccaab', 'OEB190ccccb', 'OEB190ccabb']

- **query** `OEB200cabcb`: zanja para cables de 1.10 m de profundidad a máquina normal en material normal nocturno i 3 horas volumen escaso
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190ccbcb` | gold item: `OEB200cabcb`
  - top5: ['OEB190ccbcb', 'OEB190ccbbb', 'OEB190ccdcb', 'OEB190ccbab', 'OEB190ccdbb']

- **query** `OEB200cacac`: zanja para cables de 1.10 m de profundidad a máquina normal en material normal diurno excepcional i 5 horas cualquier condición de ejecución
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190cccac` | gold item: `OEB200cacac`
  - top5: ['OEB190cccac', 'OEB190cccbc', 'OEB190ccaac', 'OEB190ccccc', 'OEB190ccabc']

- **query** `OEB200caecc`: zanja para cables de 1.10 m de profundidad a máquina normal en material normal cualquier franja horaria i 3 horas cualquier condición de ejecución
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190ccecc` | gold item: `OEB200caecc`
  - top5: ['OEB190ccecc', 'OEB190ccebc', 'OEB190ccfcc', 'OEB190cceac', 'OEB190ccfbc']

- **query** `OEB200cadba`: zanja para cables de 1.10 m de profundidad a máquina normal en material normal nocturno excepcional 3 i 5 horas volumen relevante
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190ccdba` | gold item: `OEB200cadba`
  - top5: ['OEB190ccdba', 'OEB190ccdaa', 'OEB190ccdca', 'OEB190ccbba', 'OEB190ccbaa']

## bge_m3_colbert

_none_

## hyb_bm25_uni__bge_colbert__tfidf_char_3_5

_none_

