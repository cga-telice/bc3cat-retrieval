# Examples — Right parent, wrong item

## bm25_unigram

- **query** `OEB170dddab`: canalización metálica superficial con 4 tubos de acero galvanizado de 3 1 2 de diámetro nocturno excepcional i 5 horas volumen escaso
  - gold parent: `OEB170$` | pred parent: `OEB170$`
  - top1 item: `OEB170dddbb` | gold item: `OEB170dddab`
  - top5: ['OEB170dddbb', 'OEB170dddab', 'OEB170dddcb', 'OEB170ddbbb', 'OEB170ddbab']

- **query** `OEB230cfeaa`: canalización hormigonada 3 t polietileno libre de halógenos de 200 mm adosada cualquier franja horaria i 5 horas volumen relevante
  - gold parent: `OEB230$` | pred parent: `OEB230$`
  - top1 item: `OEB230efeba` | gold item: `OEB230cfeaa`
  - top5: ['OEB230efeba', 'OEB230cfeba', 'OEB230effba', 'OEB230cffba', 'OEB230efeca']

- **query** `OEB290cffbb`: canalización hormigonada 3 t polietileno libre de halógenos de 50 mm adosada cualquier franja horaria excepcional 3 i 5 horas volumen escaso
  - gold parent: `OEB290$` | pred parent: `OEB290$`
  - top1 item: `OEB290effbb` | gold item: `OEB290cffbb`
  - top5: ['OEB290effbb', 'OEB290cffbb', 'OEB290effcb', 'OEB290cffab', 'OEB290iffbb']

- **query** `OEB280eafcc`: canalización hormigonada 5 t polietileno libre de halógenos de 40 mm normal cualquier franja horaria excepcional i 3 horas cualquier condición de ejecución
  - gold parent: `OEB280$` | pred parent: `OEB280$`
  - top1 item: `OEB280eafbc` | gold item: `OEB280eafcc`
  - top5: ['OEB280eafbc', 'OEB280cafbc', 'OEB280ecfbc', 'OEB280ccfbc', 'OEB280eafcc']

- **query** `OEB230ebfcb`: canalización hormigonada 5 t polietileno libre de halógenos de 200 mm bajo vías cualquier franja horaria excepcional i 3 horas volumen escaso
  - gold parent: `OEB230$` | pred parent: `OEB230$`
  - top1 item: `OEB230ebfbb` | gold item: `OEB230ebfcb`
  - top5: ['OEB230ebfbb', 'OEB230cbfbb', 'OEB230cbfab', 'OEB230ebfcb', 'OEB230hbfbb']

## bge_m3_colbert

- **query** `OEB300dhdcb`: canalización hormigonada 4 t, polietileno libre de halógenos de 90 mm, con topo. (nocturno excepcional/i < "3" horas/volumen escaso)
  - gold parent: `OEB300$` | pred parent: `OEB300$`
  - top1 item: `OEB300dadcb` | gold item: `OEB300dhdcb`
  - top5: ['OEB300dadcb', 'OEB300dabbb', 'OEB300dadab', 'OEB300dabcb', 'OEB300dadbb']

- **query** `OEB020dffcc`: canalización hormigonada de 8 t, pvc 110 mm, adosada. (cualquier franja horaria excepcional/i < "3" horas/cualquier condición de ejecución)
  - gold parent: `OEB020$` | pred parent: `OEB020$`
  - top1 item: `OEB020dffbc` | gold item: `OEB020dffcc`
  - top5: ['OEB020dffbc', 'OEB020dffcb', 'OEB020dffcc', 'OEB020dffca', 'OEB020dffbb']

- **query** `OEB280icebb`: canalización hormigonada 16 t, polietileno libre de halógenos de 40 mm, rocoso. (cualquier franja horaria/3 <== i < "5" horas/volumen escaso)
  - gold parent: `OEB280$` | pred parent: `OEB280$`
  - top1 item: `OEB280icfbb` | gold item: `OEB280icebb`
  - top5: ['OEB280icfbb', 'OEB280icebb', 'OEB280iafbb', 'OEB280icfab', 'OEB280icfcb']

- **query** `OEB230jgeac`: canalización hormigonada 18 t, polietileno libre de halógenos de 200 mm, en balasto. (cualquier franja horaria/i >== 5 horas/cualquier condición de ejecución)
  - gold parent: `OEB230$` | pred parent: `OEB230$`
  - top1 item: `OEB230jgfac` | gold item: `OEB230jgeac`
  - top5: ['OEB230jgfac', 'OEB230jgfbc', 'OEB230jgfaa', 'OEB230jgfab', 'OEB230jgeac']

- **query** `OEB290eeaab`: canalización hormigonada 5 t, polietileno libre de halógenos de 50 mm, en andén. (diurno/i >== 5 horas/volumen escaso)
  - gold parent: `OEB290$` | pred parent: `OEB290$`
  - top1 item: `OEB290eeabb` | gold item: `OEB290eeaab`
  - top5: ['OEB290eeabb', 'OEB290eeaab', 'OEB290eecbb', 'OEB290eecab', 'OEB290eebbb']

## hyb_bm25_uni__bge_colbert__tfidf_char_3_5

- **query** `OEB300ccaac`: 
  - gold parent: `OEB300$` | pred parent: `OEB300$`
  - top1 item: `OEB300ccabc` | gold item: `OEB300ccaac`
  - top5: ['OEB300ccabc', 'OEB300ccaac', 'OEB300cccbc', 'OEB300cccac', 'OEB300ccacc']

- **query** `OEB030hfaca`: 
  - gold parent: `OEB030$` | pred parent: `OEB030$`
  - top1 item: `OEB030haaca` | gold item: `OEB030hfaca`
  - top5: ['OEB030haaca', 'OEB030haaba', 'OEB030hacca', 'OEB030hacba', 'OEB030haaaa']

- **query** `OEB290dhfcb`: 
  - gold parent: `OEB290$` | pred parent: `OEB290$`
  - top1 item: `OEB290dafbb` | gold item: `OEB290dhfcb`
  - top5: ['OEB290dafbb', 'OEB290dafcb', 'OEB290dafab', 'OEB070bfcb', 'OEB290dhfcb']

- **query** `OEB030efacc`: 
  - gold parent: `OEB030$` | pred parent: `OEB030$`
  - top1 item: `OEB030eaabc` | gold item: `OEB030efacc`
  - top5: ['OEB030eaabc', 'OEB030eacbc', 'OEB030eaacc', 'OEB030eaaac', 'OEB030efcbc']

- **query** `OEB030afbcb`: 
  - gold parent: `OEB030$` | pred parent: `OEB030$`
  - top1 item: `OEB030aabbb` | gold item: `OEB030afbcb`
  - top5: ['OEB030aabbb', 'OEB030aabcb', 'OEB030aabab', 'OEB030aadcb', 'OEB030acbbb']

