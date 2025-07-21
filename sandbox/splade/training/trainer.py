"""
SPLADE Word-Level Trainer with Work Item Characterization

This module provides comprehensive training functionality for word-level SPLADE models
with work item characterization capabilities. It handles both similarity learning
and structured prediction tasks.
"""

import os
import json
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW, Adam, SGD
from torch.optim.lr_scheduler import LinearLR, CosineAnnealingLR, ConstantLR
from torch.utils.data import DataLoader
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, asdict
import numpy as np
from tqdm.auto import tqdm
import logging
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns

# Import our components
from sandbox.splade.core.models import WordSpladeModel, WordLevelTokenizer
from sandbox.splade.training.config import ExperimentConfig, ConfigManager
from sandbox.splade.training.data_loader import SpladeDataLoader, TrainingExample


@dataclass
class TrainingMetrics:
    """Training metrics tracking."""
    epoch: int
    step: int
    loss: float
    splade_loss: float = 0.0
    concept_loss: float = 0.0
    parameter_losses: Dict[str, float] = None
    sparsity_loss: float = 0.0
    learning_rate: float = 0.0
    
    # Evaluation metrics
    concept_accuracy: float = 0.0
    parameter_accuracies: Dict[str, float] = None
    retrieval_metrics: Dict[str, float] = None
    
    def __post_init__(self):
        if self.parameter_losses is None:
            self.parameter_losses = {}
        if self.parameter_accuracies is None:
            self.parameter_accuracies = {}
        if self.retrieval_metrics is None:
            self.retrieval_metrics = {}


class WorkItemSpladeModel(WordSpladeModel):
    """Extended SPLADE model with work item characterization capabilities."""
    
    def __init__(self, 
                 base_model_name: str, 
                 vocab_size: int,
                 num_concepts: int = 0,
                 parameter_vocabs: Dict[str, int] = None,
                 hidden_size: int = 768, 
                 dropout: float = 0.1):
        """
        Initialize Work Item SPLADE model.
        
        Args:
            base_model_name: Base transformer model
            vocab_size: SPLADE vocabulary size
            num_concepts: Number of work item concepts
            parameter_vocabs: Parameter vocabulary sizes {param_name: vocab_size}
            hidden_size: Hidden size
            dropout: Dropout rate
        """
        super().__init__(base_model_name, vocab_size, hidden_size, dropout)
        
        self.num_concepts = num_concepts
        self.parameter_vocabs = parameter_vocabs or {}
        
        # Classification heads for work item characterization
        if num_concepts > 0:
            self.concept_classifier = nn.Sequential(
                nn.Dropout(dropout),
                nn.Linear(vocab_size, hidden_size // 2),
                nn.ReLU(),
                nn.Dropout(dropout / 2),
                nn.Linear(hidden_size // 2, num_concepts)
            )
        
        # Parameter prediction heads
        self.parameter_classifiers = nn.ModuleDict()
        for param_name, param_vocab_size in self.parameter_vocabs.items():
            self.parameter_classifiers[param_name] = nn.Sequential(
                nn.Dropout(dropout),
                nn.Linear(vocab_size, hidden_size // 2),
                nn.ReLU(),
                nn.Dropout(dropout / 2),
                nn.Linear(hidden_size // 2, param_vocab_size)
            )
        
        print(f"WorkItemSpladeModel initialized:")
        print(f"  SPLADE vocab size: {vocab_size}")
        print(f"  Concepts: {num_concepts}")
        print(f"  Parameters: {list(self.parameter_vocabs.keys())}")
    
    def forward_characterization(self, 
                               input_ids: torch.Tensor,
                               attention_mask: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Forward pass for work item characterization.
        
        Args:
            input_ids: Token IDs [batch_size, seq_len]
            attention_mask: Attention mask [batch_size, seq_len]
            
        Returns:
            Dictionary with SPLADE representation and classification logits
        """
        # Get SPLADE representation
        sparse_repr = self.encode_for_splade(input_ids, attention_mask, apply_log=True)
        
        results = {'sparse_representation': sparse_repr}
        
        # Concept classification
        if hasattr(self, 'concept_classifier'):
            concept_logits = self.concept_classifier(sparse_repr)
            results['concept_logits'] = concept_logits
        
        # Parameter predictions
        for param_name, classifier in self.parameter_classifiers.items():
            param_logits = classifier(sparse_repr)
            results[f'param_{param_name}_logits'] = param_logits
        
        return results


class SpladeTrainer:
    """Comprehensive trainer for SPLADE with work item characterization."""
    
    def __init__(self, 
                 config_manager: ConfigManager,
                 model: WorkItemSpladeModel,
                 tokenizer: WordLevelTokenizer,
                 train_loader: DataLoader,
                 val_loader: DataLoader,
                 test_loader: Optional[DataLoader] = None):
        """
        Initialize SPLADE trainer.
        
        Args:
            config_manager: Configuration manager
            model: Work item SPLADE model
            tokenizer: Word-level tokenizer
            train_loader: Training data loader
            val_loader: Validation data loader
            test_loader: Test data loader (optional)
        """
        self.config = config_manager.config
        self.model = model
        self.tokenizer = tokenizer
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.test_loader = test_loader
        
        # Setup device
        self.device = torch.device(self.config.hardware.device)
        self.model.to(self.device)
        
        # Setup optimizer and scheduler
        self._setup_optimizer()
        self._setup_scheduler()
        
        # Setup logging
        self._setup_logging()
        
        # Training state
        self.current_epoch = 0
        self.global_step = 0
        self.best_val_loss = float('inf')
        self.best_concept_accuracy = 0.0
        self.training_history = []
        self.early_stopping_counter = 0
        
        # Loss weights for multi-task learning
        self.loss_weights = {
            'splade': 1.0,
            'sparsity': self.config.model.lambda_d,
            'concept': 1.0,
            'parameters': 0.5,  # Lower weight for parameters
        }
        
        print(f"SpladeTrainer initialized:")
        print(f"  Device: {self.device}")
        print(f"  Training examples: {len(train_loader.dataset)}")
        print(f"  Validation examples: {len(val_loader.dataset)}")
        print(f"  Loss weights: {self.loss_weights}")
    
    def _setup_optimizer(self):
        """Setup optimizer based on configuration."""
        # Get model parameters
        params = self.model.parameters()
        
        if self.config.training.optimizer.lower() == 'adamw':
            self.optimizer = AdamW(
                params,
                lr=self.config.training.learning_rate,
                weight_decay=self.config.training.weight_decay,
                eps=self.config.training.eps,
                betas=self.config.training.betas
            )
        elif self.config.training.optimizer.lower() == 'adam':
            self.optimizer = Adam(
                params,
                lr=self.config.training.learning_rate,
                weight_decay=self.config.training.weight_decay,
                eps=self.config.training.eps,
                betas=self.config.training.betas
            )
        elif self.config.training.optimizer.lower() == 'sgd':
            self.optimizer = SGD(
                params,
                lr=self.config.training.learning_rate,
                weight_decay=self.config.training.weight_decay,
                momentum=0.9
            )
        else:
            raise ValueError(f"Unknown optimizer: {self.config.training.optimizer}")
        
        print(f"Optimizer: {self.config.training.optimizer}")
        print(f"Learning rate: {self.config.training.learning_rate}")
    
    def _setup_scheduler(self):
        """Setup learning rate scheduler."""
        total_steps = len(self.train_loader) * self.config.training.num_epochs
        warmup_steps = int(total_steps * self.config.training.warmup_ratio)
        
        if self.config.training.scheduler.lower() == 'linear':
            self.scheduler = LinearLR(
                self.optimizer,
                start_factor=0.1,
                total_iters=warmup_steps
            )
        elif self.config.training.scheduler.lower() == 'cosine':
            self.scheduler = CosineAnnealingLR(
                self.optimizer,
                T_max=total_steps - warmup_steps
            )
        elif self.config.training.scheduler.lower() == 'constant':
            self.scheduler = ConstantLR(self.optimizer, factor=1.0)
        else:
            self.scheduler = None
        
        print(f"Scheduler: {self.config.training.scheduler}")
        print(f"Total steps: {total_steps}, Warmup steps: {warmup_steps}")
    
    def _setup_logging(self):
        """Setup logging configuration."""
        # Create logging directory
        log_dir = Path(self.config.logging.logging_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logger
        logging.basicConfig(
            level=getattr(logging, self.config.logging.logging_level),
            format=self.config.logging.log_format,
            handlers=[
                logging.FileHandler(log_dir / "training.log"),
                logging.StreamHandler() if self.config.logging.console_logging else logging.NullHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Training started: {datetime.now()}")
        self.logger.info(f"Configuration: {self.config.experiment_name}")
    
    def compute_splade_loss(self, 
                          doc_sparse: torch.Tensor, 
                          query_sparse: torch.Tensor,
                          labels: torch.Tensor = None) -> torch.Tensor:
        """
        Compute SPLADE similarity loss.
        
        Args:
            doc_sparse: Document sparse representations [batch_size, vocab_size]
            query_sparse: Query sparse representations [batch_size, vocab_size]
            labels: Labels for the pairs (optional)
            
        Returns:
            SPLADE similarity loss
        """
        # Compute similarities
        similarities = torch.sum(doc_sparse * query_sparse, dim=1)  # [batch_size]
        
        if self.config.training.loss_type == "ranking":
            # Ranking loss with margin
            # For simplicity, use all as positive pairs (could add negatives)
            target_scores = torch.ones_like(similarities)
            loss = F.margin_ranking_loss(
                similarities, 
                similarities,  # This needs proper negative sampling
                target_scores,
                margin=self.config.training.margin
            )
        
        elif self.config.training.loss_type == "contrastive":
            # Contrastive loss
            target_similarities = torch.ones_like(similarities)  # All positive pairs
            loss = F.mse_loss(similarities, target_similarities)
        
        else:
            # Simple MSE with target similarity of 1.0
            target_similarities = torch.ones_like(similarities)
            loss = F.mse_loss(similarities, target_similarities)
        
        return loss
    
    def compute_sparsity_loss(self, sparse_repr: torch.Tensor) -> torch.Tensor:
        """
        Compute sparsity regularization loss (FLOPS loss).
        
        Args:
            sparse_repr: Sparse representation [batch_size, vocab_size]
            
        Returns:
            Sparsity loss
        """
        if self.config.model.sparsity_regularizer == "flops":
            # FLOPS loss: L1 norm of the sparse representation
            return torch.mean(torch.sum(torch.abs(sparse_repr), dim=1))
        
        elif self.config.model.sparsity_regularizer == "l1":
            # Simple L1 regularization
            return torch.mean(torch.sum(sparse_repr, dim=1))
        
        else:
            return torch.tensor(0.0, device=sparse_repr.device)
    
    def compute_characterization_losses(self, 
                                      predictions: Dict[str, torch.Tensor],
                                      batch: Dict[str, Any]) -> Dict[str, torch.Tensor]:
        """
        Compute work item characterization losses.
        
        Args:
            predictions: Model predictions
            batch: Batch data with labels
            
        Returns:
            Dictionary of characterization losses
        """
        losses = {}
        
        # Concept classification loss
        if 'concept_logits' in predictions and 'concept_label' in batch:
            concept_logits = predictions['concept_logits']
            concept_labels = batch['concept_label'].to(self.device)
            losses['concept'] = F.cross_entropy(concept_logits, concept_labels)
        
        # Parameter prediction losses
        parameter_losses = {}
        for param_name in self.model.parameter_vocabs.keys():
            logits_key = f'param_{param_name}_logits'
            label_key = f'param_{param_name}'
            
            if logits_key in predictions and label_key in batch:
                param_logits = predictions[logits_key]
                param_labels = batch[label_key].to(self.device)
                parameter_losses[param_name] = F.cross_entropy(param_logits, param_labels)
        
        if parameter_losses:
            losses['parameters'] = parameter_losses
        
        return losses
    
    def compute_total_loss(self, 
                          doc_sparse: torch.Tensor,
                          query_sparse: torch.Tensor,
                          characterization_predictions: Dict[str, torch.Tensor],
                          batch: Dict[str, Any]) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute total multi-task loss.
        
        Args:
            doc_sparse: Document sparse representations
            query_sparse: Query sparse representations  
            characterization_predictions: Characterization predictions
            batch: Batch data
            
        Returns:
            Total loss and loss components
        """
        loss_components = {}
        
        # SPLADE similarity loss
        if query_sparse is not None:
            splade_loss = self.compute_splade_loss(doc_sparse, query_sparse)
            loss_components['splade'] = splade_loss.item()
        else:
            splade_loss = torch.tensor(0.0, device=doc_sparse.device)
            loss_components['splade'] = 0.0
        
        # Sparsity loss
        sparsity_loss = self.compute_sparsity_loss(doc_sparse)
        if query_sparse is not None:
            sparsity_loss += self.compute_sparsity_loss(query_sparse)
        loss_components['sparsity'] = sparsity_loss.item()
        
        # Characterization losses
        char_losses = self.compute_characterization_losses(characterization_predictions, batch)
        
        concept_loss = torch.tensor(0.0, device=doc_sparse.device)
        if 'concept' in char_losses:
            concept_loss = char_losses['concept']
            loss_components['concept'] = concept_loss.item()
        
        parameter_loss = torch.tensor(0.0, device=doc_sparse.device)
        if 'parameters' in char_losses:
            param_losses = char_losses['parameters']
            parameter_loss = torch.mean(torch.stack(list(param_losses.values())))
            loss_components['parameters'] = parameter_loss.item()
            # Add individual parameter losses
            for param_name, param_loss in param_losses.items():
                loss_components[f'param_{param_name}'] = param_loss.item()
        
        # Combine all losses
        total_loss = (
            self.loss_weights['splade'] * splade_loss +
            self.loss_weights['sparsity'] * sparsity_loss +
            self.loss_weights['concept'] * concept_loss +
            self.loss_weights['parameters'] * parameter_loss
        )
        
        loss_components['total'] = total_loss.item()
        
        return total_loss, loss_components
    
    def train_epoch(self) -> Dict[str, float]:
        """Train one epoch."""
        self.model.train()
        epoch_losses = {}
        epoch_metrics = {}
        
        progress_bar = tqdm(self.train_loader, desc=f"Epoch {self.current_epoch}")
        
        for batch_idx, batch in enumerate(progress_bar):
            # Move batch to device
            for key, value in batch.items():
                if isinstance(value, torch.Tensor):
                    batch[key] = value.to(self.device)
            
            # Forward pass
            self.optimizer.zero_grad()
            
            # Get document representations
            doc_results = self.model.forward_characterization(
                batch['input_ids'], 
                batch['attention_mask']
            )
            doc_sparse = doc_results['sparse_representation']
            
            # Get query representations if available
            query_sparse = None
            if 'query_input_ids' in batch:
                query_results = self.model.forward_characterization(
                    batch['query_input_ids'],
                    batch['query_attention_mask']
                )
                query_sparse = query_results['sparse_representation']
            
            # Compute loss
            total_loss, loss_components = self.compute_total_loss(
                doc_sparse, query_sparse, doc_results, batch
            )
            
            # Backward pass
            total_loss.backward()
            
            # Gradient clipping
            if self.config.training.max_grad_norm > 0:
                torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(), 
                    self.config.training.max_grad_norm
                )
            
            # Optimizer step
            if (batch_idx + 1) % self.config.training.gradient_accumulation_steps == 0:
                self.optimizer.step()
                if self.scheduler:
                    self.scheduler.step()
                self.global_step += 1
            
            # Update metrics
            for key, value in loss_components.items():
                if key not in epoch_losses:
                    epoch_losses[key] = []
                epoch_losses[key].append(value)
            
            # Update progress bar
            current_lr = self.optimizer.param_groups[0]['lr']
            progress_bar.set_postfix({
                'loss': f"{total_loss.item():.4f}",
                'splade': f"{loss_components.get('splade', 0):.4f}",
                'concept': f"{loss_components.get('concept', 0):.4f}",
                'lr': f"{current_lr:.2e}"
            })
            
            # Log periodically
            if self.global_step % self.config.logging.log_every_n_steps == 0:
                self.logger.info(
                    f"Step {self.global_step}: Loss={total_loss.item():.4f}, "
                    f"SPLADE={loss_components.get('splade', 0):.4f}, "
                    f"Concept={loss_components.get('concept', 0):.4f}, "
                    f"LR={current_lr:.2e}"
                )
        
        # Compute epoch averages
        epoch_metrics = {key: np.mean(values) for key, values in epoch_losses.items()}
        epoch_metrics['learning_rate'] = self.optimizer.param_groups[0]['lr']
        
        return epoch_metrics
    
    def evaluate(self, data_loader: DataLoader, dataset_name: str = "validation") -> Dict[str, float]:
        """Evaluate model on dataset."""
        self.model.eval()
        eval_losses = {}
        eval_metrics = {}
        
        # For accuracy computation
        concept_correct = 0
        concept_total = 0
        param_correct = {param: 0 for param in self.model.parameter_vocabs.keys()}
        param_total = {param: 0 for param in self.model.parameter_vocabs.keys()}
        
        with torch.no_grad():
            for batch in tqdm(data_loader, desc=f"Evaluating {dataset_name}"):
                # Move batch to device
                for key, value in batch.items():
                    if isinstance(value, torch.Tensor):
                        batch[key] = value.to(self.device)
                
                # Forward pass
                doc_results = self.model.forward_characterization(
                    batch['input_ids'], 
                    batch['attention_mask']
                )
                doc_sparse = doc_results['sparse_representation']
                
                # Get query representations if available
                query_sparse = None
                if 'query_input_ids' in batch:
                    query_results = self.model.forward_characterization(
                        batch['query_input_ids'],
                        batch['query_attention_mask']
                    )
                    query_sparse = query_results['sparse_representation']
                
                # Compute losses
                total_loss, loss_components = self.compute_total_loss(
                    doc_sparse, query_sparse, doc_results, batch
                )
                
                # Update loss metrics
                for key, value in loss_components.items():
                    if key not in eval_losses:
                        eval_losses[key] = []
                    eval_losses[key].append(value)
                
                # Compute accuracies
                if 'concept_logits' in doc_results and 'concept_label' in batch:
                    concept_preds = torch.argmax(doc_results['concept_logits'], dim=1)
                    concept_labels = batch['concept_label']
                    concept_correct += (concept_preds == concept_labels).sum().item()
                    concept_total += concept_labels.size(0)
                
                # Parameter accuracies
                for param_name in self.model.parameter_vocabs.keys():
                    logits_key = f'param_{param_name}_logits'
                    label_key = f'param_{param_name}'
                    
                    if logits_key in doc_results and label_key in batch:
                        param_preds = torch.argmax(doc_results[logits_key], dim=1)
                        param_labels = batch[label_key]
                        param_correct[param_name] += (param_preds == param_labels).sum().item()
                        param_total[param_name] += param_labels.size(0)
        
        # Compute final metrics
        eval_metrics = {key: np.mean(values) for key, values in eval_losses.items()}
        
        # Add accuracies
        if concept_total > 0:
            eval_metrics['concept_accuracy'] = concept_correct / concept_total
        
        for param_name in self.model.parameter_vocabs.keys():
            if param_total[param_name] > 0:
                eval_metrics[f'param_{param_name}_accuracy'] = param_correct[param_name] / param_total[param_name]
        
        return eval_metrics
    
    def save_checkpoint(self, epoch: int, metrics: Dict[str, float], is_best: bool = False):
        """Save model checkpoint."""
        checkpoint = {
            'epoch': epoch,
            'global_step': self.global_step,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict() if self.scheduler else None,
            'metrics': metrics,
            'config': asdict(self.config),
            'training_history': self.training_history,
        }
        
        # Save regular checkpoint
        checkpoint_dir = Path(self.config.logging.output_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        checkpoint_path = checkpoint_dir / f"checkpoint_epoch_{epoch}.pt"
        torch.save(checkpoint, checkpoint_path)
        
        # Save best model
        if is_best:
            best_path = checkpoint_dir / "best_model.pt"
            torch.save(checkpoint, best_path)
            self.logger.info(f"New best model saved at epoch {epoch}")
        
        self.logger.info(f"Checkpoint saved: {checkpoint_path}")
    
    def train(self) -> Dict[str, List[float]]:
        """Run complete training loop."""
        self.logger.info("Starting training...")
        self.logger.info(f"Training for {self.config.training.num_epochs} epochs")
        
        for epoch in range(self.config.training.num_epochs):
            self.current_epoch = epoch
            
            # Train epoch
            train_metrics = self.train_epoch()
            
            # Evaluate
            val_metrics = self.evaluate(self.val_loader, "validation")
            
            # Create epoch summary
            epoch_summary = TrainingMetrics(
                epoch=epoch,
                step=self.global_step,
                loss=train_metrics['total'],
                splade_loss=train_metrics.get('splade', 0),
                concept_loss=train_metrics.get('concept', 0),
                parameter_losses={k: v for k, v in train_metrics.items() if k.startswith('param_')},
                sparsity_loss=train_metrics.get('sparsity', 0),
                learning_rate=train_metrics['learning_rate'],
                concept_accuracy=val_metrics.get('concept_accuracy', 0),
                parameter_accuracies={k: v for k, v in val_metrics.items() if k.endswith('_accuracy')},
            )
            
            self.training_history.append(epoch_summary)
            
            # Logging
            self.logger.info(f"Epoch {epoch} Summary:")
            self.logger.info(f"  Train Loss: {train_metrics['total']:.4f}")
            self.logger.info(f"  Val Loss: {val_metrics['total']:.4f}")
            self.logger.info(f"  Concept Accuracy: {val_metrics.get('concept_accuracy', 0):.3f}")
            
            # Check for best model
            is_best = False
            if val_metrics['total'] < self.best_val_loss:
                self.best_val_loss = val_metrics['total']
                is_best = True
                self.early_stopping_counter = 0
            else:
                self.early_stopping_counter += 1
            
            if val_metrics.get('concept_accuracy', 0) > self.best_concept_accuracy:
                self.best_concept_accuracy = val_metrics.get('concept_accuracy', 0)
            
            # Save checkpoint
            if epoch % self.config.training.save_steps == 0 or is_best:
                self.save_checkpoint(epoch, val_metrics, is_best)
            
            # Early stopping
            if (self.config.training.early_stopping and 
                self.early_stopping_counter >= self.config.training.early_stopping_patience):
                self.logger.info(f"Early stopping at epoch {epoch}")
                break
        
        # Final evaluation on test set
        if self.test_loader:
            test_metrics = self.evaluate(self.test_loader, "test")
            self.logger.info("Final Test Results:")
            for key, value in test_metrics.items():
                self.logger.info(f"  {key}: {value:.4f}")
        
        self.logger.info("Training completed!")
        
        # Return training history
        history = {
            'train_loss': [m.loss for m in self.training_history],
            'splade_loss': [m.splade_loss for m in self.training_history],
            'concept_loss': [m.concept_loss for m in self.training_history],
            'concept_accuracy': [m.concept_accuracy for m in self.training_history],
            'learning_rate': [m.learning_rate for m in self.training_history],
        }
        
        return history


# Convenience functions for easy usage
def create_trainer(config_manager: ConfigManager,
                  training_mode: str = "characterization",
                  max_examples: Optional[int] = None) -> SpladeTrainer:
    """
    Create a complete SPLADE trainer with work item characterization.
    
    Args:
        config_manager: Configuration manager
        training_mode: Training mode
        max_examples: Limit examples for testing
        
    Returns:
        Configured SPLADE trainer
    """
    print("Creating SPLADE trainer with work item characterization...")
    
    # Create data loader
    data_loader = SpladeDataLoader(config_manager)
    train_loader, val_loader, test_loader = data_loader.create_train_val_test_loaders(
        training_mode=training_mode,
        max_examples=max_examples,
        include_characterization=True
    )
    
    # Get vocabularies for characterization
    num_concepts = len(data_loader.processor.concept_vocab)
    parameter_vocabs = {
        param: len(vocab) 
        for param, vocab in data_loader.processor.parameter_vocabs.items()
    }
    
    # Create model
    model = WorkItemSpladeModel(
        base_model_name=config_manager.config.model.base_model_name,
        vocab_size=data_loader.tokenizer.vocab_size,
        num_concepts=num_concepts,
        parameter_vocabs=parameter_vocabs,
        hidden_size=config_manager.config.model.hidden_size,
        dropout=config_manager.config.model.dropout
    )
    
    # Create trainer
    trainer = SpladeTrainer(
        config_manager=config_manager,
        model=model,
        tokenizer=data_loader.tokenizer,
        train_loader=train_loader,
        val_loader=val_loader,
        test_loader=test_loader
    )
    
    print("✅ SPLADE trainer created successfully!")
    return trainer


def plot_training_history(history: Dict[str, List[float]], save_path: Optional[str] = None):
    """Plot training history."""
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # Loss curves
    axes[0, 0].plot(history['train_loss'], label='Total Loss', color='blue')
    axes[0, 0].plot(history['splade_loss'], label='SPLADE Loss', color='orange')
    axes[0, 0].plot(history['concept_loss'], label='Concept Loss', color='green')
    axes[0, 0].set_title('Training Losses')
    axes[0, 0].set_xlabel('Epoch')
    axes[0, 0].set_ylabel('Loss')
    axes[0, 0].legend()
    axes[0, 0].grid(True)
    
    # Accuracy curves
    axes[0, 1].plot(history['concept_accuracy'], label='Concept Accuracy', color='red')
    axes[0, 1].set_title('Validation Accuracy')
    axes[0, 1].set_xlabel('Epoch')
    axes[0, 1].set_ylabel('Accuracy')
    axes[0, 1].legend()
    axes[0, 1].grid(True)
    
    # Learning rate
    axes[1, 0].plot(history['learning_rate'], label='Learning Rate', color='purple')
    axes[1, 0].set_title('Learning Rate Schedule')
    axes[1, 0].set_xlabel('Epoch')
    axes[1, 0].set_ylabel('Learning Rate')
    axes[1, 0].legend()
    axes[1, 0].grid(True)
    axes[1, 0].set_yscale('log')
    
    # Loss comparison
    axes[1, 1].plot(history['splade_loss'], label='SPLADE Loss', color='orange')
    axes[1, 1].plot(history['concept_loss'], label='Concept Loss', color='green')
    axes[1, 1].set_title('Loss Components Comparison')
    axes[1, 1].set_xlabel('Epoch')
    axes[1, 1].set_ylabel('Loss')
    axes[1, 1].legend()
    axes[1, 1].grid(True)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Training plots saved to: {save_path}")
    
    plt.show()


def run_training_experiment(config_manager: ConfigManager,
                          experiment_name: str = None,
                          max_examples: Optional[int] = None,
                          plot_results: bool = True) -> Tuple[SpladeTrainer, Dict[str, List[float]]]:
    """
    Run a complete SPLADE training experiment.
    
    Args:
        config_manager: Configuration manager
        experiment_name: Name for the experiment
        max_examples: Limit examples for testing
        plot_results: Whether to plot training results
        
    Returns:
        Trained model and training history
    """
    if experiment_name:
        config_manager.config.experiment_name = experiment_name
    
    print("="*60)
    print(f"SPLADE WORK ITEM CHARACTERIZATION TRAINING")
    print("="*60)
    print(f"Experiment: {config_manager.config.experiment_name}")
    print(f"Max examples: {max_examples or 'All'}")
    
    # Create trainer
    trainer = create_trainer(
        config_manager=config_manager,
        training_mode="characterization",
        max_examples=max_examples
    )
    
    # Run training
    history = trainer.train()
    
    # Plot results
    if plot_results and len(history['train_loss']) > 1:
        plot_save_path = Path(config_manager.config.logging.output_dir) / "training_curves.png"
        plot_training_history(history, str(plot_save_path))
    
    # Save final results
    results_path = Path(config_manager.config.logging.output_dir) / "training_results.json"
    with open(results_path, 'w') as f:
        json.dump({
            'config': asdict(config_manager.config),
            'final_metrics': {
                'best_val_loss': trainer.best_val_loss,
                'best_concept_accuracy': trainer.best_concept_accuracy,
                'total_epochs': len(history['train_loss']),
                'total_steps': trainer.global_step,
            },
            'history': history
        }, f, indent=2)
    
    print(f"\n✅ Training experiment completed!")
    print(f"📁 Results saved to: {config_manager.config.logging.output_dir}")
    print(f"🎯 Best validation loss: {trainer.best_val_loss:.4f}")
    print(f"🎯 Best concept accuracy: {trainer.best_concept_accuracy:.3f}")
    
    return trainer, history


def test_trainer_setup(config_manager: ConfigManager, max_examples: int = 50) -> bool:
    """Test trainer setup with small dataset."""
    print("Testing SPLADE trainer setup...")
    
    try:
        # Create trainer with small dataset
        trainer = create_trainer(
            config_manager=config_manager,
            training_mode="characterization",
            max_examples=max_examples
        )
        
        print("✅ Trainer setup successful!")
        print(f"📊 Model info:")
        print(f"  SPLADE vocab size: {trainer.model.vocab_size}")
        print(f"  Number of concepts: {trainer.model.num_concepts}")
        print(f"  Parameter types: {list(trainer.model.parameter_vocabs.keys())}")
        print(f"  Device: {trainer.device}")
        
        # Test forward pass
        print("\n🧪 Testing forward pass...")
        batch = next(iter(trainer.train_loader))
        for key, value in batch.items():
            if isinstance(value, torch.Tensor):
                batch[key] = value.to(trainer.device)
        
        trainer.model.eval()
        with torch.no_grad():
            doc_results = trainer.model.forward_characterization(
                batch['input_ids'], 
                batch['attention_mask']
            )
        
        print(f"✅ Forward pass successful!")
        print(f"📋 Output shapes:")
        for key, tensor in doc_results.items():
            if isinstance(tensor, torch.Tensor):
                print(f"  {key}: {tensor.shape}")
        
        return True
        
    except Exception as e:
        print(f"❌ Trainer setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def quick_training_test(config_manager: ConfigManager, 
                       max_examples: int = 100,
                       num_epochs: int = 2) -> bool:
    """Run a quick training test."""
    print("Running quick training test...")
    
    # Modify config for quick test
    original_epochs = config_manager.config.training.num_epochs
    original_eval_steps = config_manager.config.training.eval_steps
    original_save_steps = config_manager.config.training.save_steps
    
    config_manager.config.training.num_epochs = num_epochs
    config_manager.config.training.eval_steps = 10
    config_manager.config.training.save_steps = 20
    
    try:
        trainer = create_trainer(
            config_manager=config_manager,
            training_mode="characterization",
            max_examples=max_examples
        )
        
        # Run quick training
        print(f"🚀 Starting {num_epochs} epoch training test...")
        history = trainer.train()
        
        print("✅ Quick training test successful!")
        print(f"📈 Final metrics:")
        if history['train_loss']:
            print(f"  Final train loss: {history['train_loss'][-1]:.4f}")
        if history['concept_accuracy']:
            print(f"  Final concept accuracy: {history['concept_accuracy'][-1]:.3f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Quick training test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Restore original config
        config_manager.config.training.num_epochs = original_epochs
        config_manager.config.training.eval_steps = original_eval_steps
        config_manager.config.training.save_steps = original_save_steps


# Example usage
if __name__ == "__main__":
    # Import config
    from sandbox.splade.training.config import create_construction_optimized_config
    
    # Create configuration
    config_manager = create_construction_optimized_config(
        experiment_name="trainer_test",
        vocab_file_base="OEB"
    )
    
    # Test trainer setup
    setup_success = test_trainer_setup(config_manager, max_examples=50)
    
    if setup_success:
        print("\n" + "="*50)
        print("RUNNING QUICK TRAINING TEST")
        print("="*50)
        
        # Run quick training test
        quick_success = quick_training_test(config_manager, max_examples=100, num_epochs=2)
        
        if quick_success:
            print("\n🎉 All tests passed! Trainer is ready for full training.")
        else:
            print("\n⚠️ Quick training test failed. Check configuration.")
    else:
        print("\n⚠️ Trainer setup failed. Check data and configuration.")