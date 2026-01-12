# Examples — Wrong parent at rank-1

## bm25_unigram

- **query** `OEB030chaaa`: canalización hormigonada 3 t polietileno libre de halógenos de 110 mm con topo diurno i 5 horas volumen relevante
  - gold parent: `OEB030$` | pred parent: `OEB070$`
  - top1 item: `OEB070baba` | gold item: `OEB030chaaa`
  - top5: ['OEB070baba', 'OEB070aaba', 'OEB070bcba', 'OEB070acba', 'OEB070baca']

- **query** `OEB030abada`: canalización hormigonada 1 t polietileno libre de halógenos de 110 mm bajo vías diurno no necesita intervalo volumen relevante
  - gold parent: `OEB030$` | pred parent: `OEB070$`
  - top1 item: `OEB070aada` | gold item: `OEB030abada`
  - top5: ['OEB070aada', 'OEB070acda', 'OEB070aadb', 'OEB070abda', 'OEB070acdb']

- **query** `OEB200bbbbb`: zanja para cables de 0.80 a 1.00 m de profundidad a máquina rocoso en material rocoso nocturno 3 i 5 horas volumen escaso
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190bbbbb` | gold item: `OEB200bbbbb`
  - top5: ['OEB190bbbbb', 'OEB200bbbbb', 'OEB190bbbab', 'OEB200bbbab', 'OEB190bbbcb']

- **query** `OEB030bheba`: canalización hormigonada 2 t polietileno libre de halógenos de 110 mm con topo cualquier frana horaria 3 i 5 horas volumen relevante
  - gold parent: `OEB030$` | pred parent: `OEB070$`
  - top1 item: `OEB070beba` | gold item: `OEB030bheba`
  - top5: ['OEB070beba', 'OEB070bfba', 'OEB070beca', 'OEB070bfca', 'OEB070beaa']

- **query** `OEB030eabab`: canalización hormigonada 5 t polietileno libre de halógenos de 110 mm normal nocturno i 5 horas volumen escaso
  - gold parent: `OEB030$` | pred parent: `OEB070$`
  - top1 item: `OEB070abab` | gold item: `OEB030eabab`
  - top5: ['OEB070abab', 'OEB070bbab', 'OEB070bbbb', 'OEB070abbb', 'OEB070bdab']

## bge_m3_colbert

- **query** `OEB200cacab`: zanja para cables de 1.10 m de profundidad a máquina, normal, en material normal. (diurno excepcional/i >== 5 horas/volumen escaso)
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190cbcab` | gold item: `OEB200cacab`
  - top5: ['OEB190cbcab', 'OEB190cbcbb', 'OEB190cacab', 'OEB200cacab', 'OEB190cacbb']

- **query** `OEB020ahfac`: canalización hormigonada de 2 t, pvc 110 mm, con topo. (cualquier franja horaria excepcional/i >==5 horas/cualquier condición de ejecución)
  - gold parent: `OEB020$` | pred parent: `OEB070$`
  - top1 item: `OEB070bfab` | gold item: `OEB020ahfac`
  - top5: ['OEB070bfab', 'OEB020aafac', 'OEB070bfaa', 'OEB020aafaa', 'OEB020aafab']

- **query** `OEB200caebb`: zanja para cables de 1.10 m de profundidad a máquina, normal, en material normal. (cualquier franja horaria/3 <== i < "5" horas/volumen escaso)
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190cbfbb` | gold item: `OEB200caebb`
  - top5: ['OEB190cbfbb', 'OEB190cbebb', 'OEB190cafbb', 'OEB190caebb', 'OEB200cafbb']

- **query** `OEB020ahaab`: canalización hormigonada de 2 t, pvc 110 mm, con topo. (diurno/i >==5 horas/volumen escaso)
  - gold parent: `OEB020$` | pred parent: `OEB070$`
  - top1 item: `OEB070baab` | gold item: `OEB020ahaab`
  - top5: ['OEB070baab', 'OEB020aaaab', 'OEB020aacab', 'OEB070bcab', 'OEB020acaab']

- **query** `OEB200baeba`: zanja para cables de 0.80 a 1.00 m de profundidad a máquina, normal, en material normal. (cualquier franja horaria/3 <== i < "5" horas/volumen relevante)
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190baeba` | gold item: `OEB200baeba`
  - top5: ['OEB190baeba', 'OEB200baeba', 'OEB200bafba', 'OEB190bafba', 'OEB190bbeba']

## hyb_bm25_uni__bge_colbert__tfidf_char_3_5

- **query** `OEB300ahcba`: 
  - gold parent: `OEB300$` | pred parent: `OEB070$`
  - top1 item: `OEB070acca` | gold item: `OEB300ahcba`
  - top5: ['OEB070acca', 'OEB070acba', 'OEB300aacba', 'OEB070acaa', 'OEB300aacaa']

- **query** `OEB030cbbba`: 
  - gold parent: `OEB030$` | pred parent: `OEB070$`
  - top1 item: `OEB070bbba` | gold item: `OEB030cbbba`
  - top5: ['OEB070bbba', 'OEB070abba', 'OEB070bbca', 'OEB070abca', 'OEB070bbaa']

- **query** `OEB200abaca`: 
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190acaca` | gold item: `OEB200abaca`
  - top5: ['OEB190acaca', 'OEB190acaba', 'OEB190acaaa', 'OEB200abaca', 'OEB190accca']

- **query** `OEB030dhbda`: 
  - gold parent: `OEB030$` | pred parent: `OEB070$`
  - top1 item: `OEB070bbda` | gold item: `OEB030dhbda`
  - top5: ['OEB070bbda', 'OEB070abda', 'OEB030dabda', 'OEB070bdda', 'OEB070adda']

- **query** `OEB230bhbba`: 
  - gold parent: `OEB230$` | pred parent: `OEB070$`
  - top1 item: `OEB070bbca` | gold item: `OEB230bhbba`
  - top5: ['OEB070bbca', 'OEB070bbba', 'OEB230babba', 'OEB070bbaa', 'OEB230babaa']

