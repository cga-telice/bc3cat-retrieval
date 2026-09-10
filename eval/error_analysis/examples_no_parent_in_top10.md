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

- **query** `OEB200cadca`: zanja para cables de 1.10 m de profundidad a máquina normal en material normal nocturno excepcional i 3 horas volumen relevante
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190ccdca` | gold item: `OEB200cadca`
  - top5: ['OEB190ccdca', 'OEB190ccdba', 'OEB190ccbca', 'OEB190ccdaa', 'OEB190ccbba']

- **query** `OEB200caaab`: zanja para cables de 1.10 m de profundidad a máquina normal en material normal diurno i 5 horas volumen escaso
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190ccaab` | gold item: `OEB200caaab`
  - top5: ['OEB190ccaab', 'OEB190cccab', 'OEB190ccabb', 'OEB190ccacb', 'OEB190cccbb']

- **query** `OEB200cabbb`: zanja para cables de 1.10 m de profundidad a máquina normal en material normal nocturno 3 i 5 horas volumen escaso
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190ccbbb` | gold item: `OEB200cabbb`
  - top5: ['OEB190ccbbb', 'OEB190ccbab', 'OEB190ccbcb', 'OEB190ccdbb', 'OEB190ccdab']

## bge_m3_colbert

_none_

## hyb_bm25_uni__bge_colbert__tfidf_char_3_5

_none_

