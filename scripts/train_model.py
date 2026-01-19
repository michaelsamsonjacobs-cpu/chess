"""
Train XGBoost classifier on extracted features.
"""

import logging
import pickle
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOGGER = logging.getLogger(__name__)

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    LOGGER.warning("XGBoost not installed, using sklearn RandomForest")
    HAS_XGBOOST = False

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, roc_auc_score

from data_warehouse.database import get_session
from data_warehouse.models import TrainingFeatures


def load_training_data():
    """Load features and labels from database."""
    LOGGER.info("Loading training data...")
    
    with get_session() as session:
        features_list = session.query(TrainingFeatures).all()
        
        if not features_list:
            LOGGER.error("No training features found!")
            return None, None
        
        # Balance classes (undersample majority)
        cheaters = [tf for tf in features_list if tf.is_cheater]
        clean = [tf for tf in features_list if not tf.is_cheater]
        
        LOGGER.info(f"Checking class balance: {len(cheaters)} cheaters, {len(clean)} clean")
        
        if not clean:
            LOGGER.error("No clean games found! Cannot train classifier.")
            return None, None
            
        # Determine sample size (use all minority class)
        n_samples = min(len(cheaters), len(clean))
        import random
        random.shuffle(cheaters)
        random.shuffle(clean)
        
        balanced_features = cheaters[:n_samples] + clean[:n_samples]
        LOGGER.info(f"Balanced dataset: {len(balanced_features)} samples ({n_samples} per class)")
        
        X = []
        y = []
        
        for tf in balanced_features:
            X.append(tf.to_feature_vector())
            y.append(1 if tf.is_cheater else 0)
        
        return np.array(X), np.array(y)


def train_model(X, y):
    """Train the cheat detection model."""
    LOGGER.info(f"Training on {len(X)} samples...")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    LOGGER.info(f"Training set: {len(X_train)}, Test set: {len(X_test)}")
    LOGGER.info(f"Class balance - Cheaters: {sum(y_train)}, Non-cheaters: {len(y_train) - sum(y_train)}")
    
    # Train model
    if HAS_XGBOOST:
        model = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss'
        )
    else:
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    accuracy = accuracy_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_prob)
    
    LOGGER.info("=" * 50)
    LOGGER.info(f"Model Performance:")
    LOGGER.info(f"  Accuracy: {accuracy:.4f}")
    LOGGER.info(f"  AUC-ROC:  {auc:.4f}")
    LOGGER.info("=" * 50)
    LOGGER.info("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['Non-Cheater', 'Cheater']))
    
    # Feature importance
    if hasattr(model, 'feature_importances_'):
        feature_names = TrainingFeatures.feature_names()
        importances = sorted(zip(feature_names, model.feature_importances_), 
                           key=lambda x: x[1], reverse=True)
        LOGGER.info("\nTop Features:")
        for name, imp in importances[:5]:
            LOGGER.info(f"  {name}: {imp:.4f}")
    
    return model


def save_model(model, output_dir: Path):
    """Save trained model to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = output_dir / f"cheat_detector_{timestamp}.pkl"
    
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    
    # Also save as 'latest'
    latest_path = output_dir / "cheat_detector_latest.pkl"
    with open(latest_path, 'wb') as f:
        pickle.dump(model, f)
    
    LOGGER.info(f"Model saved to {model_path}")
    LOGGER.info(f"Latest model at {latest_path}")
    
    return model_path


def main():
    LOGGER.info("Starting model training...")
    
    X, y = load_training_data()
    
    if X is None or len(X) == 0:
        LOGGER.error("No data to train on!")
        return
    
    model = train_model(X, y)
    
    # Save model
    models_dir = Path(__file__).parent.parent / "models"
    save_model(model, models_dir)
    
    LOGGER.info("Training complete!")


if __name__ == "__main__":
    main()
