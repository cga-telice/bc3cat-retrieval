# config.py
from pathlib import Path

class Config:
    # Paths
    DATA_DIR = Path('/work/data/llamaindex')
    TEXTO_PATH = DATA_DIR / 'IISS_plataforma_texto.pkl'
    RESUMEN_PATH = DATA_DIR / 'IISS_plataforma_resumen.pkl'
    
    # Common parameters
    TOP_K = 10
    NUM_SAMPLES = 5
    
    # BM25 parameters
    BM25_K1 = 1.5
    BM25_B = 0.75