# Sprint 04 — LLM Parameter Extractor (Stage 2) with Ollama in Docker

**Tasks from backlog:** B3 (LLM parameter extractor), partial infrastructure
**Prerequisites:** Sprint 00 (schema JSON), Sprint 01 (catalog lookup for integration testing)

---

## Context

Stage 1 (item-level E5 retrieval → parent_key) and Stage 3 (catalog lookup) are done. This sprint builds Stage 2 — the LLM-based parameter extractor. It also sets up Ollama as a Docker service so the full setup remains self-contained and reproducible.

Read `CLAUDE.md` and `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` for full project context.

### Existing Docker setup

The repo already has:
- `docker-compose.yml` with services: Jupyter (port 8888) and BGE-M3 API (port 8800)
- `Dockerfile.bge-m3` for the BGE-M3 service
- Repo mounted at `/work` inside containers

We'll add Ollama as a third service following the same pattern.

---

## Objectives

### 1. Add Ollama to Docker

Add an Ollama service to `docker-compose.yml`:

```yaml
ollama:
  image: ollama/ollama:0.17.7
  ports:
    - "11434:11434"
  volumes:
    - ollama-models:/root/.ollama
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
  restart: unless-stopped
```

Add the `ollama-models` volume to persist downloaded models across container restarts.

**Why pin to `0.17.7`?** The `latest` tag on Docker Hub has historically lagged behind actual releases, and unpinned versions risk breaking reproducibility. Document this version in `CLAUDE.md` / `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` so future researchers know exactly what was used.

**Important:**
- The Ollama API will be accessible from the Jupyter container at `http://ollama:11434` (Docker service-to-service networking) or from the host at `http://localhost:11434`.
- The Jupyter container (where pipeline code runs) needs to reach Ollama. Check the docker-compose network configuration — all services should be on the same Docker network. If not, ensure they share one.
- GPU passthrough uses the NVIDIA Container Toolkit. The BGE-M3 service likely already has a similar GPU config — follow that pattern.

After starting the service:
```bash
docker-compose up -d ollama
docker-compose exec ollama ollama pull llama3.1:8b
```

Verify Ollama is running and the model is loaded:
```bash
curl http://localhost:11434/api/tags
# Should list llama3.1:8b
```

### 2. Create the prompt template module

Create `src/pipeline/prompts.py` with the prompt template for parameter extraction:

```python
def build_extraction_prompt(concept: str, axes: dict[str, list[str]], query: str) -> str:
    """
    Build the parameter extraction prompt.
    
    Args:
        concept: Human-readable concept name
        axes: {axis_label: [possible_values]} from the schema
        query: The user query text
    
    Returns:
        Formatted prompt string
    """
    ...
```

The prompt (in Spanish, matching the catalog language):

```
Eres un asistente que extrae parámetros de consultas de construcción ferroviaria.

Concepto: {concept}

Esquema de parámetros:
{axis_label_1}: {value_1_a}, {value_1_b}, ...
{axis_label_2}: {value_2_a}, {value_2_b}, ...
...

Consulta: "{query}"

Extrae el valor de cada parámetro que se pueda inferir de la consulta.
Responde SOLO con un JSON con exactamente las claves del esquema.
Si no puedes determinar el valor de un eje, usa null.

Respuesta:
```

### 3. Create the LLM parameter extractor module

Create `src/pipeline/param_extractor.py`:

```python
class LLMParamExtractor:
    def __init__(self, schema_path: str, ollama_base_url: str = "http://ollama:11434",
                 model: str = "llama3.1:8b", temperature: float = 0.0):
        """Load schema, configure Ollama connection."""
        ...

    def extract(self, parent_key: str, query: str) -> dict[str, str | None]:
        """
        Extract parameter values from a query for a given concept group.
        
        Returns:
            {axis_label: extracted_value | None} for each axis in the schema
        """
        ...

    def extract_batch(self, items: list[tuple[str, str]]) -> list[dict[str, str | None]]:
        """
        Batch extraction for multiple (parent_key, query) pairs.
        Sequential calls to Ollama (no native batch API).
        Includes progress reporting for long batches.
        """
        ...
```

**Implementation notes:**

- Use the Ollama REST API directly (`POST /api/generate`). Do NOT add the `ollama` Python package as a dependency — use `requests` (already available) to keep dependencies minimal. Example:
  ```python
  response = requests.post(f"{base_url}/api/generate", json={
      "model": model,
      "prompt": prompt,
      "stream": False,
      "options": {"temperature": 0.0}
  })
  result = response.json()["response"]
  ```
- Parse the JSON response. The LLM should return a JSON object with axis labels as keys and extracted values (or null) as values.
- **Error handling**: If the response is not valid JSON, retry once. If it fails again, return all-null for that query. Log the failure (query text, raw response) for debugging.
- **Unknown value handling**: If the LLM returns a value that's not in the schema's allowed values for that axis, treat it as null for that axis (same behavior as the catalog lookup).
- The `ollama_base_url` should default to `http://ollama:11434` (Docker service name) but be configurable for flexibility (e.g., `http://localhost:11434` when running outside Docker).

### 4. Test the extractor

Write tests (in `if __name__ == "__main__"` block or separate script) that:

1. **Connectivity**: Verify Ollama is reachable and the model is loaded
2. **Single extraction**: Pick a known query from `OEB_short_norm.parquet` with a known ground-truth item. Extract parameters and check against the ground truth.
3. **Batch of 20 queries**: Run extraction on 20 queries from different concept groups. For each:
   - Print: query text, concept, extracted params, ground-truth params, match (yes/no)
   - Report overall accuracy: what fraction of axes were correctly extracted
4. **Edge cases**:
   - Query where parameters are not explicitly mentioned → expect nulls
   - Malformed LLM response handling → verify graceful fallback
5. **Timing**: Report average time per query (important for planning the full 16,590-query run)

**Ground truth for comparison**: Load the parquet, look up the query's ground-truth `item_key`, parse its `parameters` column to get the expected axis values.

---

## Acceptance Criteria

- [ ] `docker-compose.yml` updated with Ollama service (GPU-enabled)
- [ ] Ollama running with `llama3.1:8b` pulled and responsive
- [ ] `src/pipeline/prompts.py` exists with `build_extraction_prompt()`
- [ ] `src/pipeline/param_extractor.py` exists with `LLMParamExtractor`
- [ ] Connectivity test passes
- [ ] Single extraction test: extracted params match ground truth (at least partially)
- [ ] Batch of 20 queries: per-axis accuracy and per-query accuracy reported
- [ ] Error handling: malformed response → retry → all-null fallback (no crash)
- [ ] Average time per query reported
- [ ] No existing files modified (except `docker-compose.yml` — this is the one intentional modification to an existing file)

---

## Out of Scope

- Rule-based extractor (B4 — separate sprint)
- Pipeline integration (C1)
- Full 16,590-query evaluation (C3)
- Prompt optimization or ablation (future work)
- The `ollama` Python package — use `requests` directly
