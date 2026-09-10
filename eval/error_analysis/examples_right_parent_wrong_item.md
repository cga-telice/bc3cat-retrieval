# Examples — Right parent, wrong item

## bm25_unigram

- **query** `OEB170cacbc`: canalización metálica superficial con 3 tubos de acero galvanizado de 1 de diámetro diurno excepcional 3 i 5 horas cualquier condición de ejecución
  - gold parent: `OEB170$` | pred parent: `OEB170$`
  - top1 item: `OEB170aacbc` | gold item: `OEB170cacbc`
  - top5: ['OEB170aacbc', 'OEB170adcbc', 'OEB170adcac', 'OEB170aacac', 'OEB170aaccc']

- **query** `OEB030egbca`: canalización hormigonada 5 t polietileno libre de halógenos de 110 mm en balasto nocturno i 3 horas volumen relevante
  - gold parent: `OEB030$` | pred parent: `OEB030$`
  - top1 item: `OEB030egbba` | gold item: `OEB030egbca`
  - top5: ['OEB030egbba', 'OEB030cgbba', 'OEB030egdba', 'OEB030cgdba', 'OEB030cgbaa']

- **query** `OEB180eba`: hincas con cable tensor de acero para el tendido de cables sobre una trinchera de tierra cualquier franja horaria 3 i 5 horas volumen relevante
  - gold parent: `OEB180$` | pred parent: `OEB180$`
  - top1 item: `OEB180eaa` | gold item: `OEB180eba`
  - top5: ['OEB180eaa', 'OEB180eca', 'OEB180eba', 'OEB180eda', 'OEB180faa']

- **query** `OEB280cfdbb`: canalización hormigonada 3 t polietileno libre de halógenos de 40 mm adosada nocturno excepcional 3 i 5 horas volumen escaso
  - gold parent: `OEB280$` | pred parent: `OEB280$`
  - top1 item: `OEB280efdbb` | gold item: `OEB280cfdbb`
  - top5: ['OEB280efdbb', 'OEB280cfdbb', 'OEB280efdcb', 'OEB280cfdab', 'OEB280ffdbb']

- **query** `OEB290ehdcb`: canalización hormigonada 5 t polietileno libre de halógenos de 50 mm con topo nocturno excepcional i 3 horas volumen escaso
  - gold parent: `OEB290$` | pred parent: `OEB290$`
  - top1 item: `OEB290ehdbb` | gold item: `OEB290ehdcb`
  - top5: ['OEB290ehdbb', 'OEB290chdbb', 'OEB290chdab', 'OEB290ehdcb', 'OEB290dhdbb']

## bge_m3_colbert

- **query** `OEB020ebdbb`: canalización hormigonada de 12 t, pvc 110 mm, bajo vías. (nocturno excepcional/3 >== i > "5" horas/volumen escaso)
  - gold parent: `OEB020$` | pred parent: `OEB020$`
  - top1 item: `OEB020ebdab` | gold item: `OEB020ebdbb`
  - top5: ['OEB020ebdab', 'OEB020ebdbb', 'OEB020ebbbb', 'OEB020ebbab', 'OEB020ebdcb']

- **query** `OEB300dgebb`: canalización hormigonada 4 t, polietileno libre de halógenos de 90 mm, en balasto. (cualquier franja horaria/3 <== i < "5" horas/volumen escaso)
  - gold parent: `OEB300$` | pred parent: `OEB300$`
  - top1 item: `OEB300dgfbb` | gold item: `OEB300dgebb`
  - top5: ['OEB300dgfbb', 'OEB300dgebb', 'OEB300dbfbb', 'OEB300dgfab', 'OEB300dbebb']

- **query** `OEB040jhbaa`: canalización hormigonada 18 t, polietileno libre de halógenos de 160 mm, con topo. (nocturno/i >==5 horas/volumen relevante)
  - gold parent: `OEB040$` | pred parent: `OEB040$`
  - top1 item: `OEB040jadaa` | gold item: `OEB040jhbaa`
  - top5: ['OEB040jadaa', 'OEB040jabaa', 'OEB040jabba', 'OEB040jadba', 'OEB040jbbaa']

- **query** `OEB030jffdb`: canalización hormigonada 18 t, polietileno libre de halógenos de 110 mm, adosada. (cualquier franja horaria excepcional/no necesita intervalo/volumen escaso)
  - gold parent: `OEB030$` | pred parent: `OEB030$`
  - top1 item: `OEB030jaedb` | gold item: `OEB030jffdb`
  - top5: ['OEB030jaedb', 'OEB030jafbb', 'OEB030jafdb', 'OEB030jbfdb', 'OEB030jafda']

- **query** `OEB300dgdaa`: canalización hormigonada 4 t, polietileno libre de halógenos de 90 mm, en balasto. (nocturno excepcional/i >== 5 horas/volumen relevante)
  - gold parent: `OEB300$` | pred parent: `OEB300$`
  - top1 item: `OEB300dbdaa` | gold item: `OEB300dgdaa`
  - top5: ['OEB300dbdaa', 'OEB300dbdba', 'OEB300dgdaa', 'OEB300dgdba', 'OEB300dbbaa']

## hyb_bm25_uni__bge_colbert__tfidf_char_3_5

- **query** `OEB190abeaa`: 
  - gold parent: `OEB190$` | pred parent: `OEB190$`
  - top1 item: `OEB190aceaa` | gold item: `OEB190abeaa`
  - top5: ['OEB190aceaa', 'OEB190aceba', 'OEB190acfaa', 'OEB190acfba', 'OEB190aceca']

- **query** `OEB040iafac`: 
  - gold parent: `OEB040$` | pred parent: `OEB040$`
  - top1 item: `OEB040iafbc` | gold item: `OEB040iafac`
  - top5: ['OEB040iafbc', 'OEB040iafac', 'OEB040iafcc', 'OEB040iaeac', 'OEB040iaebc']

- **query** `OEB190cbcbc`: 
  - gold parent: `OEB190$` | pred parent: `OEB190$`
  - top1 item: `OEB190cccbc` | gold item: `OEB190cbcbc`
  - top5: ['OEB190cccbc', 'OEB190ccfbc', 'OEB190cccac', 'OEB190ccccc', 'OEB190ccfac']

- **query** `OEB190cbfca`: 
  - gold parent: `OEB190$` | pred parent: `OEB190$`
  - top1 item: `OEB190ccfca` | gold item: `OEB190cbfca`
  - top5: ['OEB190ccfca', 'OEB190ccfba', 'OEB190ccfaa', 'OEB190cceca', 'OEB190cceba']

- **query** `OEB040jfcdb`: 
  - gold parent: `OEB040$` | pred parent: `OEB040$`
  - top1 item: `OEB040jacdb` | gold item: `OEB040jfcdb`
  - top5: ['OEB040jacdb', 'OEB040jaddb', 'OEB040jaadb', 'OEB040jacda', 'OEB040jccdb']

