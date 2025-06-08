# utils/evaluation.py
import numpy as np
from typing import List, Dict, Any
from src.utils.custom_types import RetrievalResult
import random

def perform_analysis(results: List[RetrievalResult]) -> Dict[str, float]:
    """Calculate standard retrieval metrics (Precision, Recall, F1, MRR, MAP)."""
    total_queries = len(results)
    total_correct = 0
    total_retrieved = 0
    reciprocal_ranks = []
    precisions = []
    
    for result in results:
        resumen_key = result['resumen_item_key']
        retrieved_keys = [item['item_key'] for item in result['texto_results']]
        total_retrieved += len(retrieved_keys)
        
        if resumen_key in retrieved_keys:
            total_correct += 1
            rank = retrieved_keys.index(resumen_key) + 1
            reciprocal_ranks.append(1 / rank)
            precisions.append(1 / rank)
        else:
            reciprocal_ranks.append(0)
            precisions.append(0)
    
    recall = total_correct / total_queries
    precision = total_correct / total_retrieved if total_retrieved > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    mrr = sum(reciprocal_ranks) / total_queries
    map_score = sum(precisions) / total_queries

    return {
        "Recall": recall,
        "Precision": precision,
        "F1 Score": f1_score,
        "Mean Reciprocal Rank (MRR)": mrr,
        "Mean Average Precision (MAP)": map_score
    }

def perform_single_match_analysis(results: List[RetrievalResult], top_k: int = 10) -> Dict[str, Any]:
    """
    Perform analysis specialized for cases where each query has exactly one correct match.
    
    Parameters:
    -----------
    results : List[dict]
        List of dictionaries containing retrieval results, where each dictionary has:
        - resumen_item_key: The query document's key
        - texto_results: List of retrieved documents with their scores
    top_k : int
        Number of top results to consider
        
    Returns:
    --------
    dict
        Dictionary containing the evaluation metrics
    """
    
    total_queries = len(results)
    hits_at_k = 0  # Number of correct matches found within top k results
    reciprocal_ranks = []
    first_hit_positions = []
    
    for result in results:
        query_key = result['resumen_item_key']
        retrieved_keys = [item['item_key'] for item in result['texto_results'][:top_k]]
        
        # Check if correct match is in top k results
        if query_key in retrieved_keys:
            hits_at_k += 1
            position = retrieved_keys.index(query_key) + 1
            reciprocal_ranks.append(1.0 / position)
            first_hit_positions.append(position)
        else:
            reciprocal_ranks.append(0.0)
            first_hit_positions.append(float('inf'))
    
    # Calculate metrics
    metrics = {
        "Success@K": hits_at_k / total_queries,  # Proportion of queries where correct match was in top k
        "MRR": sum(reciprocal_ranks) / total_queries,  # Mean Reciprocal Rank
        "Mean Position": np.mean([p for p in first_hit_positions if p != float('inf')]),  # Average position of correct matches
        "Median Position": np.median([p for p in first_hit_positions if p != float('inf')]),  # Median position of correct matches
        "Perfect Matches": sum(1 for rr in reciprocal_ranks if rr == 1.0) / total_queries,  # Proportion of correct matches at position 1
    }
    
    # Calculate position distribution
    position_dist = {}
    for pos in range(1, top_k + 1):
        position_dist[f"Position_{pos}"] = sum(1 for p in first_hit_positions if p == pos) / total_queries
    
    metrics["Position_Distribution"] = position_dist
    
    return metrics

def print_single_match_analysis(metrics: dict, top_k: int):
    """Print the single-match analysis results."""
    print("\nSingle-Match Analysis Results:")
    print("=" * 50)
    
    print(f"Success@{top_k:<15}: {metrics['Success@K']:.2%}")
    print(f"MRR: {metrics['MRR']:.4f}")
    print(f"Mean Position: {metrics['Mean Position']:.2f}")
    print(f"Median Position: {metrics['Median Position']:.1f}")
    print(f"Perfect Matches: {metrics['Perfect Matches']:.2%}")
    
    print("\nPosition Distribution:")
    print("-" * 30)
    for pos, freq in metrics["Position_Distribution"].items():
        print(f"{pos:<10}: {freq:.2%}")

def print_sample_results(all_results: List[dict], num_samples: int = 5, top_k: int = 10):
    """Print sample retrieval results."""
    samples = random.sample(all_results, min(num_samples, len(all_results)))
    
    for i, sample in enumerate(samples, 1):
        print(f"\n{'=' * 80}")
        print(f"Sample {i}")
        print(f"{'=' * 80}")
        print(f"Query item key: {sample['resumen_item_key']}")
        print(f"Query text: {sample['resumen_text']}")
        print(f"Target text: {sample['target_text']}")
        print(f"Target score: {sample['target_score']}")
        
        print("\nTop retrieved results:")
        for j, result in enumerate(sample['texto_results'][:top_k], 1):
            print(f"\n  Result {j}:")
            print(f"    Item key: {result['item_key']}")
            print(f"    Text: {result['text']}")
            # Handle single vs list of scores
            score = result['score']
            if isinstance(score, list):
                formatted_scores = ', '.join(f"{s:.6f}" for s in score)
                print(f"    Score: [{formatted_scores}]")  # Format as list
            else:
                print(f"    Score: {score:.6f}") 
        
        print(f"\n{'-' * 50}")

def calculate_prefix_success_at_k(results, k=10, prefix_length=6):
    """
    Calculate Success@K metric where success is defined as retrieving an item 
    whose item_key's first N characters match the query's item_key.
    
    Parameters:
    -----------
    results : List[dict]
        List of retrieval results, each containing:
        - resumen_item_key: The query document's key
        - texto_results: List of retrieved documents
    k : int
        Number of top results to consider
    prefix_length : int
        Number of characters to match at the beginning of item_key
        
    Returns:
    --------
    float
        Success@K score based on prefix matching
    """
    total_queries = len(results)
    successful_queries = 0
    
    for result in results:
        query_key_prefix = result['resumen_item_key'][:prefix_length]
        retrieved_items = result['texto_results'][:k]
        
        # Check if any retrieved item has a matching prefix
        for item in retrieved_items:
            retrieved_key_prefix = item['item_key'][:prefix_length]
            if query_key_prefix == retrieved_key_prefix:
                successful_queries += 1
                break
    
    return successful_queries / total_queries if total_queries > 0 else 0

def perform_prefix_match_analysis(results, top_k=10, prefix_length=6):
    """
    Perform comprehensive analysis using prefix matching instead of exact matching.
    
    Parameters:
    -----------
    results : List[dict]
        List of retrieval results
    top_k : int
        Number of top results to consider
    prefix_length : int
        Length of prefix to match
        
    Returns:
    --------
    dict
        Dictionary containing various evaluation metrics
    """
    total_queries = len(results)
    hits_at_k = 0
    reciprocal_ranks = []
    first_hit_positions = []
    
    for result in results:
        query_key_prefix = result['resumen_item_key'][:prefix_length]
        retrieved_keys = [item['item_key'] for item in result['texto_results'][:top_k]]
        
        # Find position of first match based on prefix
        position = None
        for i, key in enumerate(retrieved_keys):
            retrieved_prefix = key[:prefix_length]
            if query_key_prefix == retrieved_prefix:
                position = i + 1
                break
        
        if position is not None:
            hits_at_k += 1
            reciprocal_ranks.append(1.0 / position)
            first_hit_positions.append(position)
        else:
            reciprocal_ranks.append(0.0)
            first_hit_positions.append(float('inf'))
    
    # Calculate metrics
    metrics = {
        "Prefix_Success@K": hits_at_k / total_queries,  # Proportion of queries with a prefix match in top k
        "Prefix_MRR": sum(reciprocal_ranks) / total_queries,  # Mean Reciprocal Rank with prefix matching
        "Prefix_Mean_Position": sum([p for p in first_hit_positions if p != float('inf')]) / hits_at_k if hits_at_k > 0 else float('inf'),
        "Prefix_Median_Position": sorted([p for p in first_hit_positions if p != float('inf')])[hits_at_k // 2] if hits_at_k > 0 else float('inf'),
        "Prefix_Perfect_Matches": sum(1 for rr in reciprocal_ranks if rr == 1.0) / total_queries,  # Proportion of correct matches at position 1
    }
    
    # Calculate position distribution
    position_dist = {}
    for pos in range(1, top_k + 1):
        position_dist[f"Prefix_Position_{pos}"] = sum(1 for p in first_hit_positions if p == pos) / total_queries
    
    metrics["Prefix_Position_Distribution"] = position_dist
    
    return metrics

def print_prefix_match_analysis(metrics, top_k=10, prefix_length=6):
    """Print the prefix-match analysis results."""
    print("\nPrefix Matching Analysis Results (first {} characters):".format(prefix_length))
    print("=" * 60)
    
    print(f"Prefix_Success@{top_k:<15}: {metrics['Prefix_Success@K']:.2%}")
    print(f"Prefix_MRR: {metrics['Prefix_MRR']:.4f}")
    
    if metrics['Prefix_Mean_Position'] != float('inf'):
        print(f"Prefix_Mean_Position: {metrics['Prefix_Mean_Position']:.2f}")
    else:
        print(f"Prefix_Mean_Position: N/A (no matches found)")
        
    if metrics['Prefix_Median_Position'] != float('inf'):
        print(f"Prefix_Median_Position: {metrics['Prefix_Median_Position']:.1f}")
    else:
        print(f"Prefix_Median_Position: N/A (no matches found)")
        
    print(f"Prefix_Perfect_Matches: {metrics['Prefix_Perfect_Matches']:.2%}")
    
    print("\nPrefix Position Distribution:")
    print("-" * 40)
    for pos in range(1, top_k + 1):
        key = f"Prefix_Position_{pos}"
        if key in metrics["Prefix_Position_Distribution"]:
            print(f"Position {pos:<5}: {metrics['Prefix_Position_Distribution'][key]:.2%}")
