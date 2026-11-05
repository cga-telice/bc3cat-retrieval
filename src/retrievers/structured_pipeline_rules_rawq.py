# /src/retrievers/structured_pipeline_rules_rawq.py
# Proxy: identico a structured_pipeline_rules, pero su indice declara
# text_field="text". Sirve para medir cuanto depende el pipeline de que la
# etapa 1 reciba el texto normalizado en vez del texto crudo que indexo E5.
from .structured_pipeline import load  # noqa: F401
