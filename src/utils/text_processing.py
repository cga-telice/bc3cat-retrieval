# utils/text_processing.py
import re
from typing import List

def normalize_text(text: str) -> List[str]:
    """Normalize text by lowercasing and handling accents."""
    text = text.lower()
    text = re.sub(r'[áàäâ]', 'a', text)
    text = re.sub(r'[éèëê]', 'e', text)
    text = re.sub(r'[íìïî]', 'i', text)
    text = re.sub(r'[óòöô]', 'o', text)
    text = re.sub(r'[úùüû]', 'u', text)
    return re.findall(r'\w+', text)