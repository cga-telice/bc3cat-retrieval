# Request to `bc3cat-dataset` — E3 balanced dose set

**Requested by:** `bc3cat-retrieval`, branch `research/synthetic-oe`, sprint S0
**Drafted:** 2026-09-15 · **Issued:** *(pending — see D-009)*
**Needed by:** sprint S8. Gate G3 decides on its absence; it blocks S8 only.
**Decision of record:** D-009.

## Why this is needed

BC3CAT-Syn/OE ships two query sets. The stacked set gives the headline number, but it
**cannot identify interactions between modification types**, for two structural reasons:

- `reorder` never co-occurs with anything, so it is absent from every stacked item;
- `template_paraphrase` is present in **100 %** of stacked items.

So "count" and "which types" are confounded: a degradation at count 5 cannot be attributed
to the dose rather than to the fixed composition that every count-5 item happens to carry.
H4 (super-additivity — that stacked modifications degrade accuracy more than the sum of the
isolated per-type effects) is not testable on it.

This is the only data extension the research proposal depends on.

## What is requested

A query set over the **same OE corpus already delivered** (70 242 leaves, 83 concepts;
digests in our `MANIFEST.md`), so that every `gold_item_key` resolves against it.

### 1. Dose ladder, randomised composition

| Property | Requested |
|---|---|
| `modification_count` | 1, 2, 3, 4, 5 |
| Type mix at each count | **drawn at random** from the nine admitted types, not fixed |
| `reorder` | **admitted**, and free to co-occur |
| `template_paraphrase` | **not forced** — present only when the draw selects it |
| Types | the nine of D-001/D-002; `omission` and `new_param` stay excluded |

### 2. Within-leaf ladder — the part that matters most

Wherever a leaf admits it, please emit **the same leaf at several counts** (ideally 1
through 5). Dose–response estimated *within* an item is far stronger than a comparison
across different items, because it removes leaf difficulty from the contrast entirely.

If only one count per leaf is feasible, say so: it changes our analysis from a within-item
slope to a between-item regression, and we would rather know in advance than discover it.

### 3. Balance

- Comparable numbers of queries per count cell.
- Each type appearing at roughly even rates **across** counts, so that a count effect is
  not a disguised composition effect.
- Suggested size: **≥ 600 queries per count**, ~3 000 total, matching the per-type density
  of the existing single set. More is welcome; balance matters more than volume.

### 4. Applicability, declared per item

`unit_conversion` only applies to leaves with convertible numeric parameters, and similar
limits affect other types. Please emit, per item, **the set of types that were applicable**
— not only those applied. Without it, a comparison across counts silently compares
different populations, and we can only report effects on the treated.

### 5. Schema

Identical to the existing synthetic sets, so no loader work is needed:

```json
{"item_key": "<gold>_syn_<hash>", "parent_key": "OEA010$",
 "gold_item_key": "OEA010aaba",
 "parameters": {"A": "...", "B": null},
 "text": "...",
 "modification_types": [...], "modification_count": 3,
 "applicable_types": [...]}
```

`applicable_types` is the one addition (§4). `parent_key` must be present on every record:
we partition the set by concept against our own dev/test split, so no split logic is needed
upstream.

### 6. Provenance

Everything needed for our stamp `{run_id, config SHA, code commit, query-set SHA-256}`:

- generation seed, script path and `bc3cat-dataset` commit;
- SHA-256 of each delivered file;
- the per-item modifications sidecar, as with the existing sets, so that documented pantry
  artefacts (token doubling, the `con topo` → `con topografía` drift) stay traceable and we
  can run sensitivity analyses excluding them.

## What happens if it does not arrive

Per D-009 and gate G3: H4 drops to an exploratory regression on the existing stacked set,
with the confounding above stated in the limitations, and S8 closes at half size. It does
not block S12 or the manuscript. So this is a request, not a dependency — but the earlier it
lands, the stronger H4 gets.
