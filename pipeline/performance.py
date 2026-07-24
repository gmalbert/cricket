"""Performance tracking and analysis from settled predictions.

This module provides functions to analyze prediction performance from
the reconciled prediction log, including ROI, calibration, and accuracy metrics.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def calculate_brier_score(predictions: list[dict[str, Any]]) -> float:
    """Calculate Brier score from settled predictions.
    
    Args:
        predictions: List of prediction dicts with model_pick_prob and correct fields
        
    Returns:
        Brier score (lower is better, 0 is perfect)
    """
    if not predictions:
        return 0.0
    
    squared_errors = []
    for pred in predictions:
        prob = pred.get("model_pick_prob", 0.5)
        actual = 1.0 if pred.get("correct") else 0.0
        squared_errors.append((prob - actual) ** 2)
    
    return float(np.mean(squared_errors)) if squared_errors else 0.0


def calculate_calibration(predictions: list[dict[str, Any]], n_bins: int = 10) -> dict[str, Any]:
    """Calculate calibration metrics from settled predictions.
    
    Args:
        predictions: List of prediction dicts
        n_bins: Number of probability bins
        
    Returns:
        Dict with calibration data
    """
    if not predictions:
        return {"bins": [], "slope": 0.0, "intercept": 0.0}
    
    # Create probability bins
    bins = np.linspace(0, 1, n_bins + 1)
    bin_data = []
    
    for i in range(n_bins):
        bin_min = bins[i]
        bin_max = bins[i + 1]
        
        # Get predictions in this bin
        bin_preds = [
            p for p in predictions
            if bin_min <= p.get("model_pick_prob", 0) < bin_max
        ]
        
        if not bin_preds:
            continue
        
        # Calculate average predicted probability and actual win rate
        avg_pred = np.mean([p.get("model_pick_prob", 0) for p in bin_preds])
        actual_rate = np.mean([1.0 if p.get("correct") else 0.0 for p in bin_preds])
        
        bin_data.append({
            "bin_min": bin_min,
            "bin_max": bin_max,
            "count": len(bin_preds),
            "avg_predicted": float(avg_pred),
            "actual_rate": float(actual_rate),
        })
    
    # Calculate calibration slope/intercept via linear regression
    if len(bin_data) >= 2:
        x = np.array([b["avg_predicted"] for b in bin_data])
        y = np.array([b["actual_rate"] for b in bin_data])
        
        # Simple linear regression
        slope, intercept = np.polyfit(x, y, 1)
    else:
        slope, intercept = 1.0, 0.0
    
    return {
        "bins": bin_data,
        "slope": float(slope),
        "intercept": float(intercept),
    }


def calculate_roi_by_edge_bucket(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate ROI by edge bucket.
    
    Args:
        predictions: List of prediction dicts with edge_bucket and roi_winner fields
        
    Returns:
        Dict mapping edge bucket to ROI metrics
    """
    buckets = {}
    
    for pred in predictions:
        bucket = pred.get("edge_bucket")
        roi = pred.get("roi_winner")
        
        if bucket is None or roi is None:
            continue
        
        if bucket not in buckets:
            buckets[bucket] = []
        
        buckets[bucket].append(roi)
    
    # Calculate metrics for each bucket
    bucket_stats = {}
    for bucket, rois in buckets.items():
        if rois:
            bucket_stats[bucket] = {
                "count": len(rois),
                "total_roi": float(np.sum(rois)),
                "avg_roi": float(np.mean(rois)),
                "win_rate": float(np.mean([1 if r > 0 else 0 for r in rois])),
            }
    
    return bucket_stats


def calculate_clv(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate Closing Line Value (CLV) metrics.
    
    CLV measures how our model probabilities compare to closing market odds.
    
    Args:
        predictions: List of prediction dicts
        
    Returns:
        Dict with CLV metrics
    """
    if not predictions:
        return {"avg_clv": 0.0, "positive_clv_rate": 0.0, "samples": 0}
    
    clv_values = []
    
    for pred in predictions:
        model_prob = pred.get("model_pick_prob")
        # For CLV, we'd compare to closing odds, but for now use DK implied
        market_prob = pred.get("dk_implied")
        
        if model_prob is not None and market_prob is not None:
            clv = model_prob - market_prob
            clv_values.append(clv)
    
    if not clv_values:
        return {"avg_clv": 0.0, "positive_clv_rate": 0.0, "samples": 0}
    
    return {
        "avg_clv": float(np.mean(clv_values)),
        "positive_clv_rate": float(np.mean([1 if clv > 0 else 0 for clv in clv_values])),
        "samples": len(clv_values),
    }


def calculate_performance_summary(
    predictions: list[dict[str, Any]],
    competition: str | None = None,
) -> dict[str, Any]:
    """Calculate comprehensive performance summary.
    
    Args:
        predictions: List of settled prediction dicts
        competition: Optional filter by competition
        
    Returns:
        Dict with all performance metrics
    """
    # Filter by competition if specified
    if competition:
        predictions = [p for p in predictions if p.get("competition") == competition]
    
    if not predictions:
        return {
            "competition": competition,
            "total_predictions": 0,
            "accuracy": 0.0,
            "brier_score": 0.0,
            "total_roi": 0.0,
            "avg_roi_per_bet": 0.0,
            "calibration": {"bins": [], "slope": 0.0, "intercept": 0.0},
            "roi_by_edge_bucket": {},
            "clv": {"avg_clv": 0.0, "positive_clv_rate": 0.0, "samples": 0},
        }
    
    # Calculate metrics
    accuracy = np.mean([1.0 if p.get("correct") else 0.0 for p in predictions])
    brier = calculate_brier_score(predictions)
    
    # ROI from bets we actually placed (positive edge only)
    roi_values = [p.get("roi_winner") for p in predictions if p.get("roi_winner") is not None]
    total_roi = float(np.sum(roi_values)) if roi_values else 0.0
    avg_roi = float(np.mean(roi_values)) if roi_values else 0.0
    
    calibration = calculate_calibration(predictions)
    roi_by_bucket = calculate_roi_by_edge_bucket(predictions)
    clv = calculate_clv(predictions)
    
    return {
        "competition": competition,
        "total_predictions": len(predictions),
        "accuracy": float(accuracy),
        "brier_score": float(brier),
        "total_roi": total_roi,
        "avg_roi_per_bet": avg_roi,
        "bets_placed": len(roi_values),
        "win_rate": float(np.mean([1 if r > 0 else 0 for r in roi_values])) if roi_values else 0.0,
        "calibration": calibration,
        "roi_by_edge_bucket": roi_by_bucket,
        "clv": clv,
    }


def performance_by_competition(predictions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Calculate performance for each competition separately.
    
    Args:
        predictions: List of all settled predictions
        
    Returns:
        Dict mapping competition slug to performance summary
    """
    competitions = {p.get("competition", "unknown") for p in predictions}
    
    return {
        comp: calculate_performance_summary(predictions, competition=comp)
        for comp in competitions
    }


def settlement_status_report(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate settlement status report.
    
    Args:
        predictions: List of prediction dicts
        
    Returns:
        Dict with settlement status
    """
    total = len(predictions)
    settled = [p for p in predictions if p.get("correct") is not None]
    pending = [p for p in predictions if p.get("correct") is None]
    
    return {
        "total_predictions": total,
        "settled": len(settled),
        "pending": len(pending),
        "settlement_rate": len(settled) / total if total > 0 else 0.0,
        "oldest_unsettled": min((p.get("date") for p in pending), default=None),
    }
