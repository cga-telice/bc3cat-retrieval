"""
Word-Level SPLADE Models and Tokenizer Integration

This module provides SPLADE model architecture adapted for word-level tokenization
and integrates with our custom vocabulary system.
"""

import json
import torch
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
from transformers import AutoModel, AutoConfig
from transformers.modeling_outputs import BaseModelOutput

# Import our vocabulary components
from sandbox.splade.core.vocabulary import DualVocabularyBuilder, WordTokenizer, VocabularyBuilder


class WordLevelTokenizer:
    """
    Tokenizer wrapper that integrates our word-level vocabulary 
    with SPLADE model requirements. Compatible with HuggingFace interfaces.
    """
    
    def __init__(self, vocab_builder:VocabularyBuilder, max_length: int = 512):
        """
        Initialize word-level tokenizer.
        
        Args:
            vocab_builder: The vocabulary builder with loaded vocabulary
            max_length: Maximum sequence length
        """
        self.vocab_builder = vocab_builder
        self.word_tokenizer = vocab_builder.tokenizer
        self.max_length = max_length
        
        # Special token IDs
        self.pad_token_id = vocab_builder.special_tokens["[PAD]"]
        self.unk_token_id = vocab_builder.special_tokens["[UNK]"]
        self.cls_token_id = vocab_builder.special_tokens["[CLS]"]
        self.sep_token_id = vocab_builder.special_tokens["[SEP]"]
        self.mask_token_id = vocab_builder.special_tokens["[MASK]"]
        
        # Vocabulary properties
        self.vocab_size = len(vocab_builder.word_to_id)
        self.vocab = vocab_builder.word_to_id
        
    def encode(self, text: str, add_special_tokens: bool = True, 
               max_length: Optional[int] = None, padding: bool = False,
               truncation: bool = True) -> Dict[str, torch.Tensor]:
        """
        Encode text to token IDs with BERT-style formatting.
        
        Args:
            text: Input text to encode
            add_special_tokens: Whether to add [CLS] and [SEP] tokens
            max_length: Maximum sequence length (uses self.max_length if None)
            padding: Whether to pad to max_length
            truncation: Whether to truncate if too long
            
        Returns:
            Dictionary with input_ids, attention_mask, etc.
        """
        if max_length is None:
            max_length = self.max_length
            
        # Tokenize to words
        tokens = self.word_tokenizer.tokenize(text)
        
        # Convert to IDs
        token_ids = [self.vocab_builder.word_to_id.get(token, self.unk_token_id) for token in tokens]
        
        # Add special tokens
        if add_special_tokens:
            token_ids = [self.cls_token_id] + token_ids + [self.sep_token_id]
        
        # Truncate if necessary
        if truncation and len(token_ids) > max_length:
            if add_special_tokens:
                # Keep [CLS] and [SEP]
                token_ids = token_ids[:max_length-1] + [self.sep_token_id]
            else:
                token_ids = token_ids[:max_length]
        
        # Create attention mask
        attention_mask = [1] * len(token_ids)
        
        # Pad if necessary
        if padding and len(token_ids) < max_length:
            padding_length = max_length - len(token_ids)
            token_ids.extend([self.pad_token_id] * padding_length)
            attention_mask.extend([0] * padding_length)
        
        # Ensure we return proper tensors (not scalars)
        return {
            'input_ids': torch.tensor(token_ids, dtype=torch.long),
            'attention_mask': torch.tensor(attention_mask, dtype=torch.long),
            'token_type_ids': torch.zeros(len(token_ids), dtype=torch.long)
        }
    
    def __call__(self, text: Union[str, List[str]], 
                 add_special_tokens: bool = True,
                 max_length: Optional[int] = None,
                 padding: Union[bool, str] = False,
                 truncation: bool = True,
                 return_tensors: str = "pt") -> Dict[str, torch.Tensor]:
        """
        HuggingFace-style tokenizer call interface.
        
        Args:
            text: Input text(s) to tokenize
            add_special_tokens: Whether to add special tokens
            max_length: Maximum sequence length
            padding: Padding strategy ('max_length', True, False)
            truncation: Whether to truncate
            return_tensors: Format of returned tensors ('pt' for PyTorch)
            
        Returns:
            Batch of encoded inputs
        """
        if isinstance(text, str):
            text = [text]
        
        # Determine padding and max_length
        if padding == "max_length" or padding is True:
            do_padding = True
            if max_length is None:
                max_length = self.max_length
        else:
            do_padding = False
            if max_length is None:
                max_length = self.max_length
        
        # Encode all texts
        batch_encoding = []
        for single_text in text:
            encoding = self.encode(
                single_text,
                add_special_tokens=add_special_tokens,
                max_length=max_length,
                padding=do_padding,
                truncation=truncation
            )
            batch_encoding.append(encoding)
        
        # Stack into batch
        if len(batch_encoding) == 1:
            result = {}
            for key, tensor in batch_encoding[0].items():
                if tensor.dim() == 1:
                    # Add batch dimension: [seq_len] -> [1, seq_len]
                    result[key] = tensor.unsqueeze(0)
                elif tensor.dim() == 2:
                    # Already has batch dimension: [1, seq_len]
                    result[key] = tensor
                else:
                    # Remove extra dimensions: [1, 1, seq_len] -> [1, seq_len]
                    result[key] = tensor.view(1, -1)
            return result
        else:
            # Multiple texts - stack properly
            batch = {}
            for key in batch_encoding[0].keys():
                # Ensure all tensors have the same shape
                tensors = []
                for enc in batch_encoding:
                    tensor = enc[key]
                    if tensor.dim() == 1:
                        # Add batch dimension: [seq_len] -> [1, seq_len]
                        tensor = tensor.unsqueeze(0)
                    elif tensor.dim() > 2:
                        # Remove extra dimensions
                        tensor = tensor.view(1, -1)
                    tensors.append(tensor)
                
                # Stack along batch dimension
                batch[key] = torch.cat(tensors, dim=0)
            return batch
    
    def decode(self, token_ids: Union[List[int], torch.Tensor, int], skip_special_tokens: bool = True) -> str:
        """
        Decode token IDs back to text.
        
        Args:
            token_ids: List of token IDs, tensor, or single int to decode
            skip_special_tokens: Whether to skip special tokens
            
        Returns:
            Decoded text string
        """
        # Handle different input types
        if isinstance(token_ids, torch.Tensor):
            if token_ids.dim() == 0:
                # 0-dimensional tensor (scalar)
                token_ids = [token_ids.item()]
            elif token_ids.dim() == 1:
                # 1-dimensional tensor 
                token_ids = token_ids.tolist()
            elif token_ids.dim() > 1:
                # Multi-dimensional tensor, take first sequence
                token_ids = token_ids[0].tolist()
        elif isinstance(token_ids, int):
            # Handle single integer
            token_ids = [token_ids]
        elif not isinstance(token_ids, list):
            # Try to convert to list
            try:
                token_ids = list(token_ids)
            except:
                token_ids = [token_ids]
        
        # Ensure token_ids is a flat list of integers
        if not isinstance(token_ids, list):
            raise TypeError(f"Unable to convert token_ids to list. Got type: {type(token_ids)}")
        
        words = []
        special_token_ids = set(self.vocab_builder.special_tokens.values())
        
        for token_id in token_ids:
            # Ensure token_id is an integer
            if isinstance(token_id, torch.Tensor):
                token_id = token_id.item()
            elif not isinstance(token_id, int):
                try:
                    token_id = int(token_id)
                except (ValueError, TypeError):
                    continue  # Skip invalid token IDs
                    
            if skip_special_tokens and token_id in special_token_ids:
                continue
            word = self.vocab_builder.id_to_word.get(token_id, "[UNK]")
            words.append(word)
        
        return " ".join(words)

class WordSpladeModel(nn.Module):
    """
    SPLADE model adapted for word-level tokenization.
    Uses a base transformer with a word-level vocabulary projection head.
    """
    
    def __init__(self, base_model_name: str, vocab_size: int, 
                 hidden_size: int = 768, dropout: float = 0.1):
        """
        Initialize Word-level SPLADE model.
        
        Args:
            base_model_name: Base transformer model (e.g., Spanish BERT)
            vocab_size: Size of word-level vocabulary
            hidden_size: Hidden size of base model
            dropout: Dropout rate
        """
        super().__init__()
        
        # Load base transformer model (without head)
        self.base_model = AutoModel.from_pretrained(base_model_name)
        self.config = self.base_model.config
        
        # Get actual hidden size from the model
        self.hidden_size = self.base_model.config.hidden_size
        
        # Word-level vocabulary projection head
        self.vocab_projection = nn.Linear(self.hidden_size, vocab_size)
        
        # Dropout for regularization
        self.dropout = nn.Dropout(dropout)
        
        # Store vocabulary size
        self.vocab_size = vocab_size
        
        # Initialize projection layer
        self._init_projection_weights()
    
    def _init_projection_weights(self):
        """Initialize the vocabulary projection layer."""
        nn.init.normal_(self.vocab_projection.weight, mean=0.0, std=0.02)
        nn.init.zeros_(self.vocab_projection.bias)
    
    def forward(self, input_ids: torch.Tensor, 
                attention_mask: Optional[torch.Tensor] = None,
                token_type_ids: Optional[torch.Tensor] = None,
                return_dict: bool = True) -> Union[Dict, Tuple]:
        """
        Forward pass through the model.
        
        Args:
            input_ids: Token IDs [batch_size, seq_len]
            attention_mask: Attention mask [batch_size, seq_len]
            token_type_ids: Token type IDs [batch_size, seq_len]
            return_dict: Whether to return ModelOutput object
            
        Returns:
            SPLADE logits [batch_size, seq_len, vocab_size]
        """
        # Pass through base transformer
        outputs = self.base_model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            return_dict=True
        )
        
        # Get hidden states
        hidden_states = outputs.last_hidden_state  # [batch_size, seq_len, hidden_size]
        
        # Apply dropout
        hidden_states = self.dropout(hidden_states)
        
        # Project to vocabulary space
        logits = self.vocab_projection(hidden_states)  # [batch_size, seq_len, vocab_size]
        
        if return_dict:
            return {
                'logits': logits,
                'hidden_states': outputs.last_hidden_state,
                'attentions': outputs.attentions if hasattr(outputs, 'attentions') else None
            }
        else:
            return (logits,)
    
    def encode_for_splade(self, input_ids: torch.Tensor,
                         attention_mask: torch.Tensor,
                         apply_log: bool = True) -> torch.Tensor:
        """
        Encode inputs for SPLADE sparse representation.
        
        Args:
            input_ids: Token IDs [batch_size, seq_len]  
            attention_mask: Attention mask [batch_size, seq_len]
            apply_log: Whether to apply log(1 + x) transformation
            
        Returns:
            Sparse document vectors [batch_size, vocab_size]
        """
        # Forward pass
        outputs = self.forward(input_ids, attention_mask, return_dict=True)
        logits = outputs['logits']  # [batch_size, seq_len, vocab_size]
        
        # Apply ReLU activation
        activated = torch.relu(logits)
        
        # Sum over sequence dimension (aggregate word contributions)
        # Mask out padding tokens
        if attention_mask is not None:
            mask = attention_mask.unsqueeze(-1).expand_as(activated)
            activated = activated * mask
        
        doc_vector = torch.sum(activated, dim=1)  # [batch_size, vocab_size]
        
        # Apply log transformation (standard in SPLADE)
        if apply_log:
            doc_vector = torch.log1p(doc_vector)
        
        return doc_vector
    
    def save_pretrained(self, save_path: Path):
        """Save model and configuration."""
        save_path.mkdir(parents=True, exist_ok=True)
        
        # Save model state
        torch.save(self.state_dict(), save_path / "pytorch_model.bin")
        
        # Save configuration
        config = {
            "model_type": "word_splade",
            "base_model_name": getattr(self, '_base_model_name', 'unknown'),
            "vocab_size": self.vocab_size,
            "hidden_size": self.hidden_size,
            "dropout": 0.1,  # Default value
        }
        
        with open(save_path / "config.json", "w") as f:
            json.dump(config, f, indent=2)
        
        print(f"Model saved to {save_path}")
    
    @classmethod
    def from_pretrained(cls, model_path: Path, vocab_size: int):
        """Load model from saved checkpoint."""
        # Load configuration
        with open(model_path / "config.json", "r") as f:
            config = json.load(f)
        
        # Create model
        model = cls(
            base_model_name=config["base_model_name"],
            vocab_size=vocab_size,
            hidden_size=config.get("hidden_size", 768),
            dropout=config.get("dropout", 0.1)
        )
        
        # Load state dict
        state_dict = torch.load(model_path / "pytorch_model.bin", map_location="cpu")
        model.load_state_dict(state_dict)
        
        print(f"Model loaded from {model_path}")
        return model


class WordSpladeEncoder:
    """
    High-level encoder that combines tokenizer and model for easy use.
    Similar interface to the original SparseEncoder but for word-level.
    """
    
    def __init__(self, model: WordSpladeModel, tokenizer: WordLevelTokenizer, 
                 device: str = None):
        """
        Initialize Word SPLADE encoder.
        
        Args:
            model: The Word SPLADE model
            tokenizer: The word-level tokenizer
            device: Device to run on
        """
        self.model = model
        self.tokenizer = tokenizer
        self.device = torch.device(device if device else ('cuda' if torch.cuda.is_available() else 'cpu'))
        
        # Move model to device
        self.model.to(self.device)
        self.model.eval()
        
        print(f"WordSpladeEncoder initialized on {self.device}")
        print(f"Vocabulary size: {self.tokenizer.vocab_size}")
    
    def encode(self, texts: Union[str, List[str]], 
               batch_size: int = 8, max_length: int = 512,
               apply_sparsity: bool = True) -> torch.Tensor:
        """
        Encode texts to sparse SPLADE representations.
        
        Args:
            texts: Input text(s) to encode
            batch_size: Batch size for processing
            max_length: Maximum sequence length
            apply_sparsity: Whether to apply sparsity controls
            
        Returns:
            Sparse tensor [num_texts, vocab_size]
        """
        if isinstance(texts, str):
            texts = [texts]
        
        all_vectors = []
        
        with torch.no_grad():
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                
                # Tokenize batch
                inputs = self.tokenizer(
                    batch_texts,
                    max_length=max_length,
                    padding="max_length",
                    truncation=True,
                    return_tensors="pt"
                )
                
                # Verify and fix tensor shapes
                batch_size_actual = len(batch_texts)
                for key, tensor in inputs.items():
                    expected_shape = (batch_size_actual, max_length)
                    if tensor.shape != expected_shape:
                        print(f"⚠️  Reshaping {key} from {tensor.shape} to {expected_shape}")
                        # Ensure proper shape [batch_size, seq_len]
                        tensor = tensor.view(batch_size_actual, -1)
                        if tensor.shape[1] != max_length:
                            # Pad or truncate to max_length
                            if tensor.shape[1] < max_length:
                                pad_size = max_length - tensor.shape[1]
                                if key in ['input_ids', 'attention_mask']:
                                    pad_value = self.tokenizer.pad_token_id if key == 'input_ids' else 0
                                else:
                                    pad_value = 0
                                padding = torch.full((batch_size_actual, pad_size), pad_value, dtype=tensor.dtype)
                                tensor = torch.cat([tensor, padding], dim=1)
                            else:
                                tensor = tensor[:, :max_length]
                        inputs[key] = tensor
                
                # Move to device
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                # Encode
                batch_vectors = self.model.encode_for_splade(
                    inputs['input_ids'],
                    inputs['attention_mask'],
                    apply_log=True
                )
                
                all_vectors.append(batch_vectors.cpu())
        
        # Concatenate all batches
        if all_vectors:
            return torch.cat(all_vectors, dim=0)
        else:
            return torch.zeros(0, self.tokenizer.vocab_size)

def create_word_splade_system(vocab_path: Path, 
                             base_model_name: str = "dccuchile/bert-base-spanish-wwm-cased",
                             device: str = None,
                             use_filtered: bool = False) -> Tuple[WordSpladeModel, WordLevelTokenizer, WordSpladeEncoder]:
    """
    Convenience function to create a complete word-level SPLADE system.
    Perfect for Jupyter notebook usage.
    
    Args:
        vocab_path: Path to vocabulary directory
        base_model_name: Base transformer model to use
        device: Device to run on
        
    Returns:
        Tuple of (model, tokenizer, encoder)
    """
    print("🔧 Creating Word-Level SPLADE System...")
    
    # Load vocabulary
    print("📚 Loading vocabulary...")
    vocab_builder = VocabularyBuilder.load_vocabulary(vocab_path)
    
    # Create tokenizer
    print("🔤 Creating tokenizer...")
    tokenizer = WordLevelTokenizer(vocab_builder, max_length=512)
    
    # Create model
    print("🧠 Creating model...")
    model = WordSpladeModel(
        base_model_name=base_model_name,
        vocab_size=tokenizer.vocab_size,
        hidden_size=768  # Will be auto-detected from base model
    )
    
    # Create encoder
    print("⚡ Creating encoder...")
    encoder = WordSpladeEncoder(model, tokenizer, device)
    
    print("✅ Word-Level SPLADE system ready!")
    print(f"📊 Vocabulary size: {tokenizer.vocab_size:,}")
    print(f"🖥️  Device: {encoder.device}")
    
    return model, tokenizer, encoder


# Jupyter-friendly testing functions
def test_tokenization(tokenizer: WordLevelTokenizer, test_texts: List[str] = None):
    """
    Test tokenization with sample texts. Great for Jupyter notebooks.
    
    Args:
        tokenizer: The word-level tokenizer to test
        test_texts: Optional custom test texts
    """
    if test_texts is None:
        test_texts = [
            "El electrocardiograma muestra alteraciones.",
            "COVID-19 es una enfermedad respiratoria.",
            "La resonancia magnética nuclear detectó lesiones.",
            "Administrar 5mg de medicamento anti-inflamatorio."
        ]
    
    print("🧪 Testing Word-Level Tokenization")
    print("="*50)
    
    for text in test_texts:
        # Tokenize
        tokens = tokenizer.word_tokenizer.tokenize(text)
        
        # Encode
        encoding = tokenizer.encode(text, add_special_tokens=True, padding=True)
        
        # Decode
        decoded = tokenizer.decode(encoding['input_ids'].tolist(), skip_special_tokens=True)
        
        print(f"\n📝 Original: {text}")
        print(f"🔤 Tokens:   {tokens}")
        print(f"🔢 IDs:      {encoding['input_ids'].tolist()}")
        print(f"🔄 Decoded:  {decoded}")


def test_model_forward(model: WordSpladeModel, tokenizer: WordLevelTokenizer, 
                      test_text: str = "El paciente presenta síntomas de COVID-19."):
    """
    Test model forward pass. Great for Jupyter notebooks.
    
    Args:
        model: The Word SPLADE model
        tokenizer: The word-level tokenizer
        test_text: Text to test with
    """
    print("🧪 Testing Model Forward Pass")
    print("="*50)
    
    # Get model device
    device = next(model.parameters()).device
    print(f"🖥️  Model device: {device}")
    
    # Encode text
    inputs = tokenizer(test_text, return_tensors="pt", padding=True, truncation=True)
    
    # Move inputs to the same device as the model
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    print(f"📝 Input text: {test_text}")
    print(f"📊 Input shape: {inputs['input_ids'].shape}")
    print(f"🖥️  Input device: {inputs['input_ids'].device}")
    
    # Forward pass
    with torch.no_grad():
        outputs = model.forward(**inputs, return_dict=True)
        sparse_repr = model.encode_for_splade(inputs['input_ids'], inputs['attention_mask'])
    
    print(f"🔢 Logits shape: {outputs['logits'].shape}")
    print(f"⚡ Sparse repr shape: {sparse_repr.shape}")
    print(f"🎯 Non-zero elements: {torch.sum(sparse_repr > 0).item()}")
    print(f"📈 Max value: {torch.max(sparse_repr).item():.4f}")
    
    # Show top activated words
    if sparse_repr.shape[0] == 1:  # Single example
        top_indices = torch.topk(sparse_repr[0], k=10).indices
        top_words = [tokenizer.vocab_builder.id_to_word.get(idx.item(), "[UNK]") for idx in top_indices]
        top_values = torch.topk(sparse_repr[0], k=10).values
        
        print(f"\n🔥 Top activated words:")
        for word, value in zip(top_words, top_values):
            print(f"   {word}: {value.item():.4f}")


# Fix 2: Update the WordSpladeEncoder.encode method to handle device properly
def fixed_encode(self, texts: Union[str, List[str]], 
               batch_size: int = 8, max_length: int = 512,
               apply_sparsity: bool = True) -> torch.Tensor:
    """
    Encode texts to sparse SPLADE representations.
    
    Args:
        texts: Input text(s) to encode
        batch_size: Batch size for processing
        max_length: Maximum sequence length
        apply_sparsity: Whether to apply sparsity controls
        
    Returns:
        Sparse tensor [num_texts, vocab_size]
    """
    if isinstance(texts, str):
        texts = [texts]
    
    all_vectors = []
    
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            # Tokenize batch
            inputs = self.tokenizer(
                batch_texts,
                max_length=max_length,
                padding="max_length",
                truncation=True,
                return_tensors="pt"
            )
            
            # Move to device - this is the key fix
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Encode
            batch_vectors = self.model.encode_for_splade(
                inputs['input_ids'],
                inputs['attention_mask'],
                apply_log=True
            )
            
            all_vectors.append(batch_vectors.cpu())
    
    # Concatenate all batches
    if all_vectors:
        return torch.cat(all_vectors, dim=0)
    else:
        return torch.zeros(0, self.tokenizer.vocab_size)

def create_dual_word_splade_system(vocab_base_path: Path, file_base: str,
                                  base_model_name: str = "dccuchile/bert-base-spanish-wwm-cased",
                                  device: str = None, 
                                  use_filtered: bool = False) -> Tuple[WordSpladeModel, WordLevelTokenizer, WordSpladeEncoder]:
    """
    Create SPLADE system using dual vocabulary builder outputs.
    
    Args:
        vocab_base_path: Base path where vocabularies are saved
        file_base: Base filename used when saving vocabularies
        base_model_name: Base transformer model to use
        device: Device to run on
        use_filtered: Whether to use filtered vocabulary (without stopwords)
        
    Returns:
        Tuple of (model, tokenizer, encoder)
    """
    # Determine which vocabulary to load
    vocab_suffix = "filtered" if use_filtered else "full"
    vocab_path = vocab_base_path / f"{file_base}_vocab_{vocab_suffix}_50000"
    
    print(f"📁 Loading {'filtered' if use_filtered else 'full'} vocabulary from: {vocab_path}")
    
    return create_word_splade_system(vocab_path, base_model_name, device)