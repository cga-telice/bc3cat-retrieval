"""The S9 prompts — S9 work item 1 (d).

Zero-shot, in Spanish, naming the domain and nothing from any leaf (S9 design, Design constraints): no
catalogue text, no parameter, no example query. They were checked for format only, on at most 20 dev
queries, and no retrieval was run before they were committed. `PROMPT_SHA256` is recorded before the
first scored run; changing a template after that is an amendment, and changes every cache key.

- **HYDE** (transform `hyde`): the model writes the catalogue entry the query describes. The query is then
  the original text followed by the generated one (work item 2).
- **REWRITE** (transform `rewrite`): the model restates the query in the catalogue's canonical style, and
  the rewrite replaces it.
"""

from __future__ import annotations

import json
import re

from query_rewrite.llm import sha256_text

HYDE = (
    "Eres redactor técnico del catálogo de precios de obra civil de ADIF (Administrador de "
    "Infraestructuras Ferroviarias). A partir de la consulta siguiente, escribe la descripción técnica "
    "de la partida tal como aparecería en el catálogo: un solo párrafo en español, con el elemento de "
    "obra, sus materiales, dimensiones y unidades, y las condiciones de ejecución que correspondan. "
    "Devuelve solo la descripción, sin títulos, comillas ni comentarios.\n\n"
    "Consulta: {query}\n\n"
    "Descripción:"
)

REWRITE = (
    "Reescribe la consulta siguiente, que describe una partida del catálogo de precios de obra civil de "
    "ADIF (Administrador de Infraestructuras Ferroviarias), en el estilo normalizado del catálogo: "
    "números escritos en cifras, unidades con su abreviatura habitual (mm, cm, m, m2, m3, kg, t, h) y "
    "terminología técnica de construcción. Conserva todos los datos y valores de la consulta y no "
    "añadas información que no contenga. Responde solo con un objeto JSON de la forma "
    '{{"consulta": "..."}}, cuyo valor sea la consulta reescrita, sin notas ni comentarios.\n\n'
    "Consulta: {query}"
)

PROMPTS = {"hyde": HYDE, "rewrite": REWRITE}

#: Output format asked of the server. The format check (logs/S9/format_check.out) found the plain-text
#: rewrite echoing a "Consulta reescrita:" label in 4 of 10 outputs and appending a note in 1; asking for
#: a JSON object removes both without touching what the prompt asks for.
FORMAT_FOR = {"hyde": None, "rewrite": "json"}

#: The model each LLM transform uses (S9 design, work item 2).
MODEL_FOR = {"hyde": "qwen2.5:14b", "rewrite": "qwen2.5:14b"}

PROMPT_SHA256 = {
    name: sha256_text(json.dumps([template, FORMAT_FOR[name]], ensure_ascii=False)) for name, template in PROMPTS.items()
}


def render(transform: str, query: str) -> str:
    return PROMPTS[transform].format(query=query.strip())


_LEADING_LABEL = re.compile(r"^\s*(descripci[oó]n|consulta reescrita)\s*:\s*", re.IGNORECASE)


def parse(transform: str, response: str) -> str:
    """The generated text, from the server's response. Deterministic; a response that cannot be parsed
    raises, and the caller records it rather than inventing a query."""
    if FORMAT_FOR[transform] == "json":
        value = json.loads(response)["consulta"]
        if not isinstance(value, str):
            raise ValueError(f"`consulta` is {type(value).__name__}, not text")
        text = value
    else:
        text = response
    return _LEADING_LABEL.sub("", text.strip()).strip()
