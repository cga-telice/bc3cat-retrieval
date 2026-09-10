# Examples — Wrong parent at rank-1

## bm25_unigram

- **query** `OEB030aaeca`: canalización hormigonada 1 t polietileno libre de halógenos de 110 mm normal cualquier frana horaria i 3 horas volumen relevante
  - gold parent: `OEB030$` | pred parent: `OEB070$`
  - top1 item: `OEB070aeca` | gold item: `OEB030aaeca`
  - top5: ['OEB070aeca', 'OEB070afca', 'OEB070aeba', 'OEB070afba', 'OEB070aeaa']

- **query** `OEB200bacba`: zanja para cables de 0.80 a 1.00 m de profundidad a máquina normal en material normal diurno excepcional 3 i 5 horas volumen relevante
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190bccba` | gold item: `OEB200bacba`
  - top5: ['OEB190bccba', 'OEB190bccaa', 'OEB190bccca', 'OEB190bcaba', 'OEB190bcaaa']

- **query** `OEB030aaebb`: canalización hormigonada 1 t polietileno libre de halógenos de 110 mm normal cualquier frana horaria 3 i 5 horas volumen escaso
  - gold parent: `OEB030$` | pred parent: `OEB070$`
  - top1 item: `OEB070aebb` | gold item: `OEB030aaebb`
  - top5: ['OEB070aebb', 'OEB070afbb', 'OEB070aecb', 'OEB070afcb', 'OEB070aeab']

- **query** `OEB030ehcbb`: canalización hormigonada 5 t polietileno libre de halógenos de 110 mm con topo diurno excepcional 3 i 5 horas volumen escaso
  - gold parent: `OEB030$` | pred parent: `OEB070$`
  - top1 item: `OEB070acbb` | gold item: `OEB030ehcbb`
  - top5: ['OEB070acbb', 'OEB070bcbb', 'OEB070accb', 'OEB070bccb', 'OEB070acab']

- **query** `OEB030bhcbc`: canalización hormigonada 2 t polietileno libre de halógenos de 110 mm con topo diurno excepcional 3 i 5 horas cualquier condición de ejecución
  - gold parent: `OEB030$` | pred parent: `OEB070$`
  - top1 item: `OEB070bcbc` | gold item: `OEB030bhcbc`
  - top5: ['OEB070bcbc', 'OEB070bccc', 'OEB070bcac', 'OEB070babc', 'OEB070bacc']

## bge_m3_colbert

- **query** `OEB020ahdca`: canalización hormigonada de 2 t, pvc 110 mm, con topo. (nocturno excepcional/i < "3" horas/volumen relevante)
  - gold parent: `OEB020$` | pred parent: `OEB070$`
  - top1 item: `OEB070bdca` | gold item: `OEB020ahdca`
  - top5: ['OEB070bdca', 'OEB020aadba', 'OEB020aadca', 'OEB020aadaa', 'OEB070bdba']

- **query** `OEB200cafac`: zanja para cables de 1.10 m de profundidad a máquina, normal, en material normal. (cualquier franja horaria excepcional/i >== 5 horas/cualquier condición de ejecución)
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190cbfac` | gold item: `OEB200cafac`
  - top5: ['OEB190cbfac', 'OEB190cbfab', 'OEB200cbfac', 'OEB190cafac', 'OEB200cbfab']

- **query** `OEB200bacbb`: zanja para cables de 0.80 a 1.00 m de profundidad a máquina, normal, en material normal. (diurno excepcional/3 <== i < "5" horas/volumen escaso)
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190bacbb` | gold item: `OEB200bacbb`
  - top5: ['OEB190bacbb', 'OEB200bacbb', 'OEB190bbcbb', 'OEB190baabb', 'OEB200baabb']

- **query** `OEB050bac`: ejecución de canalización de comunicaciones para línea subterranea doble circuito de 220 ó 400 kv en terreno medio , sin reposición de pavimento. (-/-/cualquier condición de ejecución)
  - gold parent: `OEB050$` | pred parent: `OEB010$`
  - top1 item: `OEB010aab` | gold item: `OEB050bac`
  - top5: ['OEB010aab', 'OEB010aaa', 'OEB010aac', 'OEB010abb', 'OEB010abc']

- **query** `OEB200babbc`: zanja para cables de 0.80 a 1.00 m de profundidad a máquina, normal, en material normal. (nocturno/3 <== i < "5" horas/cualquier condición de ejecución)
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190babbc` | gold item: `OEB200babbc`
  - top5: ['OEB190babbc', 'OEB190badbc', 'OEB190bbbbc', 'OEB200bbbbc', 'OEB200badbc']

## hyb_bm25_uni__bge_colbert__tfidf_char_3_5

- **query** `OEB030bbacb`: 
  - gold parent: `OEB030$` | pred parent: `OEB070$`
  - top1 item: `OEB070bacb` | gold item: `OEB030bbacb`
  - top5: ['OEB070bacb', 'OEB070babb', 'OEB070bccb', 'OEB070baab', 'OEB030bbacb']

- **query** `OEB200abcba`: 
  - gold parent: `OEB200$` | pred parent: `OEB190$`
  - top1 item: `OEB190accba` | gold item: `OEB200abcba`
  - top5: ['OEB190accba', 'OEB200abcba', 'OEB190accaa', 'OEB190accca', 'OEB190acdba']

- **query** `OEB040bhddb`: 
  - gold parent: `OEB040$` | pred parent: `OEB070$`
  - top1 item: `OEB070bddb` | gold item: `OEB040bhddb`
  - top5: ['OEB070bddb', 'OEB040baddb', 'OEB070bbdb', 'OEB040bhddb', 'OEB040bhbdb']

- **query** `OEB030ahcca`: 
  - gold parent: `OEB030$` | pred parent: `OEB070$`
  - top1 item: `OEB070acca` | gold item: `OEB030ahcca`
  - top5: ['OEB070acca', 'OEB070acba', 'OEB070acaa', 'OEB070aaca', 'OEB070adca']

- **query** `OEB300bhdbb`: 
  - gold parent: `OEB300$` | pred parent: `OEB070$`
  - top1 item: `OEB070bdcb` | gold item: `OEB300bhdbb`
  - top5: ['OEB070bdcb', 'OEB070bdbb', 'OEB300badab', 'OEB300badbb', 'OEB070bdab']

