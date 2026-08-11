# -*- coding: utf-8 -*-
"""Elemen THEMATIC ACCURACY (Ketelitian Luas) - ISO 19157.

Menguji selisih luas bidang antara sistem KKP dan sertipikat:
    dL = |L_KKP - L_sertipikat|
Memenuhi toleransi bila:
    dL <= (1/2) * sqrt(L)          (PMNA/Kepala BPN No. 3 Tahun 1997)
Skor 1 bila memenuhi toleransi, 0 bila tidak.
"""

import math

from . import BaseAssessor
from ...models.schema import IKBResult, Parcel, QualityElement


def area_delta(area_kkp: float, area_cert: float) -> float:
    return abs(area_kkp - area_cert)


def area_tolerance(reference_area: float) -> float:
    """0.5 * sqrt(L)."""
    return 0.5 * math.sqrt(max(reference_area, 0.0))


class ThematicAccuracyAssessor(BaseAssessor):
    element = QualityElement.THEMATIC_ACCURACY

    def assess(self, parcel: Parcel, context: dict) -> IKBResult:
        if parcel.area_kkp is None or parcel.area_certificate is None:
            return IKBResult(self.element, 0.0, {"note": "area_missing"})

        dl = area_delta(parcel.area_kkp, parcel.area_certificate)
        ref = parcel.area_certificate or parcel.area_kkp
        tol = area_tolerance(ref)
        score = 1 if dl <= tol else 0

        return IKBResult(
            element=self.element,
            ikb_value=float(score),
            detail={"delta_luas_m2": round(dl, 4),
                    "toleransi_m2": round(tol, 4),
                    "memenuhi": bool(score)},
        )
