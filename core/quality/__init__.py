# -*- coding: utf-8 -*-
"""Paket penilai (assessor) kualitas data per elemen ISO 19157."""

from abc import ABC, abstractmethod
from typing import List

from ...models.schema import IKBResult, Parcel, QualityElement, QualityScore


def ikb_from_scores(scores: List[QualityScore]) -> float:
    """Indeks Kelas Bidang (IKB) generik.

    IKB = (1 / sum_n) * sum(S_ij), yaitu rata-rata seluruh skor biner yang dinilai.
    Rentang 0-1; makin mendekati 1 makin baik/lengkap.
    """
    if not scores:
        return 0.0
    total = sum(s.value for s in scores)
    return total / len(scores)


class BaseAssessor(ABC):
    """Kontrak umum semua penilai elemen kualitas."""

    element: QualityElement = None

    @abstractmethod
    def assess(self, parcel: Parcel, context: dict) -> IKBResult:
        """Nilai satu bidang tanah, kembalikan IKBResult untuk elemen ini."""
        raise NotImplementedError


from .completeness import CompletenessAssessor           # noqa: E402
from .logical_consistency import LogicalConsistencyAssessor  # noqa: E402
from .positional_accuracy import PositionalAccuracyAssessor  # noqa: E402
from .thematic_accuracy import ThematicAccuracyAssessor   # noqa: E402
from .temporal_accuracy import TemporalAccuracyAssessor   # noqa: E402

ASSESSOR_REGISTRY = {
    QualityElement.COMPLETENESS: CompletenessAssessor,
    QualityElement.LOGICAL_CONSISTENCY: LogicalConsistencyAssessor,
    QualityElement.POSITIONAL_ACCURACY: PositionalAccuracyAssessor,
    QualityElement.THEMATIC_ACCURACY: ThematicAccuracyAssessor,
    QualityElement.TEMPORAL_ACCURACY: TemporalAccuracyAssessor,
}

__all__ = [
    "BaseAssessor", "ikb_from_scores", "ASSESSOR_REGISTRY",
    "CompletenessAssessor", "LogicalConsistencyAssessor",
    "PositionalAccuracyAssessor", "ThematicAccuracyAssessor",
    "TemporalAccuracyAssessor",
]
