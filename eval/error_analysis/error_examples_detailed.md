# Representative Error Examples (Section 4.8)

## Method: bm25_unigram

### Lexical Confusion
- **Query** `OEB250aabec`: suministro de canalización de 1 o 2 tubos de acero galvanizado de 100 mm de diámetro para instalaciones cms en transiciones entre diferentes plataformas nocturno excepcional no aplica cualquier condición de ejecución
  - **Retrieved** `OEB250aacec`: Suministro de canalización de 1 o 2 tubos de acero galvanizado de 100mm de diámetro para instalaciones CMS en transiciones entre diferentes plataformas.  Trabajo: No aplica Banda de mantenimiento: No aplica Condiciones de ejecución: Cualquier condición de ejecución
  - **Error type:** Lexical Confusion

- **Query** `OEB180fda`: hincas con cable tensor de acero para el tendido de cables sobre una trinchera de tierra cualquier franja horaria excepcional no necesita intervalo volumen relevante
  - **Retrieved** `OEB180eda`: Hincas con cable tensor de acero para el tendido de cables sobre una trinchera de tierra. Trabajo:Cualquier franja horaria Banda de mantenimiento: No necesita intervalo Condiciones de ejecución: Volumen relevante
  - **Error type:** Lexical Confusion

### Numeric Mismatch
- **Query** `OEB170agfda`: canalización metálica superficial con 1 tubos de acero galvanizado de 6 de diámetro cualquier franja horaria excepcional no necesita intervalo volumen relevante
  - **Retrieved** `OEB170eafda`: Canalización metálica superficial con  6  tubos de acero galvanizado de 1'' de diámetro de medida interior en taludes de excesiva inclinación o rocosos, sobre hastial de túnel o puente, incluye sellado de sus extremos, herramientas y medios auxiliares necesarios para la correcta ejecución de la unidad.. Trabajo: Cualquier franja horaria excepcional Banda de mantenimiento: No necesita intervalo Condiciones de ejecución: Volumen relevante
  - **Error type:** Numeric Mismatch

- **Query** `OEB170beeca`: canalización metálica superficial con 2 tubos de acero galvanizado de 4 de diámetro cualquier franja horaria i 3 horas volumen relevante
  - **Retrieved** `OEB170dbeca`: Canalización metálica superficial con  4  tubos de acero galvanizado de 2'' de diámetro de medida interior en taludes de excesiva inclinación o rocosos, sobre hastial de túnel o puente, incluye sellado de sus extremos, herramientas y medios auxiliares necesarios para la correcta ejecución de la unidad.. Trabajo: Cualquier franja horaria Banda de mantenimiento: i < 3 horas Condiciones de ejecución: Volumen relevante
  - **Error type:** Numeric Mismatch

### Other
- **Query** `OEB250bcceb`: suministro y montaje de canalización de 6 tubos de acero galvanizado de 100 mm de diámetro para instalaciones cms en transiciones entre diferentes plataformas no aplica no aplica voumen escaso
  - **Retrieved** `OEB250acceb`: Suministro de canalización de 6 tubos de acero galvanizado de 100mm de diámetro para instalaciones CMS en transiciones entre diferentes plataformas.  Trabajo: No aplica Banda de mantenimiento: No aplica Condiciones de ejecución: Volumen escaso
  - **Error type:** Other

- **Query** `OEB250babaa`: suministro y montaje de canalización de 1 o 2 tubos de acero galvanizado de 100 mm de diámetro para instalaciones cms en transiciones entre diferentes plataformas nocturno excepcional i 5 horas volumen relevante
  - **Retrieved** `OEB250aabaa`: Suministro de canalización de 1 o 2 tubos de acero galvanizado de 100mm de diámetro para instalaciones CMS en transiciones entre diferentes plataformas.  Trabajo: Nocturno Excepcional Banda de mantenimiento:  i >= 5 horas Condiciones de ejecución: Volumen relevante
  - **Error type:** Other


## Method: bge_m3_colbert

### Lexical Confusion
- **Query** `OEB120aaca`: suministro y ejecución de embocadura canalización de 1 o 2 tubos en arqueta o cámara existente (diurno/i < "3" horas/volumen relevante)
  - **Retrieved** `OEB120acca`: Suministro y ejecución de embocadura canalización de 1 o 2 tubos en arqueta o cámara existente Trabajo: Diurno Excepcional Banda de mantenimiento: i < 3 horas Condiciones de ejecución: Volumen relevante
  - **Error type:** Lexical Confusion

- **Query** `OEB120aecb`: suministro y ejecución de embocadura canalización de 1 o 2 tubos en arqueta o cámara existente (cualquier franja horaria/i < "3" horas/volumen escaso)
  - **Retrieved** `OEB120afcb`: Suministro y ejecución de embocadura canalización de 1 o 2 tubos en arqueta o cámara existente Trabajo: Cualquier franja horaria excepcional Banda de mantenimiento: i < 3 horas Condiciones de ejecución: Volumen escaso
  - **Error type:** Lexical Confusion

### Numeric Mismatch
- **Query** `OEB020aafbc`: canalización hormigonada de 2 t, pvc 110 mm, normal. (cualquier franja horaria excepcional/3 >== i > "5" horas/cualquier condición de ejecución)
  - **Retrieved** `OEB020aafac`: Canalización hormigonada de  2  tubos de PVC de 110 mm de diámetro en cualquier clase de terreno, excepto roca, incluso  el relleno y el compactado de la zanja,  el suministro y el montaje de los tubos y hormigón tipo HE-20 sin vibrar, la prueba de los conductos, el transporte y la retirada de los productos al lugar de empleo.  Trabajo: Cualquier franja horaria excepcional Banda de mantenimiento:  i >= 5 horas Condiciones de ejecución: Cualquier condición de ejecución
  - **Error type:** Numeric Mismatch

- **Query** `OEB290abebc`: canalización hormigonada 1 t, polietileno libre de halógenos de 50 mm, bajo vías. (cualquier franja horaria/3 <== i < "5" horas/cualquier condición de ejecución)
  - **Retrieved** `OEB290abfbc`: Canalización hormigonada de  1  tubos de polietileno libre de halógenos de 50 mm de diámetro en cruce bajo vías, incluso el descerne y la entibación de los costados y la posterior reposición del balasto retirado, el relleno y compactado de la zanja,  el suministro y montaje de los tubos y hormigón tipo HE-20 sin vibrar, la prueba de los conductos, el transporte y la retirada de los productos al lugar de empleo  Trabajo: Cualquier franja horaria excepcional Banda de mantenimiento: 3 <= i < 5 horas Condiciones de ejecución: Cualquier condición de ejecución
  - **Error type:** Numeric Mismatch

### Other
- **Query** `OEB250bcaec`: suministro y montaje de canalización de 6 tubos de acero galvanizado de 100mm de diámetro para instalaciones cms en transiciones entre diferentes plataformas.(diurno excepcional/no aplica/cualquier condición de ejecución)
  - **Retrieved** `OEB250acaec`: Suministro de canalización de 6 tubos de acero galvanizado de 100mm de diámetro para instalaciones CMS en transiciones entre diferentes plataformas.  Trabajo: Diurno Excepcional Banda de mantenimiento: No aplica Condiciones de ejecución: Cualquier condición de ejecución
  - **Error type:** Other

- **Query** `OEB150ebb`: limpieza de tubo de canalización existente. (cualquier franja horaria/3 <== i < "5" horas/volumen escaso)
  - **Retrieved** `OEB150fbb`: Limpieza de tubo de canalización existente incluyendo la localización de obstrucciones y su limpieza, previo al tendido de nuevos cables. Trabajo: Cualquier franja horaria excepcional Banda de mantenimiento: 3 <= i < 5 horas Condiciones de ejecución: Volumen escaso.
  - **Error type:** Other


## Method: hyb_bm25_uni__bge_colbert__tfidf_char_3_5

### Other
- **Query** `OEB030gfdbb`: 
  - **Retrieved** `OEB030gadab`: Canalización hormigonada de  8  tubos de polietileno libre de halógenos de 110 mm de diámetro en cualquier clase de terreno, excepto roca, incluso  el relleno y compactado de la zanja,  el suministro y montaje de los tubos y hormigón tipo HE-20 sin vibrar, la prueba de los conductos, el transporte y la retirada de los productos al lugar de empleo  Trabajo: Nocturno Excepcional Banda de mantenimiento:  i >= 5 horas Condiciones de ejecución: Volumen escaso
  - **Error type:** Other

- **Query** `OEB300ifdda`: 
  - **Retrieved** `OEB300iadda`: Canalización hormigonada de  16  tubos de polietileno libre de halógenos de 90 mm de diámetro en cualquier clase de terreno, excepto roca, incluso  el relleno y compactado de la zanja,  el suministro y montaje de los tubos y hormigón tipo HE-20 sin vibrar, la prueba de los conductos, el transporte y la retirada de los productos al lugar de empleo  Trabajo: Nocturno Excepcional Banda de mantenimiento: No necesita intervalo Condiciones de ejecución: Volumen relevante
  - **Error type:** Other


