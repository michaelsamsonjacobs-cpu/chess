"""Services for aggregating profile-level analytics."""

from __future__ import annotations

from typing import List

from ..repositories import AppRepositories
from ..schemas.common import RiskFlag
from ..schemas.profile import ProfileAnalytics, ProfileIngestRequest, ProfileReport
from ..utils.statistics import linear_regression_slope, normalized_score, safe_mean


class ProfileService:
    """Service responsible for profile ingestion and analytics."""

    def __init__(self, repositories: AppRepositories) -> None:
        self._repositories = repositories

    def ingest_profile(self, request: ProfileIngestRequest) -> ProfileAnalytics:
        """Aggregate analytics for a profile across its recent games."""

        game_records = []
        for reference in request.recent_games:
            try:
                game_records.append(self._repositories.games.get(reference.game_id))
            except KeyError:
                # Skip references that are not yet ingested; datasets might still be pending.
                continue

        suspicion_scores = [record.analysis.suspicion_score for record in game_records]
        engine_rates = [record.analysis.features.engine_match_rate_top1 for record in game_records]
        rt_variances = [record.analysis.features.log_normal_rt_variance for record in game_records]
        avg_reaction_times = [record.analysis.features.average_reaction_time for record in game_records]

        aggregate_engine_match = safe_mean(engine_rates)
        suspicious_game_ratio = 0.0
        if game_records:
            suspicious_game_ratio = sum(score > 0.75 for score in suspicion_scores) / len(game_records)

        reported_rating = safe_mean(request.ratings.values()) if request.ratings else 0.0
        inferred_strength = 800.0 + aggregate_engine_match * 1200.0
        rating_gap = abs(inferred_strength - reported_rating)
        rating_anomaly = normalized_score(rating_gap, low=0.0, high=600.0)

        activity_burst_index = self._compute_activity_index(request)
        psych_consistency = 1.0 - normalized_score(safe_mean(rt_variances), low=0.01, high=0.6)

        fatigue_drift = 0.0
        if len(avg_reaction_times) >= 2:
            fatigue_drift = linear_regression_slope(list(range(len(avg_reaction_times))), avg_reaction_times)

        tilt_drift = 0.0
        if suspicion_scores:
            first_half = suspicion_scores[: max(1, len(suspicion_scores) // 2)]
            second_half = suspicion_scores[max(1, len(suspicion_scores) // 2) :]
            tilt_drift = safe_mean(second_half) - safe_mean(first_half)

        risk_score = min(
            1.0,
            max(
                0.0,
                0.45 * aggregate_engine_match
                + 0.25 * suspicious_game_ratio
                + 0.15 * psych_consistency
                + 0.15 * rating_anomaly,
            ),
        )

        flags: List[RiskFlag] = []
        if suspicious_game_ratio > 0.3 and len(game_records) >= 5:
            flags.append(
                RiskFlag(
                    code="multiple_suspicious_games",
                    message="More than 30% of recent games exceed suspicion threshold.",
                    severity="high",
                )
            )
        if rating_anomaly > 0.5 and request.ratings:
            flags.append(
                RiskFlag(
                    code="rating_jump",
                    message="Reported rating deviates strongly from inferred strength.",
                    severity="medium",
                )
            )
        if psych_consistency < 0.4 and avg_reaction_times:
            flags.append(
                RiskFlag(
                    code="psych_variability",
                    message="Psychological timing patterns vary substantially across games.",
                    severity="medium",
                )
            )

        analytics = ProfileAnalytics(
            profile_id=request.profile_id,
            platform=request.platform,
            risk_score=risk_score,
            rating_anomaly=rating_anomaly,
            activity_burst_index=activity_burst_index,
            fatigue_drift=fatigue_drift,
            tilt_drift=tilt_drift,
            psych_consistency=psych_consistency,
            aggregate_engine_match=aggregate_engine_match,
            game_count=len(game_records),
            suspicious_game_ratio=suspicious_game_ratio,
            flags=flags,
        )

        self._repositories.profiles.create(request, analytics)
        return analytics

    def get_report(self, profile_id: str) -> ProfileReport:
        """Fetch a stored profile report."""

        record = self._repositories.profiles.get(profile_id)
        summary = (
            f"Risk score {record.analytics.risk_score:.2f}; suspicious game ratio "
            f"{record.analytics.suspicious_game_ratio:.2%} with aggregate engine match "
            f"{record.analytics.aggregate_engine_match:.2f}."
        )
        return ProfileReport(analytics=record.analytics, summary=summary)

    def _compute_activity_index(self, request: ProfileIngestRequest) -> float:
        """Estimate how bursty the activity history is."""

        if not request.total_games:
            return 0.0

        active_days = self._estimate_active_days(request)
        games_per_day = request.total_games / max(active_days, 1)
        return normalized_score(games_per_day, low=0.2, high=8.0)

    def _estimate_active_days(self, request: ProfileIngestRequest) -> int:
        if request.join_date and request.last_active and request.last_active >= request.join_date:
            return (request.last_active - request.join_date).days + 1
        # Fallback heuristic using provided metadata.
        return int(request.metadata.get("estimated_active_days", 30))

