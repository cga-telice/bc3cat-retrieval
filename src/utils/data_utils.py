# utils/data_utils.py
import logging
import pickle
from pathlib import Path
from typing import Optional, List, Tuple
from src.utils.custom_types import DocumentList
import random

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def load_documents(file_path: Path) -> Optional[DocumentList]:
    """Load documents from a pickle file."""
    try:
        with open(file_path, 'rb') as file:
            documents = pickle.load(file)
        logging.info(f"Successfully loaded {len(documents)} documents from {file_path}")
        return documents
    except Exception as e:
        logging.error(f"Error loading documents from {file_path}: {str(e)}")
        return None

def select_random_documents(documents: DocumentList, n: int) -> List[Tuple[str, str]]:
    """Select n random documents and return their item_key and text."""
    selected = random.sample(documents, min(n, len(documents)))
    return [(doc.metadata['item_key'], doc.text) for doc in selected]