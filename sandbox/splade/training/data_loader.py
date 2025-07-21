"""
SPLADE Word-Level Training Data Loader

This module provides data loading and preprocessing functionality for training
word-level SPLADE models on documento/resumen pairs. It handles tokenization,
batch creation, and various training data formats.
"""

import torch
import pickle
import random
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union, Any
from dataclasses import dataclass
from torch.utils.data import Dataset, DataLoader, random_split
from llama_index.core import Document

# Import our components
from sandbox.splade.core.vocabulary import VocabularyBuilder
from sandbox.splade.core.models import WordLevelTokenizer
from sandbox.splade.training.config import ExperimentConfig, ConfigManager

def load_documents(self, file_base: str) -> Tuple[List[Document], List[Document]]:
        """
        Load documento and resumen collections.
        
        Args:
            file_base: Base filename for document files
            
        Returns:
            Tuple of (texto_docs, resumen_docs)
        """
        data_path = Path(self.config.data.data_path)
        
        # Load texto documents
        texto_path = data_path / f"{file_base}_texto.pkl"
        with open(texto_path, 'rb') as f:
            texto_docs = pickle.load(f)
        
        # Load resumen documents  
        resumen_path = data_path / f"{file_base}_resumen.pkl"
        with open(resumen_path, 'rb') as f:
            resumen_docs = pickle.load(f)
            
        print(f"Loaded {len(texto_docs)} texto documents")
        print(f"Loaded {len(resumen_docs)} resumen documents")
        
        return texto_docs, resumen_docs

@dataclass
class TrainingExample:
    """Single training example for SPLADE with work item characterization."""
    # Document content
    doc_id: str
    doc_text: str
    doc_tokens: List[str]
    doc_input_ids: torch.Tensor
    doc_attention_mask: torch.Tensor
    
    # Query/summary content (resumen)
    query_text: Optional[str] = None
    query_tokens: Optional[List[str]] = None
    query_input_ids: Optional[torch.Tensor] = None
    query_attention_mask: Optional[torch.Tensor] = None
    
    # Work item characterization data
    concept_id: Optional[str] = None  # Derived from resumen text
    parameters: Optional[Dict[str, str]] = None  # From document metadata
    parameter_labels: Optional[Dict[str, int]] = None  # Encoded parameter values
    
    # Metadata
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DataLoader."""
        result = {
            'doc_id': self.doc_id,
            'doc_input_ids': self.doc_input_ids,
            'doc_attention_mask': self.doc_attention_mask,
        }
        
        if self.query_input_ids is not None:
            result.update({
                'query_input_ids': self.query_input_ids,
                'query_attention_mask': self.query_attention_mask,
            })
        
        if self.metadata:
            result['metadata'] = self.metadata
            
        return result


class SpladeDataset(Dataset):
    """PyTorch Dataset for SPLADE training with work item characterization."""
    
    def __init__(self, 
                 examples: List[TrainingExample],
                 training_mode: str = "contrastive",
                 concept_vocab: Optional[Dict[str, int]] = None,
                 parameter_vocabs: Optional[Dict[str, Dict[str, int]]] = None):
        """
        Initialize SPLADE dataset.
        
        Args:
            examples: List of training examples
            training_mode: "contrastive", "mlm", "ranking", or "characterization"
            concept_vocab: Mapping from concept IDs to integer labels
            parameter_vocabs: Mapping from parameter names to value vocabularies
        """
        self.examples = examples
        self.training_mode = training_mode
        self.concept_vocab = concept_vocab or {}
        self.parameter_vocabs = parameter_vocabs or {}
        
        print(f"Created SpladeDataset with {len(examples)} examples")
        print(f"Training mode: {training_mode}")
        if concept_vocab:
            print(f"Concept vocabulary size: {len(concept_vocab)}")
        if parameter_vocabs:
            print(f"Parameter vocabularies: {list(parameter_vocabs.keys())}")
    
    def __len__(self) -> int:
        return len(self.examples)
    
    def __getitem__(self, idx: int) -> Dict[str, Any]:
        """Get a single training example."""
        example = self.examples[idx]
        
        if self.training_mode == "contrastive":
            return self._get_contrastive_example(example)
        elif self.training_mode == "mlm":
            return self._get_mlm_example(example)
        elif self.training_mode == "ranking":
            return self._get_ranking_example(example)
        elif self.training_mode == "characterization":
            return self._get_characterization_example(example)
        else:
            return example.to_dict()
    
    def _get_characterization_example(self, example: TrainingExample) -> Dict[str, Any]:
        """Prepare example for work item characterization training."""
        result = {
            'input_ids': example.doc_input_ids,
            'attention_mask': example.doc_attention_mask,
            'doc_id': example.doc_id,
        }
        
        # Add concept label if available
        if example.concept_id and example.concept_id in self.concept_vocab:
            result['concept_label'] = self.concept_vocab[example.concept_id]
        
        # Add parameter labels if available
        if example.parameter_labels:
            for param_name, label in example.parameter_labels.items():
                result[f'param_{param_name}'] = label
        
        # Add query for contrastive component
        if example.query_input_ids is not None:
            result.update({
                'query_input_ids': example.query_input_ids,
                'query_attention_mask': example.query_attention_mask,
            })
        
        return result
    
    def _get_contrastive_example(self, example: TrainingExample) -> Dict[str, Any]:
        """Prepare example for contrastive learning (doc-summary pairs)."""
        result = {
            'input_ids': example.doc_input_ids,
            'attention_mask': example.doc_attention_mask,
            'labels': 'positive',  # All our doc-summary pairs are positive
        }
        
        # Add query/summary if available
        if example.query_input_ids is not None:
            result.update({
                'query_input_ids': example.query_input_ids,
                'query_attention_mask': example.query_attention_mask,
            })
        
        return result
    
    def _get_mlm_example(self, example: TrainingExample) -> Dict[str, Any]:
        """Prepare example for masked language modeling."""
        # For MLM, we'll mask the document tokens
        input_ids = example.doc_input_ids.clone()
        attention_mask = example.doc_attention_mask.clone()
        
        # Create MLM labels (we'll implement masking in the trainer)
        labels = input_ids.clone()
        
        return {
            'input_ids': input_ids,
            'attention_mask': attention_mask,
            'labels': labels,
            'original_input_ids': example.doc_input_ids,  # Keep original for reference
        }
    
    def _get_ranking_example(self, example: TrainingExample) -> Dict[str, Any]:
        """Prepare example for ranking-based training."""
        return {
            'doc_input_ids': example.doc_input_ids,
            'doc_attention_mask': example.doc_attention_mask,
            'query_input_ids': example.query_input_ids,
            'query_attention_mask': example.query_attention_mask,
            'doc_id': example.doc_id,
        }


class SpladeDataProcessor:
    """Processes raw documents into training examples with work item characterization."""
    
    def __init__(self, 
                 tokenizer: WordLevelTokenizer,
                 config: ExperimentConfig):
        """
        Initialize data processor.
        
        Args:
            tokenizer: Word-level tokenizer
            config: Training configuration
        """
        self.tokenizer = tokenizer
        self.config = config
        self.max_length = config.data.max_sequence_length
        
        # Initialize vocabularies for work item characterization
        self.concept_vocab = {}  # concept_id -> integer
        self.parameter_vocabs = {}  # param_name -> {value -> integer}
        
        print(f"SpladeDataProcessor initialized")
        print(f"Max sequence length: {self.max_length}")
        print(f"Vocabulary size: {tokenizer.vocab_size}")
    
    def build_characterization_vocabularies(self, 
                                           texto_docs: List[Document], 
                                           resumen_docs: List[Document]) -> None:
        """
        Build vocabularies for concept IDs and parameter values.
        
        Args:
            texto_docs: Full text documents with parameters
            resumen_docs: Summary documents (concept descriptions)
        """
        print("Building work item characterization vocabularies...")
        
        # Build concept vocabulary from resumen texts
        concept_counts = {}
        for doc in resumen_docs:
            concept_text = doc.text if hasattr(doc, 'text') else str(doc)
            # Normalize concept text (could be enhanced with clustering)
            concept_id = concept_text.strip().upper()
            concept_counts[concept_id] = concept_counts.get(concept_id, 0) + 1
        
        # Keep concepts that appear at least twice
        self.concept_vocab = {
            concept: idx for idx, concept in enumerate(
                sorted([c for c, count in concept_counts.items() if count >= 2])
            )
        }
        
        # Build parameter vocabularies from texto document metadata
        parameter_counts = {}
        for doc in texto_docs:
            if hasattr(doc, 'metadata') and 'parameters' in doc.metadata:
                parameters = doc.metadata['parameters']
                for param_key, param_data in parameters.items():
                    if param_key not in parameter_counts:
                        parameter_counts[param_key] = {}
                    
                    # Extract parameter values
                    if isinstance(param_data, dict):
                        if 'label' in param_data:
                            value = param_data['label']
                            parameter_counts[param_key][value] = parameter_counts[param_key].get(value, 0) + 1
                        
                        if 'values' in param_data and isinstance(param_data['values'], list):
                            for value_item in param_data['values']:
                                if isinstance(value_item, dict) and 'value' in value_item:
                                    value = value_item['value']
                                    parameter_counts[param_key][value] = parameter_counts[param_key].get(value, 0) + 1
        
        # Build parameter vocabularies (keep values appearing at least twice)
        self.parameter_vocabs = {}
        for param_name, value_counts in parameter_counts.items():
            filtered_values = [v for v, count in value_counts.items() if count >= 2]
            if filtered_values:
                self.parameter_vocabs[param_name] = {
                    value: idx for idx, value in enumerate(sorted(filtered_values))
                }
        
        print(f"Built concept vocabulary: {len(self.concept_vocab)} concepts")
        print(f"Built parameter vocabularies: {list(self.parameter_vocabs.keys())}")
        for param_name, vocab in self.parameter_vocabs.items():
            print(f"  {param_name}: {len(vocab)} values")
    
    def extract_work_item_info(self, texto_doc: Document, resumen_doc: Document) -> Tuple[str, Dict[str, str], Dict[str, int]]:
        """
        Extract work item characterization information from document pair.
        
        Args:
            texto_doc: Full text document with parameters
            resumen_doc: Summary document (concept description)
            
        Returns:
            Tuple of (concept_id, parameters, parameter_labels)
        """
        # Extract concept ID from resumen
        concept_text = resumen_doc.text if hasattr(resumen_doc, 'text') else str(resumen_doc)
        concept_id = concept_text.strip().upper()
        
        # Extract parameters from texto metadata
        parameters = {}
        parameter_labels = {}
        
        if hasattr(texto_doc, 'metadata') and 'parameters' in texto_doc.metadata:
            doc_parameters = texto_doc.metadata['parameters']
            
            for param_key, param_data in doc_parameters.items():
                if isinstance(param_data, dict):
                    # Extract parameter value
                    param_value = None
                    if 'label' in param_data:
                        param_value = param_data['label']
                    elif 'values' in param_data and isinstance(param_data['values'], list):
                        # Take first value if multiple
                        for value_item in param_data['values']:
                            if isinstance(value_item, dict) and 'value' in value_item:
                                param_value = value_item['value']
                                break
                    
                    if param_value:
                        parameters[param_key] = param_value
                        
                        # Convert to label if in vocabulary
                        if (param_key in self.parameter_vocabs and 
                            param_value in self.parameter_vocabs[param_key]):
                            parameter_labels[param_key] = self.parameter_vocabs[param_key][param_value]
        
        return concept_id, parameters, parameter_labels
        """
        Load documento and resumen collections.
        
        Args:
            file_base: Base filename for document files
            
        Returns:
            Tuple of (texto_docs, resumen_docs)
        """
        data_path = Path(self.config.data.data_path)
        
        # Load texto documents
        texto_path = data_path / f"{file_base}_texto.pkl"
        with open(texto_path, 'rb') as f:
            texto_docs = pickle.load(f)
        
        # Load resumen documents  
        resumen_path = data_path / f"{file_base}_resumen.pkl"
        with open(resumen_path, 'rb') as f:
            resumen_docs = pickle.load(f)
            
        print(f"Loaded {len(texto_docs)} texto documents")
        print(f"Loaded {len(resumen_docs)} resumen documents")
        
        return texto_docs, resumen_docs
    
    def create_training_examples(self, 
                                texto_docs: List[Document], 
                                resumen_docs: List[Document],
                                max_examples: Optional[int] = None,
                                include_characterization: bool = True) -> List[TrainingExample]:
        """
        Create training examples from document pairs with work item characterization.
        
        Args:
            texto_docs: Full text documents
            resumen_docs: Summary documents
            max_examples: Limit number of examples (for testing)
            include_characterization: Whether to extract work item info
            
        Returns:
            List of training examples
        """
        print(f"Creating training examples from {len(texto_docs)} document pairs...")
        
        # Build characterization vocabularies if needed
        if include_characterization and not self.concept_vocab:
            self.build_characterization_vocabularies(texto_docs, resumen_docs)
        
        examples = []
        
        # Process in batches for memory efficiency
        batch_size = 1000
        total_docs = min(len(texto_docs), len(resumen_docs))
        
        if max_examples:
            total_docs = min(total_docs, max_examples)
            
        for i in range(0, total_docs, batch_size):
            end_idx = min(i + batch_size, total_docs)
            batch_texto = texto_docs[i:end_idx]
            batch_resumen = resumen_docs[i:end_idx]
            
            print(f"Processing batch {i//batch_size + 1}: docs {i}-{end_idx}")
            
            for j, (texto_doc, resumen_doc) in enumerate(zip(batch_texto, batch_resumen)):
                try:
                    example = self._create_single_example(
                        texto_doc, resumen_doc, i + j, include_characterization
                    )
                    if example:
                        examples.append(example)
                except Exception as e:
                    print(f"Warning: Failed to process document {i + j}: {e}")
                    continue
        
        print(f"Created {len(examples)} training examples")
        return examples
    
    def _create_single_example(self, 
                              texto_doc: Document, 
                              resumen_doc: Document, 
                              doc_idx: int,
                              include_characterization: bool = True) -> Optional[TrainingExample]:
        """Create a single training example from document pair with work item info."""
        
        # Extract text content
        doc_text = texto_doc.text if hasattr(texto_doc, 'text') else str(texto_doc)
        query_text = resumen_doc.text if hasattr(resumen_doc, 'text') else str(resumen_doc)
        
        # Skip if either text is too short
        if len(doc_text.strip()) < 10 or len(query_text.strip()) < 5:
            return None
        
        # Tokenize document
        doc_encoding = self.tokenizer(
            doc_text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )
        
        # Tokenize query/summary
        query_encoding = self.tokenizer(
            query_text,
            max_length=self.max_length // 2,  # Summaries are typically shorter
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )
        
        # Extract tokens for analysis
        doc_tokens = self.tokenizer.tokenize(doc_text)
        query_tokens = self.tokenizer.tokenize(query_text)
        
        # Extract work item characterization info
        concept_id = None
        parameters = None
        parameter_labels = None
        
        if include_characterization:
            concept_id, parameters, parameter_labels = self.extract_work_item_info(texto_doc, resumen_doc)
        
        # Create example
        example = TrainingExample(
            doc_id=f"doc_{doc_idx}",
            doc_text=doc_text,
            doc_tokens=doc_tokens,
            doc_input_ids=doc_encoding['input_ids'].squeeze(0),
            doc_attention_mask=doc_encoding['attention_mask'].squeeze(0),
            query_text=query_text,
            query_tokens=query_tokens,
            query_input_ids=query_encoding['input_ids'].squeeze(0),
            query_attention_mask=query_encoding['attention_mask'].squeeze(0),
            concept_id=concept_id,
            parameters=parameters,
            parameter_labels=parameter_labels,
            metadata={
                'doc_length': len(doc_tokens),
                'query_length': len(query_tokens),
                'doc_id': getattr(texto_doc, 'doc_id', f"doc_{doc_idx}"),
                'has_characterization': include_characterization and concept_id is not None,
            }
        )
        
        return example
    
    def create_document_only_examples(self, 
                                     documents: List[Document],
                                     max_examples: Optional[int] = None) -> List[TrainingExample]:
        """
        Create examples from documents only (for MLM pre-training).
        
        Args:
            documents: List of documents
            max_examples: Limit number of examples
            
        Returns:
            List of training examples
        """
        print(f"Creating document-only examples from {len(documents)} documents...")
        
        examples = []
        total_docs = len(documents)
        
        if max_examples:
            total_docs = min(total_docs, max_examples)
            
        for i in range(total_docs):
            if i % 1000 == 0:
                print(f"Processing document {i}/{total_docs}")
                
            try:
                doc = documents[i]
                doc_text = doc.text if hasattr(doc, 'text') else str(doc)
                
                # Skip very short documents
                if len(doc_text.strip()) < 20:
                    continue
                
                # Tokenize document
                doc_encoding = self.tokenizer(
                    doc_text,
                    max_length=self.max_length,
                    padding="max_length",
                    truncation=True,
                    return_tensors="pt"
                )
                
                doc_tokens = self.tokenizer.tokenize(doc_text)
                
                example = TrainingExample(
                    doc_id=f"doc_{i}",
                    doc_text=doc_text,
                    doc_tokens=doc_tokens,
                    doc_input_ids=doc_encoding['input_ids'].squeeze(0),
                    doc_attention_mask=doc_encoding['attention_mask'].squeeze(0),
                    metadata={
                        'doc_length': len(doc_tokens),
                        'doc_id': getattr(doc, 'doc_id', f"doc_{i}"),
                    }
                )
                
                examples.append(example)
                
            except Exception as e:
                print(f"Warning: Failed to process document {i}: {e}")
                continue
        
        print(f"Created {len(examples)} document-only examples")
        return examples


class SpladeDataLoader:
    """High-level data loader for SPLADE training."""
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize with configuration."""
        self.config = config_manager.config
        
        # Load vocabulary and create tokenizer
        self._load_vocabulary()
        
        # Initialize data processor
        self.processor = SpladeDataProcessor(self.tokenizer, self.config)
        
        # Set random seeds for reproducibility
        self._set_seeds()
    
    def _load_vocabulary(self):
        """Load vocabulary and create tokenizer."""
        vocab_suffix = "filtered" if self.config.data.use_filtered_vocab else "full"
        vocab_path = Path(self.config.data.vocab_path) / f"{self.config.data.vocab_file_base}_vocab_{vocab_suffix}_{self.config.model.vocab_size}"
        
        print(f"Loading vocabulary from: {vocab_path}")
        vocab_builder = VocabularyBuilder.load_vocabulary(vocab_path)
        
        self.tokenizer = WordLevelTokenizer(
            vocab_builder=vocab_builder,
            max_length=self.config.data.max_sequence_length
        )
        
        print(f"Tokenizer loaded with vocabulary size: {self.tokenizer.vocab_size}")
    
    def _set_seeds(self):
        """Set random seeds for reproducibility."""
        seed = self.config.data.random_seed
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    
    def create_train_val_test_loaders(self, 
                                     training_mode: str = "contrastive",
                                     max_examples: Optional[int] = None,
                                     include_characterization: bool = True) -> Tuple[DataLoader, DataLoader, DataLoader]:
        """
        Create train, validation, and test data loaders.
        
        Args:
            training_mode: "contrastive", "mlm", "ranking", or "characterization"
            max_examples: Limit total examples for testing
            include_characterization: Whether to include work item characterization
            
        Returns:
            Tuple of (train_loader, val_loader, test_loader)
        """
        print(f"Creating data loaders for {training_mode} training...")
        
        # Load documents
        texto_docs, resumen_docs = self.processor.load_documents(self.config.data.file_base)
        
        # Create training examples
        if training_mode == "mlm":
            # For MLM, use all documents (texto + resumen)
            all_docs = texto_docs + resumen_docs
            examples = self.processor.create_document_only_examples(all_docs, max_examples)
        else:
            # For contrastive/ranking/characterization, use documento-resumen pairs
            examples = self.processor.create_training_examples(
                texto_docs, resumen_docs, max_examples, include_characterization
            )
        
        # Split into train/val/test
        train_examples, val_examples, test_examples = self._split_examples(examples)
        
        # Create datasets with vocabularies for characterization
        dataset_kwargs = {
            'training_mode': training_mode,
        }
        if include_characterization:
            dataset_kwargs.update({
                'concept_vocab': self.processor.concept_vocab,
                'parameter_vocabs': self.processor.parameter_vocabs,
            })
        
        train_dataset = SpladeDataset(train_examples, **dataset_kwargs)
        val_dataset = SpladeDataset(val_examples, **dataset_kwargs)
        test_dataset = SpladeDataset(test_examples, **dataset_kwargs)
        
        # Create data loaders
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.data.batch_size,
            shuffle=True,
            num_workers=self.config.data.num_workers,
            pin_memory=self.config.data.pin_memory,
            drop_last=self.config.data.drop_last,
            collate_fn=self._collate_fn
        )
        
        val_loader = DataLoader(
            val_dataset,
            batch_size=self.config.data.eval_batch_size,
            shuffle=False,
            num_workers=self.config.data.num_workers,
            pin_memory=self.config.data.pin_memory,
            drop_last=False,
            collate_fn=self._collate_fn
        )
        
        test_loader = DataLoader(
            test_dataset,
            batch_size=self.config.data.eval_batch_size,
            shuffle=False,
            num_workers=self.config.data.num_workers,
            pin_memory=self.config.data.pin_memory,
            drop_last=False,
            collate_fn=self._collate_fn
        )
        
        print(f"Created data loaders:")
        print(f"  Train: {len(train_loader)} batches ({len(train_examples)} examples)")
        print(f"  Val:   {len(val_loader)} batches ({len(val_examples)} examples)")
        print(f"  Test:  {len(test_loader)} batches ({len(test_examples)} examples)")
        
        if include_characterization:
            print(f"  Concept vocabulary: {len(self.processor.concept_vocab)} concepts")
            print(f"  Parameter vocabularies: {list(self.processor.parameter_vocabs.keys())}")
        
        return train_loader, val_loader, test_loaderworkers=self.config.data.num_workers,
            pin_memory=self.config.data.pin_memory,
            drop_last=False,
            collate_fn=self._collate_fn
        )
        
        test_loader = DataLoader(
            test_dataset,
            batch_size=self.config.data.eval_batch_size,
            shuffle=False,
            num_workers=self.config.data.num_workers,
            pin_memory=self.config.data.pin_memory,
            drop_last=False,
            collate_fn=self._collate_fn
        )
        
        print(f"Created data loaders:")
        print(f"  Train: {len(train_loader)} batches ({len(train_examples)} examples)")
        print(f"  Val:   {len(val_loader)} batches ({len(val_examples)} examples)")
        print(f"  Test:  {len(test_loader)} batches ({len(test_examples)} examples)")
        
        return train_loader, val_loader, test_loader
    
    def _split_examples(self, examples: List[TrainingExample]) -> Tuple[List[TrainingExample], List[TrainingExample], List[TrainingExample]]:
        """Split examples into train/val/test sets."""
        total_examples = len(examples)
        
        # Calculate split sizes
        train_size = int(total_examples * self.config.data.train_split)
        val_size = int(total_examples * self.config.data.val_split)
        test_size = total_examples - train_size - val_size
        
        # Shuffle examples
        random.shuffle(examples)
        
        # Split
        train_examples = examples[:train_size]
        val_examples = examples[train_size:train_size + val_size]
        test_examples = examples[train_size + val_size:]
        
        print(f"Data split: Train={len(train_examples)}, Val={len(val_examples)}, Test={len(test_examples)}")
        
        return train_examples, val_examples, test_examples
    
    def _collate_fn(self, batch: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
        """Custom collate function for batching."""
        # Get all keys from the first item
        keys = batch[0].keys()
        collated = {}
        
        for key in keys:
            if key in ['doc_id', 'metadata']:
                # Keep as list for non-tensor data
                collated[key] = [item[key] for item in batch]
            else:
                # Stack tensors
                tensors = [item[key] for item in batch if key in item]
                if tensors and isinstance(tensors[0], torch.Tensor):
                    collated[key] = torch.stack(tensors)
                else:
                    collated[key] = tensors
        
        return collated
    
    def get_data_statistics(self, examples: List[TrainingExample]) -> Dict[str, Any]:
        """Get statistics about the training data."""
        doc_lengths = [len(ex.doc_tokens) for ex in examples]
        query_lengths = [len(ex.query_tokens) for ex in examples if ex.query_tokens]
        
        stats = {
            'total_examples': len(examples),
            'doc_length_stats': {
                'mean': np.mean(doc_lengths),
                'std': np.std(doc_lengths),
                'min': np.min(doc_lengths),
                'max': np.max(doc_lengths),
                'median': np.median(doc_lengths),
            },
            'vocab_coverage': self._calculate_vocab_coverage(examples),
        }
        
        if query_lengths:
            stats['query_length_stats'] = {
                'mean': np.mean(query_lengths),
                'std': np.std(query_lengths),
                'min': np.min(query_lengths),
                'max': np.max(query_lengths),
                'median': np.median(query_lengths),
            }
        
        return stats
    
    def _calculate_vocab_coverage(self, examples: List[TrainingExample]) -> Dict[str, float]:
        """Calculate vocabulary coverage statistics."""
        all_tokens = set()
        total_tokens = 0
        oov_tokens = 0
        
        for example in examples:
            tokens = example.doc_tokens
            if example.query_tokens:
                tokens = tokens + example.query_tokens
                
            for token in tokens:
                all_tokens.add(token)
                total_tokens += 1
                if token not in self.tokenizer.vocab:
                    oov_tokens += 1
        
        return {
            'unique_tokens': len(all_tokens),
            'total_tokens': total_tokens,
            'oov_rate': oov_tokens / total_tokens if total_tokens > 0 else 0,
            'coverage_rate': 1 - (oov_tokens / total_tokens) if total_tokens > 0 else 1,
        }


# Convenience functions for Jupyter notebooks
def create_data_loaders(config_manager: ConfigManager, 
                       training_mode: str = "characterization",
                       max_examples: Optional[int] = None,
                       include_characterization: bool = True) -> Tuple[DataLoader, DataLoader, DataLoader]:
    """Quick function to create data loaders with work item characterization."""
    data_loader = SpladeDataLoader(config_manager)
    return data_loader.create_train_val_test_loaders(training_mode, max_examples, include_characterization)


def analyze_work_item_data(config_manager: ConfigManager, 
                          max_examples: int = 1000) -> Dict[str, Any]:
    """Analyze work item characterization data."""
    data_loader = SpladeDataLoader(config_manager)
    
    # Load a sample of documents
    texto_docs, resumen_docs = data_loader.processor.load_documents(config_manager.config.data.file_base)
    examples = data_loader.processor.create_training_examples(
        texto_docs[:max_examples], 
        resumen_docs[:max_examples], 
        include_characterization=True
    )
    
    # Get statistics
    stats = data_loader.get_data_statistics(examples)
    
    # Add work item characterization statistics
    concept_distribution = {}
    parameter_distributions = {}
    characterization_coverage = 0
    
    for example in examples:
        if example.concept_id:
            characterization_coverage += 1
            concept_distribution[example.concept_id] = concept_distribution.get(example.concept_id, 0) + 1
        
        if example.parameters:
            for param_name, param_value in example.parameters.items():
                if param_name not in parameter_distributions:
                    parameter_distributions[param_name] = {}
                parameter_distributions[param_name][param_value] = parameter_distributions[param_name].get(param_value, 0) + 1
    
    stats['work_item_stats'] = {
        'characterization_coverage': characterization_coverage / len(examples),
        'unique_concepts': len(concept_distribution),
        'concept_distribution': sorted(concept_distribution.items(), key=lambda x: x[1], reverse=True)[:10],
        'parameter_types': list(parameter_distributions.keys()),
        'parameter_distributions': {
            param: sorted(dist.items(), key=lambda x: x[1], reverse=True)[:5]
            for param, dist in parameter_distributions.items()
        }
    }
    
    print("="*60)
    print("WORK ITEM CHARACTERIZATION DATA ANALYSIS")
    print("="*60)
    
    print(f"Total examples: {stats['total_examples']:,}")
    print(f"Characterization coverage: {stats['work_item_stats']['characterization_coverage']:.1%}")
    print(f"Unique concepts: {stats['work_item_stats']['unique_concepts']}")
    
    print(f"\nDocument length statistics:")
    doc_stats = stats['doc_length_stats']
    print(f"  Mean: {doc_stats['mean']:.1f} tokens")
    print(f"  Median: {doc_stats['median']:.1f} tokens")
    print(f"  Min-Max: {doc_stats['min']}-{doc_stats['max']} tokens")
    
    if 'query_length_stats' in stats:
        print(f"\nQuery/Summary length statistics:")
        query_stats = stats['query_length_stats']
        print(f"  Mean: {query_stats['mean']:.1f} tokens")
        print(f"  Median: {query_stats['median']:.1f} tokens")
    
    print(f"\nTop concepts:")
    for concept, count in stats['work_item_stats']['concept_distribution']:
        print(f"  {concept}: {count} documents")
    
    print(f"\nParameter types found: {len(stats['work_item_stats']['parameter_types'])}")
    for param_name in stats['work_item_stats']['parameter_types'][:5]:
        print(f"  {param_name}")
        for value, count in stats['work_item_stats']['parameter_distributions'][param_name]:
            print(f"    {value}: {count}")
    
    print(f"\nVocabulary coverage:")
    cov_stats = stats['vocab_coverage']
    print(f"  Coverage rate: {cov_stats['coverage_rate']:.1%}")
    print(f"  OOV rate: {cov_stats['oov_rate']:.1%}")
    
    return stats


def test_characterization_data_loading(config_manager: ConfigManager, max_examples: int = 100):
    """Test work item characterization data loading."""
    print("Testing SPLADE work item characterization data loading...")
    
    try:
        # Test characterization mode
        train_loader, val_loader, test_loader = create_data_loaders(
            config_manager, 
            training_mode="characterization", 
            max_examples=max_examples,
            include_characterization=True
        )
        
        # Test a batch
        print(f"\nTesting batch loading...")
        batch = next(iter(train_loader))
        print(f"Batch keys: {list(batch.keys())}")
        
        for key, value in batch.items():
            if isinstance(value, torch.Tensor):
                print(f"  {key}: {value.shape} ({value.dtype})")
            elif isinstance(value, list):
                print(f"  {key}: list of {len(value)} items")
                if value and not isinstance(value[0], str):
                    print(f"    First item type: {type(value[0])}")
            else:
                print(f"  {key}: {type(value)}")
        
        # Check for characterization data
        has_concepts = any(key.startswith('concept') for key in batch.keys())
        has_params = any(key.startswith('param_') for key in batch.keys())
        
        print(f"\nCharacterization data found:")
        print(f"  Concepts: {has_concepts}")
        print(f"  Parameters: {has_params}")
        
        if has_concepts:
            concept_labels = batch.get('concept_label', [])
            if isinstance(concept_labels, torch.Tensor):
                unique_concepts = torch.unique(concept_labels).tolist()
                print(f"  Unique concept labels in batch: {unique_concepts}")
        
        print(f"\n✅ Work item characterization data loading test successful!")
        return True
        
    except Exception as e:
        print(f"❌ Data loading test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# Example usage
if __name__ == "__main__":
    # Import config for testing
    from sandbox.splade.training.config import create_construction_optimized_config
    
    # Create test configuration
    config_manager = create_construction_optimized_config(
        experiment_name="characterization_data_test",
        vocab_file_base="OEB"
    )
    
    # Test work item characterization data loading
    success = test_characterization_data_loading(config_manager, max_examples=50)
    
    if success:
        # Analyze work item data characteristics
        stats = analyze_work_item_data(config_manager, max_examples=100)
        
        print(f"\n🎯 Data loader ready for work item characterization training!")
        print(f"📊 Key insights:")
        print(f"  - {stats['work_item_stats']['unique_concepts']} unique work concepts")
        print(f"  - {len(stats['work_item_stats']['parameter_types'])} parameter types")
        print(f"  - {stats['work_item_stats']['characterization_coverage']:.1%} characterization coverage")
        print(f"  - {stats['vocab_coverage']['coverage_rate']:.1%} vocabulary coverage")