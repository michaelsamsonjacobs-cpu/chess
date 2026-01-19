"""Model training entry point for ChessGuard."""
from __future__ import annotations

import argparse
import json
import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence, Tuple

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError as exc:  # pragma: no cover - Python < 3.11 fallback
    raise ImportError("The training module requires Python 3.11 or newer.") from exc

from ..data import ingest as ingest_utils

logger = logging.getLogger(__name__)


@dataclass
class DataConfig:
    """Parameters describing the training dataset."""

    path: Path
    format: str = "parquet"
    features: List[str] = field(default_factory=lambda: ["engine_average_centipawn_loss"])
    target: str = "label"
    positive_label: Optional[str] = "suspicious"
    negative_label: Optional[str] = "clean"
    drop_unlabeled: bool = True


@dataclass
class SplitConfig:
    validation_fraction: float = 0.2
    random_seed: int = 13


@dataclass
class ModelConfig:
    model_type: str = "threshold"
    direction: str = "lower-is-positive"
    optimisation_metric: str = "f1"


@dataclass
class ArtifactsConfig:
    output_dir: Path = Path("data/artifacts")
    model_filename: str = "model.json"
    metrics_filename: str = "metrics.json"
    split_filename: str = "split.json"


@dataclass
class TrainingConfig:
    data: DataConfig
    split: SplitConfig = field(default_factory=SplitConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    artifacts: ArtifactsConfig = field(default_factory=ArtifactsConfig)


@dataclass
class ThresholdModel:
    """Simple threshold-based classifier."""

    feature: str
    threshold: float
    direction: str
    positive_label: Optional[str]

    def predict(self, value: float) -> bool:
        if self.direction == "lower-is-positive":
            return value <= self.threshold
        if self.direction == "higher-is-positive":
            return value >= self.threshold
        raise ValueError(f"Unsupported direction: {self.direction}")


@dataclass
class TrainingResult:
    model: ThresholdModel
    train_metrics: Mapping[str, float]
    validation_metrics: Mapping[str, float]
    model_path: Path
    metrics_path: Path


def load_training_config(path: Path) -> TrainingConfig:
    """Load a configuration file from ``path``."""

    with path.open("rb") as handle:
        payload = tomllib.load(handle)

    data_cfg = payload.get("data", {})
    split_cfg = payload.get("split", {})
    model_cfg = payload.get("model", {})
    artifacts_cfg = payload.get("artifacts", {})

    data = DataConfig(
        path=Path(data_cfg.get("path", "data/processed/games.parquet")),
        format=data_cfg.get("format", "parquet"),
        features=list(data_cfg.get("features", [data_cfg.get("feature", "engine_average_centipawn_loss")])),
        target=data_cfg.get("target", "label"),
        positive_label=data_cfg.get("positive_label", "suspicious"),
        negative_label=data_cfg.get("negative_label", "clean"),
        drop_unlabeled=data_cfg.get("drop_unlabeled", True),
    )

    split = SplitConfig(
        validation_fraction=float(split_cfg.get("validation_fraction", 0.2)),
        random_seed=int(split_cfg.get("random_seed", 13)),
    )

    model = ModelConfig(
        model_type=model_cfg.get("type", "threshold"),
        direction=model_cfg.get("direction", "lower-is-positive"),
        optimisation_metric=model_cfg.get("optimisation_metric", "f1"),
    )

    artifacts = ArtifactsConfig(
        output_dir=Path(artifacts_cfg.get("output_dir", "data/artifacts")),
        model_filename=artifacts_cfg.get("model_filename", "model.json"),
        metrics_filename=artifacts_cfg.get("metrics_filename", "metrics.json"),
        split_filename=artifacts_cfg.get("split_filename", "split.json"),
    )

    return TrainingConfig(data=data, split=split, model=model, artifacts=artifacts)


def load_records(path: Path, fmt: str) -> List[Mapping[str, Any]]:
    """Load training records from ``path``."""

    fmt = fmt.lower()
    if fmt == "parquet":
        try:
            import pyarrow.parquet as pq  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "Reading parquet files requires 'pyarrow'. Install it with 'pip install pyarrow'."
            ) from exc
        table = pq.read_table(path)
        return table.to_pylist()
    if fmt in {"feather", "arrow", "ipc"}:
        try:
            import pyarrow.feather as feather  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "Reading feather/arrow files requires 'pyarrow'. Install it with 'pip install pyarrow'."
            ) from exc
        table = feather.read_table(path)
        return table.to_pylist()
    if fmt in {"json", "jsonl"}:
        text = path.read_text(encoding="utf-8")
        return ingest_utils.parse_json_records(text)
    if fmt == "pgn":
        text = path.read_text(encoding="utf-8")
        return ingest_utils.parse_pgn_records(text)
    if fmt == "csv":
        import csv

        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return [dict(row) for row in reader]
    raise ValueError(f"Unsupported dataset format: {fmt}")


def split_records(records: Sequence[Mapping[str, Any]], config: SplitConfig) -> Tuple[List[Mapping[str, Any]], List[Mapping[str, Any]]]:
    """Split records into train/validation sets."""

    records = list(records)
    if not records:
        raise ValueError("No records provided for training")

    rng = random.Random(config.random_seed)
    rng.shuffle(records)

    validation_size = int(len(records) * config.validation_fraction)
    validation_size = max(0, min(validation_size, len(records) - 1))
    train_size = len(records) - validation_size
    train_records = records[:train_size]
    validation_records = records[train_size:]
    logger.info(
        "Dataset split into %d training and %d validation records", len(train_records), len(validation_records)
    )
    return train_records, validation_records


def prepare_examples(
    records: Sequence[Mapping[str, Any]],
    feature: str,
    target: str,
    *,
    positive_label: Optional[str],
    negative_label: Optional[str],
    drop_unlabeled: bool = True,
    fail_if_empty: bool = True,
) -> List[Tuple[float, bool]]:
    """Convert raw mappings into ``(feature_value, label)`` pairs."""

    examples: List[Tuple[float, bool]] = []
    skipped = 0
    for record in records:
        if feature not in record:
            skipped += 1
            continue
        try:
            feature_value = float(record[feature])
        except (TypeError, ValueError):
            skipped += 1
            continue

        label_value = record.get(target)
        if label_value is None and drop_unlabeled:
            skipped += 1
            continue

        if positive_label is not None:
            is_positive = label_value == positive_label
        else:
            is_positive = bool(label_value)

        if negative_label is not None and label_value == negative_label:
            is_positive = False
        elif positive_label is not None and label_value != positive_label and drop_unlabeled:
            skipped += 1
            continue

        examples.append((feature_value, is_positive))

    if skipped:
        logger.warning("Skipped %d records due to missing features or labels", skipped)
    if not examples and fail_if_empty:
        raise ValueError("No usable training examples after preprocessing")
    return examples


def candidate_thresholds(values: Sequence[float]) -> List[float]:
    """Return a sorted list of threshold candidates covering the value range."""

    unique_values = sorted(set(values))
    if not unique_values:
        raise ValueError("Cannot build thresholds from an empty value set")
    eps = 1e-9
    if len(unique_values) == 1:
        value = unique_values[0]
        return [value - eps, value, value + eps]

    candidates: List[float] = [unique_values[0] - eps]
    candidates.extend(unique_values)
    for left, right in zip(unique_values, unique_values[1:]):
        candidates.append((left + right) / 2)
    candidates.append(unique_values[-1] + eps)
    return sorted(set(candidates))


def evaluate_threshold(
    examples: Sequence[Tuple[float, bool]],
    threshold: float,
    direction: str,
) -> Dict[str, float]:
    """Compute classification metrics for a single threshold."""

    tp = fp = tn = fn = 0
    for value, is_positive in examples:
        if direction == "lower-is-positive":
            predicted = value <= threshold
        elif direction == "higher-is-positive":
            predicted = value >= threshold
        else:
            raise ValueError(f"Unsupported direction: {direction}")

        if predicted and is_positive:
            tp += 1
        elif predicted and not is_positive:
            fp += 1
        elif not predicted and is_positive:
            fn += 1
        else:
            tn += 1

    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "threshold": threshold,
        "tp": float(tp),
        "fp": float(fp),
        "tn": float(tn),
        "fn": float(fn),
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "support_positive": float(tp + fn),
        "support_negative": float(tn + fp),
    }


def fit_threshold_model(
    examples: Sequence[Tuple[float, bool]],
    model_cfg: ModelConfig,
) -> Tuple[ThresholdModel, Dict[str, float]]:
    """Train a threshold model using ``examples``."""

    if model_cfg.model_type != "threshold":
        raise ValueError(f"Unsupported model type: {model_cfg.model_type}")

    values = [value for value, _ in examples]
    candidates = candidate_thresholds(values)

    best_metrics: Optional[Dict[str, float]] = None
    best_threshold: Optional[float] = None
    best_score = float("-inf")

    for threshold in candidates:
        metrics = evaluate_threshold(examples, threshold, model_cfg.direction)
        score = metrics.get(model_cfg.optimisation_metric, 0.0)
        if score > best_score or (score == best_score and best_threshold is not None and threshold < best_threshold):
            best_score = score
            best_metrics = metrics
            best_threshold = threshold

    if best_metrics is None or best_threshold is None:  # pragma: no cover - defensive guard
        raise RuntimeError("Failed to determine an optimal threshold")

    model = ThresholdModel(
        feature="",  # Placeholder, the caller sets the actual feature name
        threshold=best_threshold,
        direction=model_cfg.direction,
        positive_label=None,
    )
    return model, best_metrics


def train(config: TrainingConfig) -> TrainingResult:
    """Execute the training workflow based on ``config``."""

    logger.info("Loading records from %s", config.data.path)
    records = load_records(config.data.path, config.data.format)

    if not config.data.features:
        raise ValueError("No features specified in the training configuration")
    feature = config.data.features[0]
    train_records, validation_records = split_records(records, config.split)

    train_examples = prepare_examples(
        train_records,
        feature,
        config.data.target,
        positive_label=config.data.positive_label,
        negative_label=config.data.negative_label,
        drop_unlabeled=config.data.drop_unlabeled,
    )
    validation_examples = prepare_examples(
        validation_records,
        feature,
        config.data.target,
        positive_label=config.data.positive_label,
        negative_label=config.data.negative_label,
        drop_unlabeled=config.data.drop_unlabeled,
        fail_if_empty=False,
    )

    model, training_metrics = fit_threshold_model(train_examples, config.model)
    model.feature = feature
    model.positive_label = config.data.positive_label

    validation_metrics = evaluate_threshold(
        validation_examples, model.threshold, config.model.direction
    )

    artifacts_dir = config.artifacts.output_dir
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    model_artifact = {
        "model_type": config.model.model_type,
        "feature": model.feature,
        "threshold": model.threshold,
        "direction": model.direction,
        "positive_label": model.positive_label,
        "training_examples": len(train_examples),
        "validation_examples": len(validation_examples),
    }
    model_path = artifacts_dir / config.artifacts.model_filename
    model_path.write_text(json.dumps(model_artifact, indent=2), encoding="utf-8")
    logger.info("Persisted model artifact to %s", model_path)

    metrics_payload = {
        "train": training_metrics,
        "validation": validation_metrics,
    }
    metrics_path = artifacts_dir / config.artifacts.metrics_filename
    metrics_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")
    logger.info("Persisted metrics to %s", metrics_path)

    split_payload = {
        "training_records": len(train_records),
        "validation_records": len(validation_records),
        "random_seed": config.split.random_seed,
        "validation_fraction": config.split.validation_fraction,
    }
    split_path = artifacts_dir / config.artifacts.split_filename
    split_path.write_text(json.dumps(split_payload, indent=2), encoding="utf-8")

    logger.info(
        "Training complete. Threshold=%.4f, train %s=%.3f, validation %s=%.3f",
        model.threshold,
        config.model.optimisation_metric,
        training_metrics.get(config.model.optimisation_metric, 0.0),
        config.model.optimisation_metric,
        validation_metrics.get(config.model.optimisation_metric, 0.0),
    )

    return TrainingResult(
        model=model,
        train_metrics=training_metrics,
        validation_metrics=validation_metrics,
        model_path=model_path,
        metrics_path=metrics_path,
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the ChessGuard model")
    parser.add_argument("--config", type=Path, default=Path("configs/training.toml"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override the artifact output directory defined in the config",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> TrainingResult:
    args = parse_args(argv)
    config = load_training_config(args.config)
    if args.output_dir is not None:
        config.artifacts.output_dir = args.output_dir
    return train(config)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main()
