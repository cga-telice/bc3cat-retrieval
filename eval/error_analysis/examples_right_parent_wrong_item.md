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

- **query** `OEB170afcac`: Canalización metálica superficial con  1  tubos de acero galvanizado de 5'' de diámetro. (Diurno excepcional/i >== 5 horas/Cualquier condición de ejecución)
  - gold parent: `OEB170$` | pred parent: `OEB170$`
  - top1 item: `OEB170aacac` | gold item: `OEB170afcac`
  - top5: ['OEB170aacac', 'OEB170aacbc', 'OEB170adcac', 'OEB170adcbc', 'OEB170aaccc']

- **query** `OEB280chaac`: Canalización hormigonada  3  T, polietileno libre de halógenos de 40 mm, con topo. (Diurno/i >== 5 horas/Cualquier condición de ejecución)
  - gold parent: `OEB280$` | pred parent: `OEB280$`
  - top1 item: `OEB280ehabc` | gold item: `OEB280chaac`
  - top5: ['OEB280ehabc', 'OEB280chabc', 'OEB280ehcbc', 'OEB280chcbc', 'OEB280chaac']

- **query** `OEB170cgccb`: Canalización metálica superficial con  3  tubos de acero galvanizado de 6'' de diámetro. (Diurno excepcional/i < "3" horas/Volumen escaso)
  - gold parent: `OEB170$` | pred parent: `OEB170$`
  - top1 item: `OEB170egccb` | gold item: `OEB170cgccb`
  - top5: ['OEB170egccb', 'OEB170egcbb', 'OEB170egacb', 'OEB170egcab', 'OEB170egabb']

- **query** `OEB170bccbb`: Canalización metálica superficial con  2  tubos de acero galvanizado de 3'' de diámetro. (Diurno excepcional/3 <== i < "5" horas/Volumen escaso)
  - gold parent: `OEB170$` | pred parent: `OEB170$`
  - top1 item: `OEB170bbcbb` | gold item: `OEB170bccbb`
  - top5: ['OEB170bbcbb', 'OEB170bdcbb', 'OEB170bdcab', 'OEB170bbcab', 'OEB170bbccb']

- **query** `OEB280edecc`: Canalización hormigonada  5  T, polietileno libre de halógenos de 40 mm, en cruce de carretera. (Cualquier franja horaria/i < "3" horas/Cualquier condición de ejecución)
  - gold parent: `OEB280$` | pred parent: `OEB280$`
  - top1 item: `OEB280edebc` | gold item: `OEB280edecc`
  - top5: ['OEB280edebc', 'OEB280cdebc', 'OEB280edfbc', 'OEB280edecc', 'OEB280cdeac']

