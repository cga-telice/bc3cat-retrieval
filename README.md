# Proyecto de procesamiento de lenguaje natural

Este proyecto realiza procesamiento de lenguaje natural (NLP) utilizando modelos de la librería Hugging Face, almacenamiento de vectores con Milvus y almacenamiento de objetos con MinIO. Todo el sistema se despliega mediante Docker Compose.

## Requisitos

* Docker
* Docker Compose

## Instalación y arranque

1. Clonar el repositorio:

```bash
git clone <URL_DEL_REPOSITORIO>
cd <directorio_del_proyecto>
```

2. Levantar el entorno completo con Docker Compose:

```bash
docker-compose up --build
```

> Nota: el primer arranque puede tardar mientras se construyen las imágenes y se descargan las dependencias.

3. El sistema expondrá el servicio principal en `http://localhost:8000` (o el puerto especificado en el docker-compose).

## Servicios incluidos en Docker Compose

* **Aplicación principal (app)**: ejecuta el procesamiento principal.
* **Milvus**: base de datos vectorial para almacenamiento de embeddings.
* **MinIO**: almacenamiento de objetos para datasets y procesamiento de datos.
* **Ollama**: servicio auxiliar (posiblemente para modelos LLM locales).
* **etcd**: servicio de coordinación de Milvus.

## Estructura del proyecto

### Código fuente (`src/`)

* `01_parse/` → módulos de parsing y preprocesamiento de datos.
* `02_indexes/` → módulos de indexación y gestión de índices.
* `utils/` → funciones utilitarias compartidas.

### Datos (`data/`)

* `raw/` → datos originales sin procesar.
* `processed/` → datos listos para ser utilizados en el pipeline.
* `intermediate/` → resultados intermedios del procesamiento.
* `indexes/` → índices generados.

## Instrucciones de procesamiento de datos

En la carpeta `data/raw` se encuentra el archivo `BPA_2024_v2.txt`, que contiene el cuadro de precios de ADIF en formato BC3. A partir de él he generado un fichero modificado `BPA_2024_v2_OEB_mod.txt` para que las descripciones de unidades del subcapítulo **OEB** sean más expresivas (por ejemplo: "Volumen Relevante" en lugar de "R").

### Pipeline de parseado

El pipeline de procesamiento se ejecuta de forma secuencial a través de los cuadernos numerados:

- `S01_...` hasta `S08_...`

Hay que prestar especial atención a los nombres de los archivos de entrada y salida de cada cuaderno.

Estos cuadernos procesan el archivo `BPA_2024_v2.txt` y generan los datasets intermedios.

### Extracción del subcapítulo OEB

Una vez finalizado el parseado completo, se ejecuta el cuaderno:

- `Generate_OEB_dataset`

Este cuaderno filtra y extrae exclusivamente los elementos pertenecientes al subcapítulo **OEB**.

### Generación y análisis de índices

Los índices vectoriales se generan y analizan mediante los siguientes cuadernos:

- Generación: `I#_[índice]_Builder`
- Análisis: `I#_[índice]_Analysis`

Para su ejecución, los archivos de partida necesarios se encuentran en `data/processed`:

- `[Capitulo]_resumen.pkl`
- `[Capitulo]_texto.pkl`


## Dependencias principales

Las dependencias de Python se encuentran en `requirements.txt`, e incluyen:

* `transformers==4.26.0`
* `sentence-transformers==2.2.2`
* `huggingface_hub==0.13.4`

Estas versiones garantizan compatibilidad con PyTorch 2.2.2.

## Contribuciones



## Licencia


