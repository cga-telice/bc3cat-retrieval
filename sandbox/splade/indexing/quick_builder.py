"""
Quick Baseline Index Builder for Texto Collection

This module creates a simple vocabulary-based vectorizer and index for the texto
collection to establish a baseline before training SPLADE models. It uses TF-IDF
with the word-level vocabulary for fast prototyping and comparison.
"""

import pickle
import numpy as np
import torch
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union, Any
from collections import Counter, defaultdict
import json
import time
from dataclasses import dataclass
from scipy.sparse import csr_matrix, vstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging

# Import our vocabulary components
from sandbox.splade.core.vocabulary import VocabularyBuilder, WordTokenizer


@dataclass
class SearchResult:
    """Single search result."""
    item_key: str
    text: str
    score: float
    doc_index: int
    metadata: Optional[Dict[str, Any]] = None


class QuickVectorizer:
    """
    Simple vocabulary-based vectorizer using word-level tokenization.
    Provides TF-IDF weighting with the custom vocabulary.
    """
    
    def __init__(self, vocab_builder: VocabularyBuilder, max_features: Optional[int] = None):
        """
        Initialize vectorizer with vocabulary.
        
        Args:
            vocab_builder: Pre-built vocabulary builder
            max_features: Limit vocabulary size (None for all)
        """
        self.vocab_builder = vocab_builder
        self.tokenizer = vocab_builder.tokenizer
        self.max_features = max_features
        
        # Build feature vocabulary (excluding special tokens)
        self.feature_vocab = {}
        self.id_to_feature = {}
        
        # Get vocabulary sorted by frequency
        vocab_items = [
            (word, freq) for word, freq in vocab_builder.word_freq.items()
            if word not in vocab_builder.special_tokens
        ]
        vocab_items.sort(key=lambda x: x[1], reverse=True)
        
        # Limit vocabulary if specified
        if max_features:
            vocab_items = vocab_items[:max_features]
        
        # Create feature mappings
        for feature_id, (word, freq) in enumerate(vocab_items):
            self.feature_vocab[word] = feature_id
            self.id_to_feature[feature_id] = word
        
        self.vocab_size = len(self.feature_vocab)
        
        # Document frequency for IDF calculation
        self.doc_frequencies = Counter()
        self.total_docs = 0
        self.fitted = False
        
        print(f"QuickVectorizer initialized:")
        print(f"  Vocabulary size: {self.vocab_size:,}")
        print(f"  Max features: {max_features or 'All'}")
    
    def _tokenize_text(self, text: str) -> List[str]:
        """Tokenize text using word tokenizer."""
        return self.tokenizer.tokenize(text)
    
    def _text_to_counts(self, text: str) -> Dict[int, int]:
        """Convert text to term frequency counts."""
        tokens = self._tokenize_text(text)
        counts = {}
        
        for token in tokens:
            if token in self.feature_vocab:
                feature_id = self.feature_vocab[token]
                counts[feature_id] = counts.get(feature_id, 0) + 1
        
        return counts
    
    def fit(self, texts: List[str]) -> 'QuickVectorizer':
        """
        Fit vectorizer on document collection to compute IDF weights.
        
        Args:
            texts: List of document texts
            
        Returns:
            Self for chaining
        """
        print(f"Fitting vectorizer on {len(texts)} documents...")
        
        self.doc_frequencies.clear()
        self.total_docs = len(texts)
        
        for i, text in enumerate(texts):
            if i % 5000 == 0:
                print(f"  Processing document {i}/{len(texts)}")
            
            # Get unique terms in this document
            term_counts = self._text_to_counts(text)
            unique_terms = set(term_counts.keys())
            
            # Update document frequencies
            for term_id in unique_terms:
                self.doc_frequencies[term_id] += 1
        
        self.fitted = True
        print(f"✅ Vectorizer fitted:")
        print(f"  Total documents: {self.total_docs:,}")
        print(f"  Terms with DF > 1: {sum(1 for df in self.doc_frequencies.values() if df > 1):,}")
        
        return self
    
    def _compute_idf_weight(self, term_id: int) -> float:
        """Compute IDF weight for a term."""
        if not self.fitted:
            return 1.0
        
        doc_freq = self.doc_frequencies.get(term_id, 0)
        if doc_freq == 0:
            return 0.0
        
        # Standard IDF formula: log(N / df)
        idf = np.log(self.total_docs / doc_freq)
        return idf
    
    def transform_single(self, text: str) -> csr_matrix:
        """
        Transform single text to TF-IDF vector.
        
        Args:
            text: Input text
            
        Returns:
            Sparse TF-IDF vector
        """
        term_counts = self._text_to_counts(text)
        
        if not term_counts:
            # Return zero vector
            return csr_matrix((1, self.vocab_size))
        
        # Calculate TF-IDF scores
        total_terms = sum(term_counts.values())
        data = []
        indices = []
        
        for term_id, count in term_counts.items():
            tf = count / total_terms  # Term frequency
            idf = self._compute_idf_weight(term_id)
            tfidf = tf * idf
            
            if tfidf > 0:
                data.append(tfidf)
                indices.append(term_id)
        
        # Create sparse vector
        if data:
            row = np.zeros(len(data))
            vector = csr_matrix((data, (row, indices)), shape=(1, self.vocab_size))
        else:
            vector = csr_matrix((1, self.vocab_size))
        
        return vector
    
    def transform(self, texts: List[str], batch_size: int = 1000) -> csr_matrix:
        """
        Transform multiple texts to TF-IDF matrix.
        
        Args:
            texts: List of input texts
            batch_size: Processing batch size
            
        Returns:
            Sparse TF-IDF matrix
        """
        print(f"Transforming {len(texts)} texts to TF-IDF vectors...")
        
        vectors = []
        
        for i in range(0, len(texts), batch_size):
            if i % (batch_size * 10) == 0:
                print(f"  Processing batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")
            
            batch_texts = texts[i:i + batch_size]
            batch_vectors = [self.transform_single(text) for text in batch_texts]
            
            if batch_vectors:
                batch_matrix = vstack(batch_vectors)
                vectors.append(batch_matrix)
        
        if vectors:
            final_matrix = vstack(vectors)
        else:
            final_matrix = csr_matrix((len(texts), self.vocab_size))
        
        print(f"✅ Transformation complete:")
        print(f"  Matrix shape: {final_matrix.shape}")
        print(f"  Sparsity: {(1 - final_matrix.nnz / np.prod(final_matrix.shape)):.3f}")
        
        return final_matrix
    
    def fit_transform(self, texts: List[str], batch_size: int = 1000) -> csr_matrix:
        """Fit vectorizer and transform texts in one step."""
        self.fit(texts)
        return self.transform(texts, batch_size)
    
    def get_feature_names(self) -> List[str]:
        """Get list of feature names (words)."""
        return [self.id_to_feature[i] for i in range(self.vocab_size)]
    
    def save(self, save_path: Path) -> None:
        """Save vectorizer state."""
        save_path.mkdir(parents=True, exist_ok=True)
        
        vectorizer_state = {
            'feature_vocab': self.feature_vocab,
            'id_to_feature': self.id_to_feature,
            'vocab_size': self.vocab_size,
            'doc_frequencies': dict(self.doc_frequencies),
            'total_docs': self.total_docs,
            'fitted': self.fitted,
            'max_features': self.max_features,
        }
        
        with open(save_path / "vectorizer_state.json", "w", encoding="utf-8") as f:
            json.dump(vectorizer_state, f, ensure_ascii=False, indent=2)
        
        print(f"Vectorizer saved to {save_path}")
    
    @classmethod
    def load(cls, save_path: Path, vocab_builder: VocabularyBuilder) -> 'QuickVectorizer':
        """Load vectorizer state."""
        with open(save_path / "vectorizer_state.json", "r", encoding="utf-8") as f:
            state = json.load(f)
        
        vectorizer = cls(vocab_builder, state['max_features'])
        vectorizer.feature_vocab = state['feature_vocab']
        vectorizer.id_to_feature = {int(k): v for k, v in state['id_to_feature'].items()}
        vectorizer.vocab_size = state['vocab_size']
        vectorizer.doc_frequencies = Counter({int(k): v for k, v in state['doc_frequencies'].items()})
        vectorizer.total_docs = state['total_docs']
        vectorizer.fitted = state['fitted']
        
        print(f"Vectorizer loaded from {save_path}")
        return vectorizer


class QuickSearchIndex:
    """
    Simple search index using TF-IDF vectors and cosine similarity.
    """
    
    def __init__(self, vectorizer: QuickVectorizer):
        """
        Initialize search index.
        
        Args:
            vectorizer: Fitted QuickVectorizer
        """
        self.vectorizer = vectorizer
        self.document_vectors = None
        self.documents = []
        self.doc_metadata = []
        self.indexed = False
        
        print(f"QuickSearchIndex initialized")
    
    def index_documents(self, 
                       documents: List[Any], 
                       text_field: str = "text",
                       key_field: str = "item_key",
                       batch_size: int = 1000) -> None:
        """
        Index a collection of documents.
        
        Args:
            documents: List of documents (Document objects or dicts)
            text_field: Field name containing text content
            key_field: Field name containing document key/ID (default: "item_key")
            batch_size: Processing batch size
        """
        print(f"Indexing {len(documents)} documents...")
        
        # Extract texts and metadata
        texts = []
        self.documents = []
        self.doc_metadata = []
        
        for i, doc in enumerate(documents):
            # Extract text content
            if hasattr(doc, text_field):
                text = getattr(doc, text_field)
            elif isinstance(doc, dict) and text_field in doc:
                text = doc[text_field]
            else:
                text = str(doc)
            
            # Extract key/ID - prioritize item_key field
            doc_key = None
            
            # Try direct attribute access first for item_key
            if hasattr(doc, key_field):
                doc_key = getattr(doc, key_field)
            elif hasattr(doc, 'item_key'):
                doc_key = doc.item_key
            # Try metadata first (this is where item_key is likely stored)
            elif hasattr(doc, 'metadata') and isinstance(doc.metadata, dict):
                if 'item_key' in doc.metadata:
                    doc_key = doc.metadata['item_key']
                elif key_field in doc.metadata:
                    doc_key = doc.metadata[key_field]
            # Try dictionary access
            elif isinstance(doc, dict):
                if 'item_key' in doc:
                    doc_key = doc['item_key']
                elif key_field in doc:
                    doc_key = doc[key_field]
            
            # Fallback to index-based ID if no item_key found
            if not doc_key:
                doc_key = f"doc_{i}"
            
            # Extract metadata
            metadata = {}
            if hasattr(doc, 'metadata') and isinstance(doc.metadata, dict):
                metadata = doc.metadata.copy()
            elif isinstance(doc, dict):
                metadata = {k: v for k, v in doc.items() if k not in [text_field, key_field]}
            
            texts.append(text)
            self.documents.append({
                'key': doc_key,
                'text': text,
                'index': i
            })
            self.doc_metadata.append(metadata)
        
        # Create document vectors
        if not self.vectorizer.fitted:
            self.document_vectors = self.vectorizer.fit_transform(texts, batch_size)
        else:
            self.document_vectors = self.vectorizer.transform(texts, batch_size)
        
        self.indexed = True
        
        print(f"✅ Indexing complete:")
        print(f"  Documents indexed: {len(self.documents):,}")
        print(f"  Vector matrix shape: {self.document_vectors.shape}")
        print(f"  Average document length: {np.mean([len(d['text']) for d in self.documents]):.1f} chars")
    
    def search(self, 
               queries: Union[str, List[str]], 
               top_k: int = 10,
               min_score: float = 0.0) -> Union[List[SearchResult], List[List[SearchResult]]]:
        """
        Search the index with queries.
        
        Args:
            queries: Single query string or list of queries
            top_k: Number of top results to return
            min_score: Minimum similarity score threshold
            
        Returns:
            Search results (single list if single query, list of lists if multiple)
        """
        if not self.indexed:
            raise ValueError("Index has not been built. Call index_documents() first.")
        
        # Handle single query
        single_query = isinstance(queries, str)
        if single_query:
            queries = [queries]
        
        print(f"Searching with {len(queries)} queries...")
        
        # Transform queries to vectors
        query_vectors = []
        for query in queries:
            query_vector = self.vectorizer.transform_single(query)
            query_vectors.append(query_vector)
        
        if query_vectors:
            query_matrix = vstack(query_vectors)
        else:
            return [] if single_query else [[] for _ in queries]
        
        # Compute similarities
        similarities = cosine_similarity(query_matrix, self.document_vectors)
        
        # Process results for each query
        all_results = []
        
        for i, query in enumerate(queries):
            query_similarities = similarities[i]
            
            # Get top-k indices
            top_indices = np.argsort(query_similarities)[::-1][:top_k]
            
            # Create search results
            results = []
            for doc_idx in top_indices:
                score = query_similarities[doc_idx]
                
                if score >= min_score:
                    doc_info = self.documents[doc_idx]
                    metadata = self.doc_metadata[doc_idx]
                    
                    result = SearchResult(
                        item_key=doc_info['key'],
                        text=doc_info['text'],
                        score=float(score),
                        doc_index=int(doc_idx),
                        metadata=metadata
                    )
                    results.append(result)
            
            all_results.append(results)
        
        print(f"✅ Search complete:")
        print(f"  Average results per query: {np.mean([len(r) for r in all_results]):.1f}")
        
        # Return format based on input
        if single_query:
            return all_results[0]
        else:
            return all_results
    
    def get_document_by_key(self, key: str) -> Optional[Dict[str, Any]]:
        """Get document by its key."""
        for doc_info in self.documents:
            if doc_info['key'] == key:
                doc_idx = doc_info['index']
                return {
                    'key': key,
                    'text': doc_info['text'],
                    'index': doc_idx,
                    'metadata': self.doc_metadata[doc_idx],
                    'vector': self.document_vectors[doc_idx]
                }
        return None
    
    def get_index_statistics(self) -> Dict[str, Any]:
        """Get index statistics."""
        if not self.indexed:
            return {"indexed": False}
        
        doc_lengths = [len(doc['text']) for doc in self.documents]
        vector_norms = np.array(self.document_vectors.sum(axis=1)).flatten()
        
        return {
            "indexed": True,
            "total_documents": len(self.documents),
            "vocabulary_size": self.vectorizer.vocab_size,
            "matrix_shape": self.document_vectors.shape,
            "sparsity": 1 - self.document_vectors.nnz / np.prod(self.document_vectors.shape),
            "avg_doc_length": np.mean(doc_lengths),
            "median_doc_length": np.median(doc_lengths),
            "avg_vector_norm": np.mean(vector_norms),
            "median_vector_norm": np.median(vector_norms),
        }
    
    def save(self, save_path: Path) -> None:
        """Save search index."""
        save_path.mkdir(parents=True, exist_ok=True)
        
        # Save vectorizer
        self.vectorizer.save(save_path)
        
        # Save index data
        index_data = {
            'documents': self.documents,
            'doc_metadata': self.doc_metadata,
            'indexed': self.indexed,
        }
        
        with open(save_path / "index_data.json", "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
        
        # Save document vectors (sparse matrix)
        if self.document_vectors is not None:
            np.savez(save_path / "document_vectors.npz", 
                    data=self.document_vectors.data,
                    indices=self.document_vectors.indices,
                    indptr=self.document_vectors.indptr,
                    shape=self.document_vectors.shape)
        
        print(f"Search index saved to {save_path}")
    
    @classmethod
    def load(cls, save_path: Path, vocab_builder: VocabularyBuilder) -> 'QuickSearchIndex':
        """Load search index."""
        # Load vectorizer
        vectorizer = QuickVectorizer.load(save_path, vocab_builder)
        
        # Create index
        index = cls(vectorizer)
        
        # Load index data
        with open(save_path / "index_data.json", "r", encoding="utf-8") as f:
            index_data = json.load(f)
        
        index.documents = index_data['documents']
        index.doc_metadata = index_data['doc_metadata']
        index.indexed = index_data['indexed']
        
        # Load document vectors
        vectors_path = save_path / "document_vectors.npz"
        if vectors_path.exists():
            loaded = np.load(vectors_path)
            index.document_vectors = csr_matrix(
                (loaded['data'], loaded['indices'], loaded['indptr']),
                shape=loaded['shape']
            )
        
        print(f"Search index loaded from {save_path}")
        return index


def load_documents_from_pickle(file_path: Union[str, Path]) -> List[Any]:
    """Load documents from pickle file."""
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Document file not found: {file_path}")
    
    print(f"Loading documents from {file_path}")
    
    with open(file_path, 'rb') as f:
        documents = pickle.load(f)
    
    print(f"Loaded {len(documents)} documents")
    return documents


def create_baseline_index(vocab_path: Union[str, Path],
                         data_path: Union[str, Path],
                         file_base: str = "OEB",
                         use_filtered_vocab: bool = True,
                         max_features: Optional[int] = None,
                         output_dir: Optional[Union[str, Path]] = None) -> QuickSearchIndex:
    """
    Create baseline search index for texto collection.
    
    Args:
        vocab_path: Path to vocabulary directory
        data_path: Path to data directory
        file_base: Base filename for documents
        use_filtered_vocab: Whether to use filtered vocabulary
        max_features: Limit vocabulary size
        output_dir: Directory to save index (optional)
        
    Returns:
        Built search index
    """
    print("="*60)
    print("CREATING BASELINE SEARCH INDEX")
    print("="*60)
    
    # Load vocabulary
    vocab_suffix = "filtered" if use_filtered_vocab else "full"
    vocab_full_path = Path(vocab_path) / f"{file_base}_vocab_{vocab_suffix}_50000"
    
    print(f"Loading vocabulary from: {vocab_full_path}")
    vocab_builder = VocabularyBuilder.load_vocabulary(vocab_full_path)
    
    # Create vectorizer
    print(f"Creating vectorizer (max_features: {max_features or 'All'})...")
    vectorizer = QuickVectorizer(vocab_builder, max_features=max_features)
    
    # Load texto documents
    texto_path = Path(data_path) / f"{file_base}_texto.pkl"
    documents = load_documents_from_pickle(texto_path)
    
    # Create and build index
    index = QuickSearchIndex(vectorizer)
    index.index_documents(documents, text_field="text", key_field="item_key")
    
    # Save index if output directory specified
    if output_dir:
        output_path = Path(output_dir)
        vocab_type = "filtered" if use_filtered_vocab else "full"
        features_suffix = f"_{max_features}" if max_features else ""
        index_name = f"{file_base}_baseline_index_{vocab_type}{features_suffix}"
        
        save_path = output_path / index_name
        index.save(save_path)
        
        print(f"✅ Index saved to: {save_path}")
    
    # Print statistics
    stats = index.get_index_statistics()
    print(f"\n📊 Index Statistics:")
    print(f"  Documents: {stats['total_documents']:,}")
    print(f"  Vocabulary size: {stats['vocabulary_size']:,}")
    print(f"  Matrix shape: {stats['matrix_shape']}")
    print(f"  Sparsity: {stats['sparsity']:.3f}")
    print(f"  Avg document length: {stats['avg_doc_length']:.1f} chars")
    
    return index


def test_search_functionality(index: QuickSearchIndex, 
                             test_queries: List[str] = None,
                             top_k: int = 5) -> None:
    """Test search functionality with sample queries."""
    if test_queries is None:
        test_queries = [
            "canalización tubos polietileno",
            "hormigonada galvanizado",
            "excavación zanjas",
            "montaje suministro",
            "diámetro mm"
        ]
    
    print(f"\n🔍 Testing search with {len(test_queries)} queries:")
    print("="*50)
    
    for i, query in enumerate(test_queries):
        print(f"\nQuery {i+1}: '{query}'")
        results = index.search(query, top_k=top_k, min_score=0.01)
        
        print(f"Results ({len(results)}):")
        for j, result in enumerate(results[:3]):  # Show top 3
            text_preview = result.text[:100] + "..." if len(result.text) > 100 else result.text
            print(f"  {j+1}. Score: {result.score:.3f}")
            print(f"     Key: {result.item_key}")
            print(f"     Text: {text_preview}")
        
        if not results:
            print("     No results found")


def batch_search_example(index: QuickSearchIndex) -> None:
    """Example of batch search functionality."""
    print(f"\n🔍 Testing batch search:")
    print("="*30)
    
    batch_queries = [
        "canalización polietileno",
        "excavación zanjas terreno",
        "hormigonada galvanizado",
        "suministro montaje tubos"
    ]
    
    print(f"Batch queries: {batch_queries}")
    
    # Batch search
    start_time = time.time()
    batch_results = index.search(batch_queries, top_k=3)
    search_time = time.time() - start_time
    
    print(f"Search completed in {search_time:.3f} seconds")
    print(f"Results per query:")
    
    for i, (query, results) in enumerate(zip(batch_queries, batch_results)):
        print(f"  Query {i+1}: {len(results)} results (top score: {results[0].score:.3f})" if results else f"  Query {i+1}: 0 results")


# Convenience functions for notebooks and scripts
def quick_baseline_setup(file_base: str = "OEB",
                        vocab_path: str = "/work/sandbox/splade/vocabularies",
                        data_path: str = "/work/data/processed",
                        use_filtered: bool = True,
                        max_features: Optional[int] = 10000,
                        save_index: bool = True) -> QuickSearchIndex:
    """Quick setup for baseline index (notebook-friendly)."""
    output_dir = "/work/sandbox/splade/baseline_indices" if save_index else None
    
    return create_baseline_index(
        vocab_path=vocab_path,
        data_path=data_path,
        file_base=file_base,
        use_filtered_vocab=use_filtered,
        max_features=max_features,
        output_dir=output_dir
    )


def load_baseline_index(file_base: str = "OEB",
                       vocab_path: str = "/work/sandbox/splade/vocabularies",
                       index_path: str = "/work/sandbox/splade/baseline_indices",
                       use_filtered: bool = True,
                       max_features: Optional[int] = 10000) -> QuickSearchIndex:
    """Load existing baseline index."""
    # Load vocabulary
    vocab_suffix = "filtered" if use_filtered else "full"
    vocab_full_path = Path(vocab_path) / f"{file_base}_vocab_{vocab_suffix}_50000"
    vocab_builder = VocabularyBuilder.load_vocabulary(vocab_full_path)
    
    # Load index
    vocab_type = "filtered" if use_filtered else "full"
    features_suffix = f"_{max_features}" if max_features else ""
    index_name = f"{file_base}_baseline_index_{vocab_type}{features_suffix}"
    
    load_path = Path(index_path) / index_name
    return QuickSearchIndex.load(load_path, vocab_builder)


# Example usage
if __name__ == "__main__":
    # Create baseline index
    print("Creating baseline search index...")
    
    index = create_baseline_index(
        vocab_path="/work/sandbox/splade/vocabularies",
        data_path="/work/data/processed", 
        file_base="OEB",
        use_filtered_vocab=True,
        max_features=10000,  # Limit vocabulary for speed
        output_dir="/work/sandbox/splade/baseline_indices"
    )
    
    # Test search functionality
    test_search_functionality(index)
    
    # Test batch search
    batch_search_example(index)
    
    print(f"\n✅ Baseline index creation and testing complete!")
    print(f"📁 Index saved and ready for use")
    print(f"🔧 Use load_baseline_index() to reload in other scripts")