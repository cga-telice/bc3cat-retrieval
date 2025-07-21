"""
SPLADE Word-Level Training Configuration System

This module provides comprehensive configuration management for training
word-level SPLADE models. It handles hyperparameters, model settings,
data configuration, and hardware optimization settings.
"""

import json
import yaml
import os
import torch
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, asdict, field
from datetime import datetime


@dataclass
class ModelConfig:
    """Model architecture configuration."""
    # Base model settings
    base_model_name: str = "dccuchile/bert-base-spanish-wwm-cased"
    vocab_size: int = 50000
    hidden_size: int = 768  # Will be auto-detected from base model
    dropout: float = 0.15
    
    # SPLADE-specific parameters
    sparsity_regularizer: str = "flops"  # "flops", "l1", or "none"
    lambda_d: float = 5e-6  # Document sparsity regularization weight
    lambda_q: float = 8e-6  # Query sparsity regularization weight
    
    # Activation and pooling
    activation: str = "relu"  # "relu", "gelu", or "swish"
    pooling: str = "sum"  # "sum", "max", or "mean"
    apply_log: bool = True  # Apply log(1+x) transformation
    
    # Model initialization
    freeze_base_model: bool = False  # Whether to freeze base model weights
    reinit_layers: int = 0  # Number of top layers to reinitialize


@dataclass
class DataConfig:
    """Data processing and loading configuration."""
    # Vocabulary settings
    vocab_path: str = "/work/sandbox/splade/vocabularies"
    vocab_file_base: str = "OEB"
    use_filtered_vocab: bool = True  # Use filtered (no stopwords) vocabulary
    
    # Document paths
    data_path: str = "/work/data/processed"
    file_base: str = "OEB"
    
    # Tokenization settings
    max_sequence_length: int = 256
    add_special_tokens: bool = True
    truncation: bool = True
    padding: str = "max_length"  # "max_length", "longest", or "do_not_pad"
    
    # Training data split
    train_split: float = 0.8
    val_split: float = 0.1
    test_split: float = 0.1
    random_seed: int = 42
    
    # Data augmentation
    enable_augmentation: bool = False
    augmentation_prob: float = 0.1
    
    # Batch processing
    batch_size: int = 8
    eval_batch_size: int = 32
    num_workers: int = 4
    pin_memory: bool = True
    drop_last: bool = True


@dataclass
class TrainingConfig:
    """Training process configuration."""
    # Optimizer settings
    optimizer: str = "adamw"  # "adamw", "adam", or "sgd"
    learning_rate: float = 3e-5
    weight_decay: float = 0.01
    eps: float = 1e-8
    betas: tuple = (0.9, 0.999)
    
    # Learning rate scheduling
    scheduler: str = "linear"  # "linear", "cosine", "constant", or "polynomial"
    warmup_steps: int = 1000
    warmup_ratio: float = 0.15  # Alternative to warmup_steps
    
    # Training loop
    num_epochs: int = 15
    max_steps: int = -1  # Override epochs if set
    gradient_accumulation_steps: int = 4
    max_grad_norm: float = 1.0
    
    # Evaluation settings
    eval_strategy: str = "steps"  # "steps", "epoch", or "no"
    eval_steps: int = 500
    save_strategy: str = "steps"  # "steps", "epoch", or "no"
    save_steps: int = 1000
    save_total_limit: int = 3
    
    # Early stopping
    early_stopping: bool = True
    early_stopping_patience: int = 3
    early_stopping_threshold: float = 1e-4
    
    # Loss configuration
    loss_type: str = "ranking"  # "ranking", "contrastive", or "mlm"
    margin: float = 0.3  # For ranking loss
    temperature: float = 0.1  # For contrastive loss
    
    # MLM settings (for pre-training)
    mlm_probability: float = 0.15
    mlm_ignore_index: int = -100


@dataclass
class HardwareConfig:
    """Hardware and performance optimization configuration."""
    # Device settings
    device: str = "auto"  # "auto", "cpu", "cuda", or specific device
    use_cuda: bool = True
    cuda_device_count: int = -1  # -1 for auto-detect
    
    # Mixed precision training
    fp16: bool = False
    bf16: bool = False  # Better than fp16 if supported
    fp16_opt_level: str = "O1"  # For apex
    
    # Memory optimization
    gradient_checkpointing: bool = False
    dataloader_num_workers: int = 4
    pin_memory: bool = True
    
    # Performance tuning
    torch_compile: bool = False  # PyTorch 2.0 compilation
    torch_compile_mode: str = "default"  # "default", "reduce-overhead", "max-autotune"
    
    # Distributed training
    local_rank: int = -1
    world_size: int = 1
    distributed_backend: str = "nccl"


@dataclass
class LoggingConfig:
    """Logging and monitoring configuration."""
    # Output paths
    output_dir: str = "/work/sandbox/splade/models"
    logging_dir: str = "/work/sandbox/splade/logs"
    cache_dir: str = "/work/sandbox/splade/cache"
    
    # Logging settings
    logging_level: str = "INFO"  # "DEBUG", "INFO", "WARNING", "ERROR"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    console_logging: bool = True
    file_logging: bool = True
    
    # Progress tracking
    progress_bar: bool = True
    log_every_n_steps: int = 50
    save_predictions: bool = True
    
    # Monitoring
    report_to: str = "none"  # "tensorboard", "wandb", "none"
    run_name: Optional[str] = None
    project_name: str = "splade-word-level"
    
    # Checkpointing
    resume_from_checkpoint: Optional[str] = None
    save_safetensors: bool = True


@dataclass
class ExperimentConfig:
    """Complete experiment configuration."""
    # Component configurations
    model: ModelConfig = field(default_factory=ModelConfig)
    data: DataConfig = field(default_factory=DataConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    # Experiment metadata
    experiment_name: str = "word_splade_experiment"
    description: str = "Word-level SPLADE training experiment"
    tags: List[str] = field(default_factory=list)
    
    # Reproducibility
    seed: int = 42
    deterministic: bool = True
    
    def __post_init__(self):
        """Post-initialization processing."""
        # Set up experiment directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if self.experiment_name == "word_splade_experiment":
            self.experiment_name = f"word_splade_{timestamp}"
        
        # Update paths with experiment name
        self.logging.output_dir = str(Path(self.logging.output_dir) / self.experiment_name)
        self.logging.logging_dir = str(Path(self.logging.logging_dir) / self.experiment_name)
        
        # Auto-detect device if needed
        if self.hardware.device == "auto":
            self.hardware.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Set vocabulary size from vocabulary path if available
        if self.data.vocab_path and self.data.vocab_file_base:
            vocab_suffix = "filtered" if self.data.use_filtered_vocab else "full"
            vocab_full_path = Path(self.data.vocab_path) / f"{self.data.vocab_file_base}_vocab_{vocab_suffix}_{self.model.vocab_size}"
            if vocab_full_path.exists():
                # Could load actual vocab size here if needed
                pass


class ConfigManager:
    """Configuration manager with loading, saving, and validation capabilities."""
    
    def __init__(self, config: Optional[ExperimentConfig] = None):
        """Initialize configuration manager."""
        self.config = config or ExperimentConfig()
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "ConfigManager":
        """Create configuration from dictionary."""
        # Parse nested configuration
        model_config = ModelConfig(**config_dict.get("model", {}))
        data_config = DataConfig(**config_dict.get("data", {}))
        training_config = TrainingConfig(**config_dict.get("training", {}))
        hardware_config = HardwareConfig(**config_dict.get("hardware", {}))
        logging_config = LoggingConfig(**config_dict.get("logging", {}))
        
        # Extract experiment-level settings
        experiment_dict = {k: v for k, v in config_dict.items() 
                          if k not in ["model", "data", "training", "hardware", "logging"]}
        
        config = ExperimentConfig(
            model=model_config,
            data=data_config,
            training=training_config,
            hardware=hardware_config,
            logging=logging_config,
            **experiment_dict
        )
        
        return cls(config)
    
    @classmethod
    def from_json(cls, json_path: Union[str, Path]) -> "ConfigManager":
        """Load configuration from JSON file."""
        with open(json_path, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)
        return cls.from_dict(config_dict)
    
    @classmethod
    def from_yaml(cls, yaml_path: Union[str, Path]) -> "ConfigManager":
        """Load configuration from YAML file."""
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f)
        return cls.from_dict(config_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self.config)
    
    def save_json(self, json_path: Union[str, Path]) -> None:
        """Save configuration to JSON file."""
        Path(json_path).parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    def save_yaml(self, yaml_path: Union[str, Path]) -> None:
        """Save configuration to YAML file."""
        Path(yaml_path).parent.mkdir(parents=True, exist_ok=True)
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, allow_unicode=True)
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []
        
        # Validate paths exist
        if not Path(self.config.data.data_path).exists():
            issues.append(f"Data path does not exist: {self.config.data.data_path}")
        
        vocab_suffix = "filtered" if self.config.data.use_filtered_vocab else "full"
        vocab_path = Path(self.config.data.vocab_path) / f"{self.config.data.vocab_file_base}_vocab_{vocab_suffix}_{self.config.model.vocab_size}"
        if not vocab_path.exists():
            issues.append(f"Vocabulary path does not exist: {vocab_path}")
        
        # Validate split ratios
        total_split = self.config.data.train_split + self.config.data.val_split + self.config.data.test_split
        if abs(total_split - 1.0) > 1e-6:
            issues.append(f"Data splits don't sum to 1.0: {total_split}")
        
        # Validate hardware settings
        if self.config.hardware.device.startswith("cuda") and not torch.cuda.is_available():
            issues.append("CUDA device requested but CUDA is not available")
        
        # Validate learning rate and scheduler
        if self.config.training.scheduler == "linear" and self.config.training.warmup_ratio <= 0:
            issues.append("Linear scheduler requires positive warmup_ratio")
        
        # Validate batch sizes
        if self.config.data.batch_size <= 0:
            issues.append("Batch size must be positive")
        
        # Validate sparsity parameters
        if self.config.model.lambda_d < 0 or self.config.model.lambda_q < 0:
            issues.append("Sparsity regularization weights must be non-negative")
        
        return issues
    
    def update_from_env(self) -> None:
        """Update configuration from environment variables."""
        # Define environment variable mappings
        env_mappings = {
            "SPLADE_LEARNING_RATE": ("training", "learning_rate", float),
            "SPLADE_BATCH_SIZE": ("data", "batch_size", int),
            "SPLADE_NUM_EPOCHS": ("training", "num_epochs", int),
            "SPLADE_DEVICE": ("hardware", "device", str),
            "SPLADE_OUTPUT_DIR": ("logging", "output_dir", str),
            "SPLADE_VOCAB_PATH": ("data", "vocab_path", str),
            "SPLADE_DATA_PATH": ("data", "data_path", str),
            "SPLADE_FP16": ("hardware", "fp16", lambda x: x.lower() == "true"),
            "SPLADE_GRADIENT_ACCUMULATION": ("training", "gradient_accumulation_steps", int),
        }
        
        for env_var, (section, param, converter) in env_mappings.items():
            if env_var in os.environ:
                try:
                    value = converter(os.environ[env_var])
                    setattr(getattr(self.config, section), param, value)
                    print(f"Updated {section}.{param} from environment: {value}")
                except (ValueError, TypeError) as e:
                    print(f"Warning: Could not parse {env_var}={os.environ[env_var]}: {e}")
    
    def create_output_directories(self) -> None:
        """Create necessary output directories."""
        directories = [
            self.config.logging.output_dir,
            self.config.logging.logging_dir,
            self.config.logging.cache_dir,
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {directory}")
    
    def print_config(self) -> None:
        """Print configuration in a readable format."""
        print("=" * 60)
        print("SPLADE TRAINING CONFIGURATION")
        print("=" * 60)
        
        sections = [
            ("Model Configuration", self.config.model),
            ("Data Configuration", self.config.data),
            ("Training Configuration", self.config.training),
            ("Hardware Configuration", self.config.hardware),
            ("Logging Configuration", self.config.logging),
        ]
        
        for section_name, section_config in sections:
            print(f"\n{section_name}:")
            for key, value in asdict(section_config).items():
                print(f"  {key}: {value}")
        
        print(f"\nExperiment: {self.config.experiment_name}")
        print(f"Description: {self.config.description}")
        print(f"Tags: {self.config.tags}")


def create_default_config(experiment_name: str = None, 
                         vocab_file_base: str = "OEB",
                         use_filtered_vocab: bool = True) -> ConfigManager:
    """Create a default configuration for common use cases."""
    config = ExperimentConfig()
    
    if experiment_name:
        config.experiment_name = experiment_name
    
    # Set vocabulary configuration
    config.data.vocab_file_base = vocab_file_base
    config.data.file_base = vocab_file_base
    config.data.use_filtered_vocab = use_filtered_vocab
    
    # Optimize for common hardware
    if torch.cuda.is_available():
        config.hardware.device = "cuda"
        config.hardware.fp16 = True
        config.data.batch_size = 16
    else:
        config.hardware.device = "cpu"
        config.data.batch_size = 8
    
    return ConfigManager(config)


def create_quick_config(learning_rate: float = 5e-5,
                       batch_size: int = 16,
                       num_epochs: int = 5,
                       vocab_file_base: str = "OEB") -> ConfigManager:
    """Create a quick configuration for testing."""
    config_manager = create_default_config(
        experiment_name=f"quick_test_{datetime.now().strftime('%H%M%S')}",
        vocab_file_base=vocab_file_base
    )
    
    # Set quick training parameters
    config_manager.config.training.learning_rate = learning_rate
    config_manager.config.data.batch_size = batch_size
    config_manager.config.training.num_epochs = num_epochs
    config_manager.config.training.eval_steps = 100
    config_manager.config.training.save_steps = 200
    
    return config_manager


# Convenience functions for Jupyter notebooks
def load_config(config_path: str) -> ConfigManager:
    """Load configuration from file (auto-detect format)."""
    path = Path(config_path)
    if path.suffix.lower() == '.json':
        return ConfigManager.from_json(path)
    elif path.suffix.lower() in ['.yml', '.yaml']:
        return ConfigManager.from_yaml(path)
    else:
        raise ValueError(f"Unsupported config format: {path.suffix}")


def save_config(config_manager: ConfigManager, config_path: str) -> None:
    """Save configuration to file (auto-detect format)."""
    path = Path(config_path)
    if path.suffix.lower() == '.json':
        config_manager.save_json(path)
    elif path.suffix.lower() in ['.yml', '.yaml']:
        config_manager.save_yaml(path)
    else:
        raise ValueError(f"Unsupported config format: {path.suffix}")


# Example usage and testing
if __name__ == "__main__":
    # Create default configuration
    config_manager = create_default_config(
        experiment_name="test_experiment",
        vocab_file_base="OEB",
        use_filtered_vocab=True
    )
    
    # Update from environment variables
    config_manager.update_from_env()
    
    # Validate configuration
    issues = config_manager.validate()
    if issues:
        print("Configuration issues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("Configuration is valid!")
    
    # Print configuration
    config_manager.print_config()
    
    # Create output directories
    config_manager.create_output_directories()
    
    # Save configuration
    save_config(config_manager, "/work/sandbox/splade/training/example_config.json")
    print("\nConfiguration saved to example_config.json")