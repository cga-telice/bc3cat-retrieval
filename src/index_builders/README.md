# Index Builders

This folder contains **per-method index builder modules** used by `index_build.ipynb`.

Each file here implements the **builder contract** so the main notebook can:
- Pick the correct feature field to index.
- Build the method-specific artifacts.
- Save them in the standardized index format.

---

## 📄 File Naming Convention

- The filename **must** match the method `name` in the YAML config.
- Example:
  - YAML: `method.name: tfidf_unigram` → file: `tfidf_unigram.py`
  - YAML: `method.name: tfidf_unigram_phrases` → file: `tfidf_unigram_phrases.py`

---

## 📜 Builder Contract

Each builder module **must** define:

```python
def select_field(feats_meta: dict) -> str:
    """
    Given the features_meta JSON, return the name of the column in the
    long-format parquet that should be indexed for this method.
    """

def build(cfg: dict, long_df, text_field: str):
    """
    Build the index for this method.

    Args:
        cfg         - Full YAML config loaded as a dict
        long_df     - Pandas DataFrame of the long-format collection
        text_field  - The column to index (from select_field)

    Returns:
        artifacts   - dict of {filename: object} to persist
                      Supported:
                        - .npz (CSR matrix)
                        - .json (dict/list)
                        - .npy (numpy array)
                      Special keys:
                        "__num_docs__"   (int)
                        "__vocab_size__" (int)
                        "__corpus_hash__" (str)

        transformer - Optional fitted model/vectorizer for probing (or None)
        X_docs      - Optional document-term matrix for probing (or None)
    """
