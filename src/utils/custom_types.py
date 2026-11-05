# custom_types.py
from typing import List, Dict, Any, Union, Tuple, Optional
import numpy as np
import scipy.sparse as sparse
from llama_index.core import Document

DocumentList = List[Document]
RetrievalResult = Dict[str, Any]
EmbeddingVector = Union[np.ndarray, sparse.csr_matrix]