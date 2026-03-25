"""Prompt templates for the structured retrieval pipeline.

Contains prompt templates for Stage 2 (LLM parameter extraction/classification).
Prompts are in Spanish to match the catalog language.

Five modes:
  - Extraction (Sprint 04): LLM copies/paraphrases values from the query.
  - Classification (Sprint 07): LLM selects from a closed set of schema values.
  - Two-step (Sprint 08): Step 1 freely extracts, Step 2 matches to schema.
  - Parameter-aware (Sprint 09): Step 1 detects per-parameter info, Step 2 matches non-null only.
  - Paraaware2 (Sprint 12): Per-axis detection+classification, one LLM call per axis with values shown.
"""


def build_extraction_prompt(
    concept: str, axes: dict[str, list[str]], query: str
) -> str:
    """Build the parameter extraction prompt for a query.

    Args:
        concept: Human-readable concept name (e.g., "CANALIZACIÓN PARA LÍNEA...")
        axes: {axis_label: [possible_values]} from the concept schema
        query: The user query text

    Returns:
        Formatted prompt string in Spanish
    """
    # Build the parameter schema section
    schema_lines = []
    for axis_label, values in axes.items():
        values_str = ", ".join(values)
        schema_lines.append(f"{axis_label}: {values_str}")
    schema_section = "\n".join(schema_lines)

    prompt = (
        "Eres un asistente que extrae parámetros de consultas de construcción ferroviaria.\n"
        "\n"
        f"Concepto: {concept}\n"
        "\n"
        "Esquema de parámetros:\n"
        f"{schema_section}\n"
        "\n"
        f'Consulta: "{query}"\n'
        "\n"
        "Extrae el valor de cada parámetro que se pueda inferir de la consulta.\n"
        "Responde SOLO con un JSON con exactamente las claves del esquema.\n"
        "Si no puedes determinar el valor de un eje, usa null.\n"
        "\n"
        "Respuesta:"
    )
    return prompt


def build_classification_prompt(
    concept: str, axes: dict[str, list[str]], query: str
) -> str:
    """Build a classification prompt that asks the LLM to SELECT from schema values.

    Unlike the extraction prompt (which asks the LLM to copy/paraphrase values),
    this prompt presents values as a closed set and asks the LLM to pick one.
    This eliminates normalization errors (e.g. ``1,10 m`` -> ``1.10``).

    Args:
        concept: Human-readable concept name (e.g., "CANALIZACION PARA LINEA...")
        axes: {axis_label: [possible_values]} from the concept schema
        query: The user query text

    Returns:
        Formatted classification prompt string in Spanish (ASCII-safe)
    """
    # Build the parameter schema section with pipe-separated values
    schema_lines = []
    for axis_label, values in axes.items():
        values_str = " | ".join(values)
        schema_lines.append(f"{axis_label}: {values_str}")
    schema_section = "\n".join(schema_lines)

    prompt = (
        "Eres un asistente que clasifica consultas de construccion ferroviaria "
        "segun los parametros de un concepto.\n"
        "\n"
        f"Concepto: {concept}\n"
        "\n"
        "Para cada parametro, indica cual de los valores permitidos corresponde a la consulta.\n"
        "Responde UNICAMENTE con uno de los valores exactos listados o null.\n"
        "NO modifiques, reformatees ni parafrasees los valores.\n"
        "\n"
        "Parametros y valores permitidos:\n"
        f"{schema_section}\n"
        "\n"
        f'Consulta: "{query}"\n'
        "\n"
        "Responde SOLO con un JSON con exactamente las claves indicadas.\n"
        "Cada valor debe ser uno de los listados arriba (copiado exactamente) o null.\n"
        "\n"
        "Respuesta:"
    )
    return prompt


def build_twostep_extract_prompt(
    concept: str, axes: dict[str, list[str]], query: str
) -> str:
    """Step 1 of two-step extraction: free-form value identification.

    Asks the LLM to describe what value each axis has based on the query,
    without showing schema values. No formatting constraints on output values.
    """
    axis_list = "\n".join(f"- {label}" for label in axes)

    prompt = (
        "Eres un asistente que analiza consultas de construccion ferroviaria.\n"
        "\n"
        f"Concepto: {concept}\n"
        "\n"
        "La consulta describe un elemento con estos parametros:\n"
        f"{axis_list}\n"
        "\n"
        f'Consulta: "{query}"\n'
        "\n"
        "Para cada parametro, describe brevemente que valor indica la consulta.\n"
        'Si la consulta no menciona un parametro, indica "no especificado".\n'
        "\n"
        "Responde SOLO con un JSON con las claves de los parametros.\n"
        "\n"
        "Respuesta:"
    )
    return prompt


def build_twostep_match_prompt(
    concept: str, axes: dict[str, list[str]], extracted: dict[str, str | None]
) -> str:
    """Step 2 of two-step extraction: match free-form values to schema.

    Given the LLM's free-form extraction from Step 1, asks the LLM to select
    the closest matching schema value for each axis.
    """
    # Build extracted values section
    extracted_lines = []
    for label, value in extracted.items():
        display = value if value else "no especificado"
        extracted_lines.append(f"{label}: {display}")
    extracted_section = "\n".join(extracted_lines)

    # Build schema values section (pipe-separated)
    schema_lines = []
    for label, values in axes.items():
        values_str = " | ".join(values)
        schema_lines.append(f"{label}: {values_str}")
    schema_section = "\n".join(schema_lines)

    prompt = (
        "Eres un asistente que asocia valores extraidos con los valores "
        "oficiales de un catalogo de construccion ferroviaria.\n"
        "\n"
        f"Concepto: {concept}\n"
        "\n"
        "Valores extraidos de una consulta:\n"
        f"{extracted_section}\n"
        "\n"
        "Valores permitidos en el catalogo:\n"
        f"{schema_section}\n"
        "\n"
        "Para cada parametro, indica cual de los valores del catalogo "
        "corresponde al valor extraido.\n"
        "Responde con el valor exacto del catalogo (copiado tal cual) "
        "o null si no hay correspondencia.\n"
        "\n"
        "Responde SOLO con un JSON con exactamente las claves indicadas.\n"
        "\n"
        "Respuesta:"
    )
    return prompt


def build_paraaware_extract_prompt(
    concept: str, axes: dict[str, list[str]], query: str
) -> str:
    """Step 1 of parameter-aware two-step: structured parameter detection.

    For each axis, asks the LLM whether the query contains relevant
    information for that parameter and, if so, to describe it briefly.
    Unlike twostep Step 1, this explicitly frames the task as detection
    ("does the query contain info about X?") rather than open extraction.
    """
    axis_list = "\n".join(f"- {label}" for label in axes)

    prompt = (
        "Eres un asistente que analiza consultas de construccion ferroviaria.\n"
        "\n"
        f"Concepto: {concept}\n"
        "\n"
        "Analiza la siguiente consulta y determina si contiene informacion sobre "
        "cada uno de los parametros indicados.\n"
        "\n"
        "Parametros a buscar:\n"
        f"{axis_list}\n"
        "\n"
        f'Consulta: "{query}"\n'
        "\n"
        "Para cada parametro:\n"
        "- Si la consulta contiene informacion relevante, indica que dice la consulta "
        "sobre ese parametro (en tus propias palabras, brevemente).\n"
        "- Si la consulta NO contiene informacion sobre ese parametro, indica null.\n"
        "\n"
        "Responde SOLO con un JSON con las claves de los parametros.\n"
        "\n"
        "Respuesta:"
    )
    return prompt


def build_paraaware_match_prompt(
    concept: str, axes: dict[str, list[str]], extracted: dict[str, str | None]
) -> str:
    """Step 2 of parameter-aware two-step: match to catalog values.

    Given only the non-null axes from Step 1, asks the LLM to select
    the closest matching schema value for each axis.
    Only non-null axes are included (null axes are pre-filtered).
    """
    # Build extracted values section (only non-null axes)
    extracted_lines = []
    for label, value in extracted.items():
        extracted_lines.append(f"{label}: {value}")
    extracted_section = "\n".join(extracted_lines)

    # Build schema values section (only for non-null axes)
    schema_lines = []
    for label in extracted:
        values = axes[label]
        values_str = " | ".join(values)
        schema_lines.append(f"{label}: {values_str}")
    schema_section = "\n".join(schema_lines)

    prompt = (
        "Eres un asistente que asocia valores extraidos con valores de un "
        "catalogo oficial.\n"
        "\n"
        f"Concepto: {concept}\n"
        "\n"
        "De una consulta se han extraido los siguientes valores para cada parametro:\n"
        f"{extracted_section}\n"
        "\n"
        "Los valores oficiales del catalogo para cada parametro son:\n"
        f"{schema_section}\n"
        "\n"
        "Para cada parametro, indica cual de los valores oficiales corresponde al "
        "valor extraido. Debes responder con el valor exacto del catalogo, copiado "
        "tal cual, o null si el valor extraido no corresponde a ninguno.\n"
        "\n"
        "Responde SOLO con un JSON con las claves de los parametros.\n"
        "\n"
        "Respuesta:"
    )
    return prompt


def build_paraaware2_step1_prompt(
    concept: str, axis_label: str, values: list[str], query: str
) -> str:
    """Step 1 of paraaware2: per-axis detection+classification.

    For a single axis, shows all possible values and asks the LLM
    to either select the matching value or respond null.
    One call per axis (N calls total for N axes).

    Args:
        concept: Human-readable concept name
        axis_label: The parameter name (e.g., "TERRENO")
        values: List of possible values for this axis
        query: The user query text

    Returns:
        Formatted prompt string in Spanish (ASCII-safe)
    """
    values_str = " | ".join(values)

    prompt = (
        "Eres un asistente que clasifica consultas de construccion ferroviaria.\n"
        "\n"
        f"Concepto: {concept}\n"
        "\n"
        f"Parametro: {axis_label}\n"
        f"Valores permitidos: {values_str}\n"
        "\n"
        f'Consulta: "{query}"\n'
        "\n"
        f'Si la consulta indica un valor para el parametro "{axis_label}", '
        "responde con el valor exacto de la lista (copiado tal cual). "
        "Si no, responde null.\n"
        "\n"
        "Responde UNICAMENTE con el valor exacto o null. Sin explicaciones.\n"
        "\n"
        "Respuesta:"
    )
    return prompt


def build_paraaware2_step2_prompt(
    axis_label: str, values: list[str], extracted: str
) -> str:
    """Step 2 fallback for paraaware2: match unexpected text to schema values.

    Only called when Step 1 produced an unexpected response (not an exact
    match and not null). Asks LLM to select the closest matching value.

    Args:
        axis_label: The parameter name
        values: List of possible values for this axis
        extracted: The unexpected text from Step 1

    Returns:
        Formatted prompt string in Spanish (ASCII-safe)
    """
    values_str = " | ".join(values)

    prompt = (
        f'Un sistema extrajo el texto "{extracted}" para el parametro "{axis_label}".\n'
        "\n"
        f"Los valores oficiales son: {values_str}\n"
        "\n"
        "Indica cual de los valores oficiales corresponde al texto extraido.\n"
        "Responde UNICAMENTE con el valor exacto de la lista o null.\n"
        "\n"
        "Respuesta:"
    )
    return prompt
