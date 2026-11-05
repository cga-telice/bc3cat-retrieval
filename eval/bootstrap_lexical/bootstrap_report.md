# Bootstrap significance — Acc@1

- Queries: 16590
- Bootstraps: 10000
- α = 0.05
- Best method: **bm25_unigram** (Acc@1 = **0.8691**)

Legend: Holm = Holm–Bonferroni (FWER), BH = Benjamini–Hochberg (FDR). `✓` = best is significantly better (method is worse), `≈` = no significant difference, `✗` = opposite direction.

| Method | Acc@1 | Δ vs best | 95% CI | Holm | BH |
|---|---:|---:|---:|:--:|:--:|
| **bm25_unigram** | **0.8691** | — | — | — | — |
| bm25_unibigram | 0.8267 | 0.0424 | [0.0362, 0.0485] | ✓ | ✓ |
| tfidf_unigram_phrases_replace | 0.7083 | 0.1608 | [0.1527, 0.1688] | ✓ | ✓ |
| tfidf_unigram_phrases_add | 0.6500 | 0.2191 | [0.2112, 0.2271] | ✓ | ✓ |
| tfidf_unigram_nostop | 0.6416 | 0.2275 | [0.2201, 0.2351] | ✓ | ✓ |
| tfidf_unigram | 0.6265 | 0.2426 | [0.2351, 0.2500] | ✓ | ✓ |
| tfidf_char_3_5 | 0.5583 | 0.3107 | [0.3028, 0.3187] | ✓ | ✓ |
