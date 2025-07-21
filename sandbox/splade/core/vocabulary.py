"""
Enhanced Word-Level Vocabulary Management for SPLADE

This module builds both full and filtered vocabularies simultaneously,
allowing comparison of approaches with and without Spanish stopwords.
"""

import re
import json
import pickle
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Counter
from collections import Counter, defaultdict
import unicodedata

import numpy as np
from llama_index.core import Document


class WordTokenizer:
    """
    Word-level tokenizer optimized for technical Spanish text.
    Enhanced with stopword filtering capabilities.
    """
    
    def __init__(self, preserve_case: bool = False, min_word_len: int = 1, 
                 max_word_len: int = 50, filter_stopwords: bool = False, compound_terms: List[str]=[]):
        """
        Initialize word tokenizer.
        
        Args:
            preserve_case: Whether to preserve original casing
            min_word_len: Minimum word length to keep
            max_word_len: Maximum word length to keep (filter noise)
            filter_stopwords: Whether to filter Spanish stopwords
            compound_terms: List of compound terms to preserve as single tokens
        """
        self.preserve_case = preserve_case
        self.min_word_len = min_word_len
        self.max_word_len = max_word_len
        self.filter_stopwords = filter_stopwords
        
        # Store compound terms as a set for fast lookup
        self.compound_terms = set(compound_terms) if compound_terms else set()
        
        # Spanish stopwords - common function words
        self.spanish_stopwords = {
            # Articles
            'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
            # Prepositions  
            'de', 'del', 'al', 'en', 'con', 'por', 'para', 'sin', 'sobre',
            'entre', 'hasta', 'desde', 'hacia', 'ante', 'bajo', 'tras',
            # Conjunctions
            'y', 'e', 'o', 'u', 'pero', 'sino', 'que', 'si',
            # Common adjectives/adverbs
            'muy', 'más', 'menos', 'todo', 'toda', 'todos', 'todas',
            'cualquier', 'cualquiera', 'otro', 'otra', 'otros', 'otras',
            # Pronouns
            'se', 'le', 'lo', 'la', 'me', 'te', 'nos', 'les', 'su', 'sus',
            # Common verbs (highly frequent forms)
            'es', 'son', 'está', 'están', 'ser', 'estar', 'tener', 'tiene',
        }

        # Technical patterns to preserve
        self.technical_patterns = [
            r'\b[A-Z]{2,10}\b',  # Acronyms: ECG, MRI, etc.
            r'\b\w+[0-9]+\w*\b',  # Terms with numbers: COVID19, H1N1, etc.
            r'\b[0-9]+[a-zA-Z]+\b',  # Numbers + letters: 5mg, 10km, etc.
            r'\b\w+-\w+\b',  # Hyphenated terms: anti-inflammatory, etc.
        ]
        
        # Compile patterns
        self.compiled_patterns = [re.compile(pattern) for pattern in self.technical_patterns]
    
    def add_compound_terms(self, compound_terms: List[str]) -> None:
        """
        Add compound terms to the existing set.
        
        Args:
            compound_terms: List of compound terms to add
        """
        if compound_terms:
            self.compound_terms.update(compound_terms)
            print(f"Added {len(compound_terms)} compound terms to tokenizer")
    
    def _normalize_unicode(self, text: str) -> str:
        """Normalize Unicode characters while preserving Spanish accents."""
        return unicodedata.normalize('NFKC', text)
    
    def _extract_compound_terms(self, text: str) -> Tuple[Dict[str, str], str]:
        """
        Extract compound terms from text and create placeholders.
        
        Args:
            text: Input text
            
        Returns:
            Tuple of (placeholders_dict, modified_text)
        """
        if not self.compound_terms:
            return {}, text
            
        placeholders = {}
        modified_text = text
        
        # Sort compound terms by length (longest first) to avoid partial matches
        sorted_compounds = sorted(self.compound_terms, key=len, reverse=True)
        
        for i, compound in enumerate(sorted_compounds):
            # Create a unique placeholder that won't interfere with regex
            placeholder = f"__COMP{i:03d}__"
            
            # Check if compound exists in text (case insensitive, whole word match)
            pattern = r'\b' + re.escape(compound) + r'\b'
            if re.search(pattern, modified_text, flags=re.IGNORECASE):
                placeholders[placeholder] = compound
                # Replace in text (case insensitive, whole word match)
                modified_text = re.sub(pattern, placeholder, modified_text, flags=re.IGNORECASE)
        
        return placeholders, modified_text
    
    def _is_stopword(self, word: str) -> bool:
        """Check if word is a Spanish stopword."""
        return word.lower() in self.spanish_stopwords
    
    def _extract_technical_terms(self, text: str) -> Set[str]:
        """Extract technical terms that should be preserved as single tokens."""
        technical_terms = set()
        
        # Only extract if no placeholders are present (to avoid conflicts)
        if '__COMP' not in text:
            for pattern in self.compiled_patterns:
                matches = pattern.findall(text)
                # Filter out single digits and very short matches that might be false positives
                filtered_matches = [m for m in matches if len(m) >= 3 or (len(m) == 2 and any(c.isalpha() for c in m))]
                technical_terms.update(matches)
        
        return technical_terms

    def _replace_technical_terms(self, text: str, technical_terms: Set[str]) -> Tuple[Dict[str, str], str]:
        """
        Replace technical terms with placeholders, ensuring no partial matches.
        
        Args:
            text: Input text
            technical_terms: Set of technical terms to replace
            
        Returns:
            Tuple of (placeholders_dict, modified_text)
        """
        tech_placeholders = {}
        modified_text = text
        
        # Sort by length (longest first) to avoid partial replacements
        sorted_terms = sorted(technical_terms, key=len, reverse=True)
        
        for i, term in enumerate(sorted_terms):
            placeholder = f"__TECH{i:03d}__"
            
            # Use word boundaries to ensure we don't replace partial matches
            # For terms that are purely numeric, be more careful
            if term.isdigit():
                # For pure numbers, ensure they're standalone
                pattern = r'\b' + re.escape(term) + r'\b'
            else:
                # For alphanumeric terms, use word boundaries
                pattern = r'\b' + re.escape(term) + r'\b'
            
            if re.search(pattern, modified_text):
                tech_placeholders[placeholder] = term
                modified_text = re.sub(pattern, placeholder, modified_text)
        
        return tech_placeholders, modified_text
    
    def _basic_tokenize(self, text: str) -> List[str]:
        """
        Basic word tokenization with compound and technical term preservation.
        
        Args:
            text: Input text to tokenize
            
        Returns:
            List of word tokens
        """
        # Normalize Unicode
        text = self._normalize_unicode(text)
        
        # Step 1: Extract and replace compound terms first (they have priority)
        compound_placeholders, modified_text = self._extract_compound_terms(text)
        
        # Step 2: Extract technical terms from remaining text (only if no compound placeholders)
        tech_placeholders = {}
        if not compound_placeholders:  # Only if no compound terms to avoid conflicts
            technical_terms = self._extract_technical_terms(modified_text)

            # Step 3: Replace technical terms with placeholders using safe method
            tech_placeholders, modified_text = self._replace_technical_terms(modified_text, technical_terms)
        
        # Step 4: Basic tokenization on word boundaries
        words = re.findall(r'\b\w+\b', modified_text)
        
        # Step 5: Restore compound terms and technical terms
        restored_words = []
        for word in words:
            restored = False
            
            # Check compound placeholders first
            for placeholder, compound in compound_placeholders.items():
                if word == placeholder:
                    final_compound = compound.lower() if not self.preserve_case else compound
                    restored_words.append(final_compound)
                    restored = True
                    break
            
            if not restored:
                # Check technical placeholders
                for placeholder, tech_term in tech_placeholders.items():
                    if word == placeholder:
                        restored_words.append(tech_term)
                        restored = True
                        break
            
            if not restored:
                # Check for corrupted placeholders that weren't properly restored
                if '__TECH' in word or '__COMP' in word:
                    # Log this for debugging but skip the corrupted token
                    print(f"⚠️  Warning: Found corrupted placeholder: {word}")
                    continue

                # Regular word
                final_word = word.lower() if not self.preserve_case else word
                restored_words.append(final_word)
        
        # Step 6: Apply filters
        filtered_words = []
        for word in restored_words:
            # Skip empty words
            if not word or not word.strip():
                continue
                
            # Length filter (be more lenient for compound terms)
            min_len = self.min_word_len if ' ' not in word else 1
            if not (min_len <= len(word) <= self.max_word_len):
                continue
            
            # Stopword filter (don't filter compound terms)
            if self.filter_stopwords and ' ' not in word and self._is_stopword(word):
                continue
            
            filtered_words.append(word)
        
        return filtered_words
    
    def tokenize(self, text: str) -> List[str]:
        """
        Main tokenization method.
        
        Args:
            text: Input text to tokenize
            
        Returns:
            List of word tokens
        """
        if not text or not text.strip():
            return []
        
        return self._basic_tokenize(text)
    
    def tokenize_batch(self, texts: List[str]) -> List[List[str]]:
        """
        Tokenize a batch of texts.
        
        Args:
            texts: List of input texts
            
        Returns:
            List of token lists
        """
        return [self.tokenize(text) for text in texts]
    
    def get_stopwords(self) -> Set[str]:
        """Return the set of Spanish stopwords."""
        return self.spanish_stopwords.copy()
    
    def get_compound_terms(self) -> Set[str]:
        """Return the set of compound terms."""
        return self.compound_terms.copy()

class DualVocabularyBuilder:
    """
    Builds both full and filtered vocabularies simultaneously.
    Allows comparison of SPLADE performance with/without stopwords.
    """
    
    def __init__(self, min_freq: int = 1, max_vocab_size: int = 50000, 
                 include_special_tokens: bool = True, compound_terms: List[str] = None):
        """
        Initialize dual vocabulary builder.
        
        Args:
            min_freq: Minimum frequency for a word to be included
            max_vocab_size: Maximum vocabulary size
            include_special_tokens: Whether to include special tokens
        """
        self.min_freq = min_freq
        self.max_vocab_size = max_vocab_size
        self.include_special_tokens = include_special_tokens

        # Default compound terms if none provided
        if compound_terms is None:
            compound_terms = []
        
        # Create tokenizers
        self.tokenizer_full = WordTokenizer(filter_stopwords=False, compound_terms=compound_terms)
        self.tokenizer_filtered = WordTokenizer(filter_stopwords=True, compound_terms=compound_terms)
        
        # Create vocabulary builders
        self.vocab_full = VocabularyBuilder(
            tokenizer=self.tokenizer_full,
            min_freq=min_freq,
            max_vocab_size=max_vocab_size,
            include_special_tokens=include_special_tokens
        )
        
        self.vocab_filtered = VocabularyBuilder(
            tokenizer=self.tokenizer_filtered,
            min_freq=min_freq,
            max_vocab_size=max_vocab_size,
            include_special_tokens=include_special_tokens
        )
    
    def analyze_corpus(self, documents: List[Document]) -> Tuple[Dict, Dict]:
        """
        Analyze corpus with both tokenizers.
        
        Args:
            documents: List of documents to analyze
            
        Returns:
            Tuple of (full_stats, filtered_stats)
        """
        print("Analyzing corpus with full vocabulary...")
        full_stats = self.vocab_full.analyze_corpus(documents)
        
        print("\nAnalyzing corpus with filtered vocabulary...")
        filtered_stats = self.vocab_filtered.analyze_corpus(documents)
        
        return full_stats, filtered_stats
    
    def build_vocabularies(self, documents: List[Document]) -> None:
        """
        Build both vocabularies from document collection.
        
        Args:
            documents: List of documents to build vocabularies from
        """
        print("="*60)
        print("BUILDING DUAL VOCABULARIES")
        print("="*60)
        
        print("\n1. Building FULL vocabulary (with stopwords)...")
        self.vocab_full.build_vocabulary(documents)
        
        print("\n2. Building FILTERED vocabulary (without stopwords)...")
        self.vocab_filtered.build_vocabulary(documents)
        
        print("\n✅ Both vocabularies built successfully!")
    
    def calculate_coverage(self, documents: List[Document]) -> Tuple[Dict, Dict]:
        """
        Calculate coverage for both vocabularies.
        
        Args:
            documents: Documents to test coverage on
            
        Returns:
            Tuple of (full_coverage, filtered_coverage)
        """
        print("Calculating coverage for full vocabulary...")
        full_coverage = self.vocab_full.calculate_coverage(documents)
        
        print("Calculating coverage for filtered vocabulary...")
        filtered_coverage = self.vocab_filtered.calculate_coverage(documents)
        
        return full_coverage, filtered_coverage
    
    def save_vocabularies(self, base_path: Path, file_base: str) -> None:
        """
        Save both vocabularies to disk.
        
        Args:
            base_path: Base directory for saving
            file_base: Base filename for the vocabularies
        """
        # Save full vocabulary
        full_path = base_path / f"{file_base}_vocab_full_{self.max_vocab_size}"
        self.vocab_full.save_vocabulary(full_path)
        
        # Save filtered vocabulary
        filtered_path = base_path / f"{file_base}_vocab_filtered_{self.max_vocab_size}"
        self.vocab_filtered.save_vocabulary(filtered_path)
        
        # Save comparison stats
        comparison_stats = {
            "full_vocabulary": {
                "size": len(self.vocab_full.word_to_id),
                "total_tokens": self.vocab_full.total_tokens,
                "unique_words": self.vocab_full.unique_words,
            },
            "filtered_vocabulary": {
                "size": len(self.vocab_filtered.word_to_id),
                "total_tokens": self.vocab_filtered.total_tokens,
                "unique_words": self.vocab_filtered.unique_words,
            },
            "stopwords_removed": list(self.tokenizer_filtered.get_stopwords()),
            "configuration": {
                "min_freq": self.min_freq,
                "max_vocab_size": self.max_vocab_size,
                "include_special_tokens": self.include_special_tokens,
            }
        }
        
        comparison_path = base_path / f"{file_base}_vocabulary_comparison.json"
        with open(comparison_path, "w", encoding="utf-8") as f:
            json.dump(comparison_stats, f, ensure_ascii=False, indent=2)
        
        print(f"\n📁 Full vocabulary saved to: {full_path}")
        print(f"📁 Filtered vocabulary saved to: {filtered_path}")
        print(f"📊 Comparison stats saved to: {comparison_path}")
    
    def print_comparison_stats(self, full_stats: Dict = None, 
                              filtered_stats: Dict = None) -> None:
        """
        Print comparison statistics for both vocabularies.
        
        Args:
            full_stats: Full vocabulary corpus stats
            filtered_stats: Filtered vocabulary corpus stats
        """
        print("\n" + "="*60)
        print("DUAL VOCABULARY COMPARISON")
        print("="*60)
        
        # Print side-by-side comparison
        print(f"{'Metric':<25} {'Full':<15} {'Filtered':<15} {'Difference':<15}")
        print("-" * 70)
        
        if full_stats and filtered_stats:
            metrics = [
                ("Total tokens", "total_tokens"),
                ("Unique words", "unique_words"),
                ("Avg tokens/doc", "avg_tokens_per_doc"),
            ]
            
            for label, key in metrics:
                full_val = full_stats[key]
                filtered_val = filtered_stats[key]
                
                if isinstance(full_val, float):
                    diff = f"{full_val - filtered_val:+.1f}"
                    full_str = f"{full_val:.1f}"
                    filtered_str = f"{filtered_val:.1f}"
                else:
                    diff = f"{full_val - filtered_val:+,}"
                    full_str = f"{full_val:,}"
                    filtered_str = f"{filtered_val:,}"
                
                print(f"{label:<25} {full_str:<15} {filtered_str:<15} {diff:<15}")
        
        # Vocabulary sizes
        full_vocab_size = len(self.vocab_full.word_to_id)
        filtered_vocab_size = len(self.vocab_filtered.word_to_id)
        vocab_diff = full_vocab_size - filtered_vocab_size
        
        print(f"{'Vocabulary size':<25} {full_vocab_size:<15} {filtered_vocab_size:<15} {vocab_diff:+d}")
        
        # Show removed stopwords
        removed_stopwords = []
        for word in self.tokenizer_filtered.get_stopwords():
            if word in self.vocab_full.word_to_id:
                freq = self.vocab_full.word_freq.get(word, 0)
                removed_stopwords.append((word, freq))
        
        # Sort by frequency
        removed_stopwords.sort(key=lambda x: x[1], reverse=True)
        
        print(f"\nStopwords removed from vocabulary ({len(removed_stopwords)} total):")
        for word, freq in removed_stopwords[:10]:  # Show top 10
            print(f"  {word}: {freq:,} occurrences")
        
        if len(removed_stopwords) > 10:
            total_removed_freq = sum(freq for _, freq in removed_stopwords)
            print(f"  ... and {len(removed_stopwords) - 10} more")
            print(f"  Total stopword occurrences: {total_removed_freq:,}")
        
        print(f"\nMost frequent words in filtered vocabulary:")
        for word, freq in self.vocab_filtered.word_freq.most_common(10):
            if word not in self.vocab_filtered.special_tokens:
                print(f"  {word}: {freq:,}")


# Keep the original VocabularyBuilder class unchanged for compatibility
class VocabularyBuilder:
    """
    Original VocabularyBuilder - kept for compatibility.
    """
    
    def __init__(self, tokenizer: WordTokenizer = None, min_freq: int = 1, 
                 max_vocab_size: int = 50000, include_special_tokens: bool = True):
        self.tokenizer = tokenizer or WordTokenizer()
        self.min_freq = min_freq
        self.max_vocab_size = max_vocab_size
        self.include_special_tokens = include_special_tokens
        
        # Vocabulary mappings
        self.word_to_id: Dict[str, int] = {}
        self.id_to_word: Dict[int, str] = {}
        self.word_freq: Counter = Counter()
        
        # Special tokens
        self.special_tokens = {
            "[PAD]": 0,
            "[UNK]": 1,
            "[CLS]": 2,
            "[SEP]": 3,
            "[MASK]": 4,
        }
        
        # Statistics
        self.total_tokens = 0
        self.unique_words = 0
        self.coverage_stats = {}
    
    def _add_special_tokens(self):
        """Add special tokens to vocabulary."""
        if self.include_special_tokens:
            for token, idx in self.special_tokens.items():
                self.word_to_id[token] = idx
                self.id_to_word[idx] = token
    
    def analyze_corpus(self, documents: List[Document]) -> Dict:
        """Analyze corpus to gather vocabulary statistics."""
        print("Analyzing corpus for vocabulary statistics...")
        
        word_freq = Counter()
        total_tokens = 0
        total_docs = len(documents)
        
        for i, doc in enumerate(documents):
            if i % 1000 == 0:
                print(f"Analyzing document {i}/{total_docs}")
            
            text = doc.text if hasattr(doc, 'text') else str(doc)
            tokens = self.tokenizer.tokenize(text)
            
            word_freq.update(tokens)
            total_tokens += len(tokens)
        
        # Calculate statistics
        unique_words = len(word_freq)
        
        stats = {
            "total_documents": total_docs,
            "total_tokens": total_tokens,
            "unique_words": unique_words,
            "avg_tokens_per_doc": total_tokens / total_docs if total_docs > 0 else 0,
            "vocab_at_different_thresholds": {},
            "most_common_words": word_freq.most_common(50),
        }
        
        # Vocabulary size at different frequency thresholds
        for threshold in [1, 2, 5, 10, 20, 50]:
            vocab_size = sum(1 for freq in word_freq.values() if freq >= threshold)
            stats["vocab_at_different_thresholds"][threshold] = vocab_size
        
        return stats
    
    def build_vocabulary(self, documents: List[Document]) -> None:
        """Build vocabulary from document collection."""
        print(f"Building vocabulary from {len(documents)} documents...")
        print(f"Settings: min_freq={self.min_freq}, max_vocab_size={self.max_vocab_size}")
        
        # Reset vocabulary
        self.word_to_id.clear()
        self.id_to_word.clear()
        self.word_freq.clear()
        
        # Add special tokens first
        self._add_special_tokens()
        
        # Count word frequencies
        for i, doc in enumerate(documents):
            if i % 1000 == 0:
                print(f"Processing document {i}/{len(documents)}")
            
            text = doc.text if hasattr(doc, 'text') else str(doc)
            tokens = self.tokenizer.tokenize(text)
            self.word_freq.update(tokens)
            self.total_tokens += len(tokens)
        
        # Filter by frequency and build final vocabulary
        filtered_words = [
            word for word, freq in self.word_freq.items()
            if freq >= self.min_freq
        ]
        
        # Sort by frequency (most common first)
        filtered_words.sort(key=lambda w: self.word_freq[w], reverse=True)
        
        # Limit vocabulary size
        if len(filtered_words) > self.max_vocab_size - len(self.special_tokens):
            filtered_words = filtered_words[:self.max_vocab_size - len(self.special_tokens)]
        
        # Build word-to-id mapping
        next_id = len(self.special_tokens)
        for word in filtered_words:
            self.word_to_id[word] = next_id
            self.id_to_word[next_id] = word
            next_id += 1
        
        self.unique_words = len(self.word_to_id)
        
        print(f"Vocabulary built: {self.unique_words} words")
        print(f"Total tokens processed: {self.total_tokens}")
        print(f"Coverage: {len(filtered_words) / len(self.word_freq) * 100:.2f}%")
    
    def calculate_coverage(self, documents: List[Document]) -> Dict:
        """Calculate vocabulary coverage on a document set."""
        total_tokens = 0
        covered_tokens = 0
        oov_words = Counter()
        
        for doc in documents:
            text = doc.text if hasattr(doc, 'text') else str(doc)
            tokens = self.tokenizer.tokenize(text)
            
            for token in tokens:
                total_tokens += 1
                if token in self.word_to_id:
                    covered_tokens += 1
                else:
                    oov_words[token] += 1
        
        coverage = covered_tokens / total_tokens if total_tokens > 0 else 0
        
        return {
            "coverage_ratio": coverage,
            "total_tokens": total_tokens,
            "covered_tokens": covered_tokens,
            "oov_tokens": total_tokens - covered_tokens,
            "unique_oov_words": len(oov_words),
            "most_common_oov": oov_words.most_common(20),
        }
    
    def encode(self, text: str) -> List[int]:
        """Encode text to token IDs."""
        tokens = self.tokenizer.tokenize(text)
        return [self.word_to_id.get(token, self.special_tokens["[UNK]"]) for token in tokens]
    
    def decode(self, token_ids: List[int]) -> List[str]:
        """Decode token IDs to words."""
        return [self.id_to_word.get(id, "[UNK]") for id in token_ids]
    
    def save_vocabulary(self, save_path: Path) -> None:
        """Save vocabulary to disk."""
        save_path.mkdir(parents=True, exist_ok=True)
        
        # Save mappings
        with open(save_path / "word_to_id.json", "w", encoding="utf-8") as f:
            json.dump(self.word_to_id, f, ensure_ascii=False, indent=2)
        
        with open(save_path / "id_to_word.json", "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in self.id_to_word.items()}, f, ensure_ascii=False, indent=2)
        
        # Save frequencies
        with open(save_path / "word_frequencies.json", "w", encoding="utf-8") as f:
            json.dump(dict(self.word_freq), f, ensure_ascii=False, indent=2)
        
        # Save tokenizer and builder state
        vocab_state = {
            "tokenizer_config": {
                "preserve_case": self.tokenizer.preserve_case,
                "min_word_len": self.tokenizer.min_word_len,
                "max_word_len": self.tokenizer.max_word_len,
                "filter_stopwords": getattr(self.tokenizer, 'filter_stopwords', False),
            },
            "builder_config": {
                "min_freq": self.min_freq,
                "max_vocab_size": self.max_vocab_size,
                "include_special_tokens": self.include_special_tokens,
            },
            "statistics": {
                "total_tokens": self.total_tokens,
                "unique_words": self.unique_words,
                "vocab_size": len(self.word_to_id),
            },
            "special_tokens": self.special_tokens,
        }
        
        with open(save_path / "vocabulary_config.json", "w", encoding="utf-8") as f:
            json.dump(vocab_state, f, ensure_ascii=False, indent=2)
        
        print(f"Vocabulary saved to {save_path}")
    
    @classmethod
    def load_vocabulary(cls, save_path: Path) -> "VocabularyBuilder":
        """Load vocabulary from disk."""
        # Load configuration
        with open(save_path / "vocabulary_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # Recreate tokenizer
        tokenizer_config = config["tokenizer_config"]
        tokenizer = WordTokenizer(**tokenizer_config)
        
        # Recreate builder
        builder_config = config["builder_config"]
        builder = cls(tokenizer=tokenizer, **builder_config)
        
        # Load mappings
        with open(save_path / "word_to_id.json", "r", encoding="utf-8") as f:
            builder.word_to_id = json.load(f)
        
        with open(save_path / "id_to_word.json", "r", encoding="utf-8") as f:
            id_to_word_str = json.load(f)
            builder.id_to_word = {int(k): v for k, v in id_to_word_str.items()}
        
        # Load frequencies
        with open(save_path / "word_frequencies.json", "r", encoding="utf-8") as f:
            freq_dict = json.load(f)
            builder.word_freq = Counter(freq_dict)
        
        # Load statistics
        stats = config["statistics"]
        builder.total_tokens = stats["total_tokens"]
        builder.unique_words = stats["unique_words"]
        builder.special_tokens = config["special_tokens"]
        
        print(f"Vocabulary loaded from {save_path}")
        print(f"Vocabulary size: {len(builder.word_to_id)}")
        
        return builder


def print_vocabulary_stats(vocab_builder: VocabularyBuilder, 
                         corpus_stats: Dict = None) -> None:
    """Print comprehensive vocabulary statistics."""
    print("\n" + "="*60)
    print("VOCABULARY STATISTICS")
    print("="*60)
    
    if corpus_stats:
        print(f"Corpus Analysis:")
        print(f"  Total documents: {corpus_stats['total_documents']:,}")
        print(f"  Total tokens: {corpus_stats['total_tokens']:,}")
        print(f"  Unique words: {corpus_stats['unique_words']:,}")
        print(f"  Avg tokens/doc: {corpus_stats['avg_tokens_per_doc']:.1f}")
        print()
        
        print("Vocabulary size at different frequency thresholds:")
        for threshold, size in corpus_stats['vocab_at_different_thresholds'].items():
            print(f"  Min freq {threshold:2d}: {size:,} words")
        print()
    
    print(f"Final Vocabulary:")
    print(f"  Vocabulary size: {len(vocab_builder.word_to_id):,}")
    print(f"  Min frequency: {vocab_builder.min_freq}")
    print(f"  Max vocab size: {vocab_builder.max_vocab_size:,}")
    print(f"  Special tokens: {len(vocab_builder.special_tokens)}")
    print()
    
    print("Most frequent words:")
    for word, freq in vocab_builder.word_freq.most_common(20):
        if word not in vocab_builder.special_tokens:
            print(f"  {word}: {freq:,}")