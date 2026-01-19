
import logging
import numpy as np
from collections import defaultdict
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_warehouse.database import get_session
from data_warehouse.models import TrainingGame, TrainingFeatures

logging.basicConfig(level=logging.INFO, format='%(message)s')
LOGGER = logging.getLogger(__name__)

def main():
    with get_session() as session:
        # Join Games and Features
        results = session.query(TrainingGame, TrainingFeatures)\
            .join(TrainingFeatures)\
            .filter(TrainingGame.analyzed == True)\
            .all()
            
        cohorts = defaultdict(list)
        
        # Process INSIDE session to avoid DetachedInstanceError
        for game, features in results:
            # Determine Cohort
            if game.cheater_side in ('white', 'black', 'both'):
                cohort = "Cheater"
            elif game.white_username == 'VladimirKramnik' or game.black_username == 'VladimirKramnik':
                cohort = "Vladimir Kramnik"
            else:
                # Simple heuristic for Titled/High-Level
                 cohort = "Clean (Other Titled)"
                
            # Store features in memory (features are already loaded)
            # We copy key values to avoid detachment issues if we access lazily loaded attributes
            cohorts[cohort].append(features)
            
        # Force evaluation of feature attributes before session closes
        # Actually, let's just extract the raw data we need into simple dicts/lists
        processed_cohorts = {}
        for name, feats in cohorts.items():
            processed_cohorts[name] = []
            for f in feats:
                processed_cohorts[name].append({
                    'engine_agreement': f.engine_agreement,
                    'avg_centipawn_loss': f.avg_centipawn_loss,
                    'move_time_variance': f.move_time_variance,
                    'complexity_correlation': f.complexity_correlation
                })
                
    cohorts = processed_cohorts
        
    print("\n" + "="*60)
    print(f"{'METRIC COMPARISON':^60}")
    print("="*60)
    
    metrics = [
        ('engine_agreement', 'Engine Match'),
        ('avg_centipawn_loss', 'Avg CPL'),
        ('move_time_variance', 'Time Var'),
        ('complexity_correlation', 'Complexity Corr')
    ]
    
    for metric_key, label in metrics:
        print(f"\n{label.upper()}:")
        for name, data in cohorts.items():
            vals = [f[metric_key] for f in data if f.get(metric_key) is not None]
            if not vals: continue
            
            avg = np.mean(vals)
            std = np.std(vals)
            print(f"  {name:<20} | Avg: {avg:.3f} | Std: {std:.3f} | N={len(vals)}")

if __name__ == "__main__":
    main()
