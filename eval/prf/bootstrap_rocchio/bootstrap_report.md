# Bootstrap significance — Acc@1

- Queries: 16590
- Bootstraps: 10000
- α = 0.05
- Best method: **bm25_unigram** (Acc@1 = **0.8691**)

Legend: Holm = Holm–Bonferroni (FWER), BH = Benjamini–Hochberg (FDR). `✓` = best is significantly better (method is worse), `≈` = no significant difference, `✗` = opposite direction.

| Method | Acc@1 | Δ vs best | 95% CI | Holm | BH |
|---|---:|---:|---:|:--:|:--:|
| **bm25_unigram** | **0.8691** | — | — | — | — |
| prf_rocchio__bm25_unigram__M5__N20__beta0_5 | 0.8565 | 0.0126 | [0.0104, 0.0148] | ✓ | ✓ |
