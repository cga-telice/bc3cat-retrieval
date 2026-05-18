#!/usr/bin/env python
# coding: utf-8

# In[10]:

# Function to quote single characters (parameter lables)
def quote_second_term(text):
    # This regular expression matches an operator followed by a variable or a sequence of characters
    pattern = r'(\w+\s*([=<>!]=|[=<>])\s*)(\w+)'

    # This function is used to replace the matched pattern
    def replacer(match):
        return f'{match.group(1)}"{match.group(3)}"'

    # Replace all occurrences in the text using the pattern and replacer function
    return re.sub(pattern, replacer, text)

# formula_processing.py
import re
from math import sin, cos, tan, asin, acos, atan, atan2, sqrt, fabs as ABS, floor as INT

# Function to translate the formula string into Python syntax
def translate_formula_to_python(formula):
# Dictionary to hold the Python equivalents of custom operators and functions
    python_equivalents = {
        "@": " or ",
        "&": " and ",
        "^": "**",
        "=": "==",
        "<>": "!=",
        #"!": "not ",
        "ABS": "ABS",
        "INT": "INT",
        "ROUND": "round",
        "SIN": "sin",
        "COS": "cos",
        "TAN": "tan",
        "ASIN": "asin",
        "ACOS": "acos",
        "ATAN": "atan",
        "ATAN2": "atan2",
        "SQRT": "sqrt",
        "ATOF": "float",  # Assuming conversion from string to float
        "FTOA": "str",    # Assuming conversion from float to string
    }

    # Replace custom operators and function names with Python equivalents
    for custom, py_equiv in python_equivalents.items():
        formula = re.sub(re.escape(custom), py_equiv, formula)
    
    # Transform conditions into Python's ternary condition syntax
    formula = re.sub(r'\(%(\w)=(\w)\)', r'(1 if \1=="\2" else 0)', formula)
   
    # Transform single characters into strings
    formula = quote_second_term(formula)

    return formula


# In[ ]:




