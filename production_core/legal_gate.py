"""Legal gates for high-risk monitoring features."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .identity import new_id


class GatedFeature(str, Enum):
    SCREENSHOT_STREAMING = "screenshot_streaming"
    FILE_SYSTEM_SURVEILLANCE = "file_system_surveillance"
    ML_RISK_SCORING = "ml_risk_scoring"
    REMOTE_COMMANDS = "remote_commands"


@dataclass(frozen=True)
class LegalReview:
    id: str
    tenant_id: str
    feature: GatedFeature
    reviewer_id: str
    reviewed_at: datetime
    reference: str


class FeatureGate:
    def __init__(self) -> None:
        self.reviews: dict[tuple[str, GatedFeature], LegalReview] = {}

    def record_review(
        self,
        feature: GatedFeature,
        tenant_id: str,
        reviewer_id: str,
        reviewed_at: datetime,
        reference: str,
    ) -> LegalReview:
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        review = LegalReview(
            id=new_id(),
            tenant_id=tenant_id,
            feature=feature,
            reviewer_id=reviewer_id,
            reviewed_at=reviewed_at,
            reference=reference,
        )
        self.reviews[(tenant_id, feature)] = review
        return review

    def is_allowed(self, feature: GatedFeature, tenant_id: str) -> bool:
        return (tenant_id, feature) in self.reviews

    def require_allowed(self, feature: GatedFeature, tenant_id: str) -> None:
        if not self.is_allowed(feature, tenant_id=tenant_id):
            raise PermissionError(f"{feature.value} is blocked for tenant {tenant_id} until legal review is recorded")
