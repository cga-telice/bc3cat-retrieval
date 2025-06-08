import math
import time
from typing import List, Dict, Any, Set, Optional, Tuple, Union
from llama_index.core import Document
from scipy.sparse import load_npz, csr_matrix
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from collections import defaultdict
from src.utils.text_processing import normalize_text
from src.utils.custom_types import DocumentList, EmbeddingVector
from src.utils.config import Config

#### BM25 INDEX CLASSES ####

# Custom BM25 vectorizer using sparse representations.
class SparseBM25Vectorizer:
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.vectorizer = CountVectorizer(binary=False, lowercase=True, token_pattern=r'\b\w+\b')
        self.doc_len = None
        self.avgdl = None
        self.idf = None
        self.doc_freq = None

    def fit(self, documents):
        texts = [doc.text if isinstance(doc, Document) else doc for doc in documents]
        X = self.vectorizer.fit_transform(texts)
        self.doc_len = X.sum(axis=1).A1
        self.avgdl = self.doc_len.mean()
        n_docs = X.shape[0]
        self.doc_freq = X.sum(axis=0).A1
        self.idf = np.log((n_docs - self.doc_freq + 0.5) / (self.doc_freq + 0.5) + 1.0)
        return self

    def transform(self, documents):
        if isinstance(documents, str):
            documents = [documents]
        texts = [doc.text if isinstance(doc, Document) else doc for doc in documents]
        X = self.vectorizer.transform(texts)
        return self._bm25_sparse(X)

    def _bm25_sparse(self, X):
        rows, cols = X.nonzero()
        data = X.data

        doc_len = self.doc_len[rows]
        idf = self.idf[cols]

        numerator = data * (self.k1 + 1)
        denominator = data + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)

        scores = idf * numerator / denominator
        return csr_matrix((scores, (rows, cols)), shape=X.shape)

    def get_vocabulary(self):
        """Return the vocabulary as a dict mapping terms to indices."""
        return self.vectorizer.vocabulary_
    
    def extract_tokens(self, text):
        """Extract tokens from text using the same settings as the vectorizer."""
        return self.vectorizer.build_analyzer()(text)

class SparseBM25Retriever:
    def __init__(self, documents, vectorizer, embeddings):
        self.documents = documents
        self.vectorizer = vectorizer
        self.embeddings = embeddings

    def retrieve(self, query: str, top_k=10):
        """
        Efficient retrieval of top-K relevant documents using sparse BM25.
        """
        query_embedding = self.vectorizer.transform([query])  # Ensure it's a sparse matrix
        
        # Compute sparse cosine similarity (dot product is enough in BM25 space)
        scores = query_embedding @ self.embeddings.T  # Sparse matrix multiplication
        scores = np.array(scores.toarray()).flatten()  # Convert to dense array
        
        # Get top-k indices efficiently using argpartition (O(N log K) instead of O(N log N))
        top_k_idx = np.argpartition(scores, -top_k)[-top_k:]  # Get top-K without sorting everything
        top_k_idx = top_k_idx[np.argsort(scores[top_k_idx])[::-1]]  # Sort top-K results

        # Retrieve top results
        results = [
            {
                "item_key": self.documents[idx].metadata.get("item_key", f"Doc-{idx}"),
                "text": self.documents[idx].text,
                "score": scores[idx]
            }
            for idx in top_k_idx
        ]

        return results

#### TREE INDEX CLASSES ####

class TreeNode:
    def __init__(self, key, level, description=""):
        self.key = key                 # Node key (part of item_key)
        self.level = level             # Level in the tree
        self.description = description # Path-based description for embedding
        self.children = {}             # Child nodes
        self.documents = []            # Document IDs at this node (only for leaves)
        self.embedding = None          # BM25 embedding for this node

