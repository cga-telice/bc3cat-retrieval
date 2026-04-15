# Bootstrap significance — Acc@1

- Queries: 25321
- Bootstraps: 10000
- α = 0.05
- Best method: **bm25_unigram** (Acc@1 = **0.5694**)

Legend: Holm = Holm–Bonferroni (FWER), BH = Benjamini–Hochberg (FDR). `✓` = best is significantly better (method is worse), `≈` = no significant difference, `✗` = opposite direction.

| Method | Acc@1 | Δ vs best | 95% CI | Holm | BH |
|---|---:|---:|---:|:--:|:--:|
| **bm25_unigram** | **0.5694** | — | — | — | — |
| bm25_unibigram | 0.5416 | 0.0278 | [0.0238, 0.0317] | ≈ | ✓ |
| tfidf_unigram_phrases_replace | 0.4641 | 0.1053 | [0.1000, 0.1106] | ≈ | ✓ |
| tfidf_unigram_phrases_add | 0.4259 | 0.1436 | [0.1381, 0.1490] | ≈ | ✓ |
| tfidf_unigram_nostop | 0.4204 | 0.1490 | [0.1440, 0.1541] | ≈ | ✓ |
| tfidf_unigram | 0.4105 | 0.1589 | [0.1539, 0.1641] | ≈ | ✓ |
| tfidf_char_3_5 | 0.3658 | 0.2036 | [0.1983, 0.2089] | ≈ | ✓ |
| rrf__bm25_char_e5 | 0.3252 | 0.2442 | [0.2381, 0.2504] | ≈ | ✓ |
| bge_m3_colbert | 0.2935 | 0.2759 | [0.2694, 0.2825] | ≈ | ✓ |
| dense_e5 | 0.0880 | 0.4815 | [0.4742, 0.4886] | ≈ | ✓ |
| bge_m3_dense | 0.0831 | 0.4863 | [0.4796, 0.4928] | ≈ | ✓ |
| bge_m3_sparse | 0.0816 | 0.4878 | [0.4814, 0.4942] | ≈ | ✓ |
| dense_es_hiiamsid | 0.0160 | 0.5534 | [0.5469, 0.5598] | ≈ | ✓ |
| dense_gte_instrQ | 0.0092 | 0.5602 | [0.5541, 0.5664] | ≈ | ✓ |
| dense_gte | 0.0085 | 0.5610 | [0.5547, 0.5672] | ≈ | ✓ |
