"""Export training data for scikit-learn and other ML frameworks."""

from __future__ import annotations

import logging
from typing import Tuple, Optional, List, Dict, Any
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from ..models import TrainingFeatures, TrainingGame
from ..database import get_session

LOGGER = logging.getLogger(__name__)


def export_to_dataframe(
    session: Optional[Session] = None,
    include_metadata: bool = False,
    balance_classes: bool = False,
    limit: Optional[int] = None
) -> pd.DataFrame:
    """Export training data to a pandas DataFrame.
    
    Args:
        session: Database session (uses default if None)
        include_metadata: Include game metadata columns
        balance_classes: Undersample majority class for balance
        limit: Maximum number of samples
        
    Returns:
        DataFrame with features and labels
    """
    if session is None:
        with get_session() as session:
            return _export_to_dataframe_impl(session, include_metadata, balance_classes, limit)
    return _export_to_dataframe_impl(session, include_metadata, balance_classes, limit)


def _export_to_dataframe_impl(
    session: Session,
    include_metadata: bool,
    balance_classes: bool,
    limit: Optional[int]
) -> pd.DataFrame:
    """Implementation of DataFrame export."""
    query = session.query(TrainingFeatures)
    
    if limit:
        query = query.limit(limit)
    
    features = query.all()
    
    if not features:
        return pd.DataFrame()
    
    # Convert to dict records
    records = []
    for f in features:
        record = {
            "game_id": f.game_id,
            "engine_agreement": f.engine_agreement or 0,
            "adjusted_engine_agreement": f.adjusted_engine_agreement or 0,
            "timing_suspicion": f.timing_suspicion or 0,
            "scramble_toggle_score": f.scramble_toggle_score or 0,
            "streak_improbability": f.streak_improbability or 0,
            "critical_position_accuracy": f.critical_position_accuracy or 0,
            "complexity_correlation": f.complexity_correlation or 0,
            "sniper_gap": f.sniper_gap or 0,
            "opponent_correlation_score": f.opponent_correlation_score or 0,
            "session_fatigue_score": f.session_fatigue_score or 0,
            "avg_centipawn_loss": f.avg_centipawn_loss or 0,
            "move_time_variance": f.move_time_variance or 0,
            "critical_moves_correct_pct": f.critical_moves_correct_pct or 0,
            "book_exit_accuracy": f.book_exit_accuracy or 0,
            "is_cheater": f.is_cheater,
        }
        
        if include_metadata and f.game:
            record.update({
                "source": f.game.source,
                "time_class": f.game.time_class,
                "white_rating": f.game.white_rating,
                "black_rating": f.game.black_rating,
            })
        
        records.append(record)
    
    df = pd.DataFrame(records)
    
    # Balance classes if requested
    if balance_classes and len(df) > 0:
        cheaters = df[df["is_cheater"] == True]
        non_cheaters = df[df["is_cheater"] == False]
        
        min_size = min(len(cheaters), len(non_cheaters))
        if min_size > 0:
            cheaters = cheaters.sample(n=min_size, random_state=42)
            non_cheaters = non_cheaters.sample(n=min_size, random_state=42)
            df = pd.concat([cheaters, non_cheaters]).sample(frac=1, random_state=42)
    
    return df


def export_for_sklearn(
    session: Optional[Session] = None,
    test_size: float = 0.2,
    random_state: int = 42,
    balance: bool = True
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Export data for scikit-learn training.
    
    Args:
        session: Database session
        test_size: Fraction of data for testing
        random_state: Random seed for reproducibility
        balance: Whether to balance classes
        
    Returns:
        Tuple of (X_train, X_test, y_train, y_test)
    """
    from sklearn.model_selection import train_test_split
    
    df = export_to_dataframe(session, balance_classes=balance)
    
    if len(df) == 0:
        raise ValueError("No training data available")
    
    # Feature columns (exclude metadata and target)
    feature_cols = TrainingFeatures.feature_names()
    
    X = df[feature_cols].values
    y = df["is_cheater"].astype(int).values
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, 
        test_size=test_size, 
        random_state=random_state,
        stratify=y if balance else None
    )
    
    LOGGER.info(f"Exported {len(X_train)} training samples, {len(X_test)} test samples")
    LOGGER.info(f"Training class balance: {y_train.sum() / len(y_train):.2%} cheaters")
    
    return X_train, X_test, y_train, y_test


def export_to_parquet(
    output_path: str,
    session: Optional[Session] = None,
    include_metadata: bool = True
) -> Path:
    """Export training data to Parquet format.
    
    Args:
        output_path: Path for output Parquet file
        session: Database session
        include_metadata: Include game metadata
        
    Returns:
        Path to created Parquet file
    """
    df = export_to_dataframe(session, include_metadata=include_metadata)
    
    path = Path(output_path)
    df.to_parquet(path, engine="pyarrow", index=False)
    
    LOGGER.info(f"Exported {len(df)} samples to {path}")
    return path


def export_to_csv(
    output_path: str,
    session: Optional[Session] = None,
    include_metadata: bool = True
) -> Path:
    """Export training data to CSV format.
    
    Args:
        output_path: Path for output CSV file
        session: Database session
        include_metadata: Include game metadata
        
    Returns:
        Path to created CSV file
    """
    df = export_to_dataframe(session, include_metadata=include_metadata)
    
    path = Path(output_path)
    df.to_csv(path, index=False)
    
    LOGGER.info(f"Exported {len(df)} samples to {path}")
    return path


def get_dataset_stats(session: Optional[Session] = None) -> Dict[str, Any]:
    """Get statistics about the training dataset.
    
    Returns:
        Dictionary with dataset statistics
    """
    if session is None:
        with get_session() as session:
            return _get_dataset_stats_impl(session)
    return _get_dataset_stats_impl(session)


def _get_dataset_stats_impl(session: Session) -> Dict[str, Any]:
    """Implementation of dataset stats."""
    total_games = session.query(TrainingGame).count()
    analyzed_games = session.query(TrainingGame).filter_by(analyzed=True).count()
    
    cheater_games = session.query(TrainingGame).filter(
        TrainingGame.cheater_side.in_(["white", "black", "both"])
    ).count()
    
    clean_games = session.query(TrainingGame).filter(
        TrainingGame.cheater_side == "none"
    ).count()
    
    # By source
    sources = session.query(
        TrainingGame.source,
        session.query(TrainingGame).filter_by(source=TrainingGame.source).count()
    ).group_by(TrainingGame.source).all()
    
    # By time class
    time_classes = session.query(
        TrainingGame.time_class,
        session.query(TrainingGame).filter_by(time_class=TrainingGame.time_class).count()
    ).group_by(TrainingGame.time_class).all()
    
    return {
        "total_games": total_games,
        "analyzed_games": analyzed_games,
        "cheater_games": cheater_games,
        "clean_games": clean_games,
        "cheater_ratio": cheater_games / total_games if total_games > 0 else 0,
        "by_source": dict(sources) if sources else {},
        "by_time_class": dict(time_classes) if time_classes else {},
    }
