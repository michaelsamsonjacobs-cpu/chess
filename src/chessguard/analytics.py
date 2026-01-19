"""Risk scoring and explanation utilities."""

from __future__ import annotations

from typing import Dict, Tuple

from .models import LivePGNSubmission, ModelExplanation, RiskAssessment


class RiskEngine:
    """Simple heuristic engine that emulates a suspicious-move detector."""

    def assess(self, submission: LivePGNSubmission) -> Tuple[RiskAssessment, ModelExplanation]:
        features = self._extract_features(submission)

        base_score = 25.0
        contributions: Dict[str, float] = {}

        # High engine agreement strongly increases suspicion.
        engine_agreement = features["engine_agreement"]
        contributions["engine_agreement"] = engine_agreement * 35.0

        # Low ACPL indicates precision similar to engine play.
        if features["average_centipawn_loss"] is not None:
            acpl = features["average_centipawn_loss"]
            contributions["average_centipawn_loss"] = max(0.0, (45 - acpl) / 45) * 25.0
        else:
            contributions["average_centipawn_loss"] = 0.0

        # Time anomalies (consistent move times in critical positions).
        contributions["time_anomalies"] = min(features["time_anomalies"] * 8.0, 20.0)

        # Historical context.
        contributions["prior_flags"] = min(features["prior_flags"] * 10.0, 25.0)

        # PGN annotations.
        contributions["brilliancies"] = features["brilliancies"] * 1.5
        contributions["blunders"] = -min(features["blunders"] * 2.5, 15.0)

        raw_score = base_score + sum(contributions.values())
        score = max(0.0, min(100.0, raw_score))

        tier = self._determine_tier(score)
        recommended = self._recommended_actions(tier)

        explanation = ModelExplanation(
            summary=self._build_summary(score, tier, features),
            top_factors=self._format_factors(contributions, features),
        )
        assessment = RiskAssessment(
            score=score,
            tier=tier,
            recommended_actions=recommended,
        )
        return assessment, explanation

    # ------------------------------------------------------------------
    # Feature engineering helpers
    # ------------------------------------------------------------------
    def _extract_features(self, submission: LivePGNSubmission) -> Dict[str, float]:
        metadata = submission.metadata or {}
        pgn = submission.pgn

        brilliancies = pgn.count("!!") + pgn.count(" !")
        blunders = pgn.count("??") + metadata.get("reported_blunders", 0)

        engine_agreement = float(metadata.get("engine_agreement", 0.0))
        if engine_agreement > 1:
            engine_agreement = engine_agreement / 100.0

        acpl = metadata.get("average_centipawn_loss")
        if acpl is not None:
            acpl = float(acpl)

        time_anomalies = float(metadata.get("time_anomalies", 0.0))
        prior_flags = float(metadata.get("prior_flags", 0.0))

        return {
            "engine_agreement": engine_agreement,
            "average_centipawn_loss": acpl,
            "time_anomalies": time_anomalies,
            "prior_flags": prior_flags,
            "brilliancies": float(brilliancies),
            "blunders": float(blunders),
        }

    def _determine_tier(self, score: float) -> str:
        if score >= 85:
            return "Critical"
        if score >= 70:
            return "High"
        if score >= 50:
            return "Medium"
        return "Low"

    def _recommended_actions(self, tier: str) -> list[str]:
        if tier == "Critical":
            return [
                "Notify chief arbiter immediately",
                "Escort player for interview",
                "Isolate playing device and gather logs",
            ]
        if tier == "High":
            return [
                "Initiate secondary fair-play review",
                "Collect player's device for inspection",
            ]
        if tier == "Medium":
            return [
                "Increase live monitoring",
                "Schedule follow-up analysis after round",
            ]
        return ["Continue monitoring"]

    def _build_summary(self, score: float, tier: str, features: Dict[str, float]) -> str:
        snippets = [
            f"Score {score:.1f} ({tier})",
            f"Engine agreement {features['engine_agreement']:.0%}",
        ]
        acpl = features.get("average_centipawn_loss")
        if acpl is not None:
            snippets.append(f"ACPL {acpl:.1f}")
        if features.get("time_anomalies", 0.0) > 0:
            snippets.append(
                f"{features['time_anomalies']:.0f} anomalous time clusters detected"
            )
        return ", ".join(snippets)

    def _format_factors(
        self, contributions: Dict[str, float], features: Dict[str, float]
    ) -> list[Dict[str, float | str]]:
        factor_names = {
            "engine_agreement": "Engine move agreement",
            "average_centipawn_loss": "Average centipawn loss",
            "time_anomalies": "Timing anomalies",
            "prior_flags": "Historical flags",
            "brilliancies": "Annotated brilliancies",
            "blunders": "Blunders",
        }
        formatted = []
        for key, value in contributions.items():
            formatted.append(
                {
                    "feature": factor_names.get(key, key),
                    "score_contribution": round(value, 2),
                    "raw_value": features.get(key),
                }
            )
        return formatted
