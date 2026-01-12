# Representative Error Examples (Section 4.8)

## Method: bm25_unigram

### Lexical Confusion
- **Query** `OEB250abaec`: suministro de canalización de 4 tubos de acero galvanizado de 100 mm de diámetro para instalaciones cms en transiciones entre diferentes plataformas diurno excepcional no aplica cualquier condición de ejecución
  - **Retrieved** `OEB250abcec`: Suministro de canalización de 4 tubos de acero galvanizado de 100mm de diámetro para instalaciones CMS en transiciones entre diferentes plataformas.  Trabajo: No aplica Banda de mantenimiento: No aplica Condiciones de ejecución: Cualquier condición de ejecución
  - **Error type:** Lexical Confusion

- **Query** `OEB180caa`: hincas con cable tensor de acero para el tendido de cables sobre una trinchera de tierra diurno excepcional i 5 horas volumen relevante
  - **Retrieved** `OEB180aaa`: Hincas con cable tensor de acero para el tendido de cables sobre una trinchera de tierra. Trabajo:Diurno Banda de mantenimiento:  i >= 5 horas Condiciones de ejecución: Volumen relevante
  - **Error type:** Lexical Confusion

### Numeric Mismatch
- **Query** `OEB290cbebb`: canalización hormigonada 3 t polietileno libre de halógenos de 50 mm bajo vías cualquier franja horaria 3 i 5 horas volumen escaso
  - **Retrieved** `OEB290ebebb`: Canalización hormigonada de  5  tubos de polietileno libre de halógenos de 50 mm de diámetro en cruce bajo vías, incluso el descerne y la entibación de los costados y la posterior reposición del balasto retirado, el relleno y compactado de la zanja,  el suministro y montaje de los tubos y hormigón tipo HE-20 sin vibrar, la prueba de los conductos, el transporte y la retirada de los productos al lugar de empleo  Trabajo: Cualquier franja horaria Banda de mantenimiento: 3 <= i < 5 horas Condiciones de ejecución: Volumen escaso
  - **Error type:** Numeric Mismatch

- **Query** `OEB280cbbba`: canalización hormigonada 3 t polietileno libre de halógenos de 40 mm bajo vías nocturno 3 i 5 horas volumen relevante
  - **Retrieved** `OEB280ebbba`: Canalización hormigonada de  5  tubos de polietileno libre de halógenos de 40 mm de diámetro en cruce bajo vías, incluso el descerne y la entibación de los costados y la posterior reposición del balasto retirado, el relleno y compactado de la zanja,  el suministro y montaje de los tubos y hormigón tipo HE-20 sin vibrar, la prueba de los conductos, el transporte y la retirada de los productos al lugar de empleo  Trabajo: Nocturno Banda de mantenimiento: 3 <= i < 5 horas Condiciones de ejecución: Volumen relevante
  - **Error type:** Numeric Mismatch

### Other
- **Query** `OEB250bbbcc`: suministro y montaje de canalización de 4 tubos de acero galvanizado de 100 mm de diámetro para instalaciones cms en transiciones entre diferentes plataformas nocturno excepcional i 3 horas cualquier condición de ejecución
  - **Retrieved** `OEB250abbcc`: Suministro de canalización de 4 tubos de acero galvanizado de 100mm de diámetro para instalaciones CMS en transiciones entre diferentes plataformas.  Trabajo: Nocturno Excepcional Banda de mantenimiento: i < 3 horas Condiciones de ejecución: Cualquier condición de ejecución
  - **Error type:** Other

- **Query** `OEB250babab`: suministro y montaje de canalización de 1 o 2 tubos de acero galvanizado de 100 mm de diámetro para instalaciones cms en transiciones entre diferentes plataformas nocturno excepcional i 5 horas voumen escaso
  - **Retrieved** `OEB250aabab`: Suministro de canalización de 1 o 2 tubos de acero galvanizado de 100mm de diámetro para instalaciones CMS en transiciones entre diferentes plataformas.  Trabajo: Nocturno Excepcional Banda de mantenimiento:  i >= 5 horas Condiciones de ejecución: Volumen escaso
  - **Error type:** Other


## Method: bge_m3_colbert

### Lexical Confusion
- **Query** `OEB120cabb`: suministro y ejecución de embocadura canalización de 6 tubos en arqueta o cámara existente (diurno/3 <== i < "5" horas/volumen escaso)
  - **Retrieved** `OEB120ccbb`: Suministro y ejecución de embocadura canalización de 6 tubos en arqueta o cámara existente Trabajo: Diurno Excepcional Banda de mantenimiento: 3 <= i < 5 horas Condiciones de ejecución: Volumen escaso
  - **Error type:** Lexical Confusion

- **Query** `OEB120aedc`: suministro y ejecución de embocadura canalización de 1 o 2 tubos en arqueta o cámara existente (cualquier franja horaria/no necesita intervalo/cualquier condición de ejecución)
  - **Retrieved** `OEB120afdc`: Suministro y ejecución de embocadura canalización de 1 o 2 tubos en arqueta o cámara existente Trabajo: Cualquier franja horaria excepcional Banda de mantenimiento: No necesita intervalo Condiciones de ejecución: Cualquier condición de ejecución
  - **Error type:** Lexical Confusion

### Numeric Mismatch
- **Query** `OEB280egecb`: canalización hormigonada 5 t, polietileno libre de halógenos de 40 mm, en balasto. (cualquier franja horaria/i < "3" horas/volumen escaso)
  - **Retrieved** `OEB280egfbb`: Canalización hormigonada de  5  tubos de polietileno libre de halógenos de 40 mm de diámetro en zona de balasto, incluso el descerne y la entibación de los costados y la posterior reposición del balasto retirado, el relleno y compactado de la zanja,  el suministro y montaje de los tubos y hormigón tipo HE-20 sin vibrar, la prueba de los conductos, el transporte y la retirada de los productos al lugar de empleo  Trabajo: Cualquier franja horaria excepcional Banda de mantenimiento: 3 <= i < 5 horas Condiciones de ejecución: Volumen escaso
  - **Error type:** Numeric Mismatch

- **Query** `OEB030chdca`: canalización hormigonada 3 t, polietileno libre de halógenos de 110 mm, con topo. (nocturno excepcional/i < "3" horas/volumen relevante)
  - **Retrieved** `OEB030cadba`: Canalización hormigonada de  3  tubos de polietileno libre de halógenos de 110 mm de diámetro en cualquier clase de terreno, excepto roca, incluso  el relleno y compactado de la zanja,  el suministro y montaje de los tubos y hormigón tipo HE-20 sin vibrar, la prueba de los conductos, el transporte y la retirada de los productos al lugar de empleo  Trabajo: Nocturno Excepcional Banda de mantenimiento: 3 <= i < 5 horas Condiciones de ejecución: Volumen relevante
  - **Error type:** Numeric Mismatch

### Other
- **Query** `OEB110bda`: tubería de pvc de 110 mm de diámetro para drenaje de arqueta (nocturno/no necesita intervalo/volumen relevante)
  - **Retrieved** `OEB110dda`: Suministro y colocación de tubería de PVC de 110 mm de diámetro para drenaje de arqueta desde centro de arqueta a pie de talud incluyendo relleno y compactación de tierras. Trabajo: Nocturno Excepcional Banda de mantenimiento: No necesita intervalo Condiciones de ejecución: Volumen relevante
  - **Error type:** Other

- **Query** `OEB110abc`: tubería de pvc de 110 mm de diámetro para drenaje de arqueta (diurno/3 <== i < "5" horas/cualquier condición de ejecución)
  - **Retrieved** `OEB110cbc`: Suministro y colocación de tubería de PVC de 110 mm de diámetro para drenaje de arqueta desde centro de arqueta a pie de talud incluyendo relleno y compactación de tierras. Trabajo: Diurno Excepcional Banda de mantenimiento: 3 <= i < 5 horas Condiciones de ejecución: Cualquier condición de ejecución
  - **Error type:** Other


## Method: hyb_bm25_uni__bge_colbert__tfidf_char_3_5

### Other
- **Query** `OEB300cfedb`: 
  - **Retrieved** `OEB300caedb`: Canalización hormigonada de  3  tubos de polietileno libre de halógenos de 90 mm de diámetro en cualquier clase de terreno, excepto roca, incluso  el relleno y compactado de la zanja,  el suministro y montaje de los tubos y hormigón tipo HE-20 sin vibrar, la prueba de los conductos, el transporte y la retirada de los productos al lugar de empleo  Trabajo: Cualquier franja horaria Banda de mantenimiento: No necesita intervalo Condiciones de ejecución: Volumen escaso
  - **Error type:** Other

- **Query** `OEB230khbdb`: 
  - **Retrieved** `OEB230kabdb`: Canalización hormigonada de  24  tubos de polietileno libre de halógenos de 200 mm de diámetro en cualquier clase de terreno, excepto roca, incluso  el relleno y compactado de la zanja,  el suministro y montaje de los tubos y hormigón tipo HE-20 sin vibrar, la prueba de los conductos, el transporte y la retirada de los productos al lugar de empleo  Trabajo: Nocturno Banda de mantenimiento: No necesita intervalo Condiciones de ejecución: Volumen escaso
  - **Error type:** Other


