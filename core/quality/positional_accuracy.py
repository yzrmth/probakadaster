# -*- coding: utf-8 -*-
"""Elemen POSITIONAL ACCURACY (Akurasi Posisi) - ISO 19157.

Membandingkan geometri bidang uji (KKP) terhadap data referensi (ortofoto)
dengan tiga metrik:
  1. Circularity Ratio   CR = 4*pi*L / K^2   (L=luas, K=keliling); mendekati 1 = mirip.
  2. Near Distance       jarak centroid uji-referensi; mendekati 0 = akurat.
  3. Polygon Area        dA = |A_u - A_r|; makin kecil = makin akurat.

Signifikansi diuji dengan uji-z beda rata-rata:
    z = (x_bar - mu) / (s / sqrt(n))
Ukuran sampel memakai rumus Slovin: n = N / (1 + N*e^2).
"""

import math

from . import BaseAssessor
from ...models.schema import IKBResult, Parcel, QualityElement


def circularity_ratio(area: float, perimeter: float) -> float:
    """CR = 4*pi*A / P^2. Lingkaran sempurna -> 1."""
    if perimeter <= 0:
        return 0.0
    return (4.0 * math.pi * area) / (perimeter ** 2)


def near_distance(centroid_u, centroid_r) -> float:
    """Jarak Euclidean antar centroid (x,y)."""
    return math.hypot(centroid_u[0] - centroid_r[0], centroid_u[1] - centroid_r[1])


def area_difference(area_u: float, area_r: float) -> float:
    return abs(area_u - area_r)


def slovin_sample_size(population: int, error: float = 0.10) -> int:
    """n = N / (1 + N e^2)."""
    if population <= 0:
        return 0
    return math.ceil(population / (1.0 + population * error ** 2))


def z_test(sample_mean: float, expected: float, std: float, n: int) -> float:
    """z = (x_bar - mu) / (s / sqrt(n)). Return 0 bila std/n tak valid."""
    if std <= 0 or n <= 0:
        return 0.0
    return (sample_mean - expected) / (std / math.sqrt(n))


class PositionalAccuracyAssessor(BaseAssessor):
    element = QualityElement.POSITIONAL_ACCURACY

    # ambang skor -> boleh dikonfigurasi
    CR_MIN = 0.60          # bentuk cukup mirip
    NEAR_MAX = 0.50        # meter, batas geseran centroid dianggap akurat
    Z_CRITICAL = 1.96      # alpha 0.05 dua sisi

    def assess(self, parcel: Parcel, context: dict) -> IKBResult:
        ref = context.get("reference", {}).get(parcel.parcel_id)
        if not ref:
            # tanpa referensi -> tidak dapat dinilai; skor konservatif 0.
            return IKBResult(self.element, 0.0, {"note": "no_reference"})

        cr = circularity_ratio(ref["area_u"], ref["perimeter_u"])
        nd = near_distance(ref["centroid_u"], ref["centroid_r"])
        da = area_difference(ref["area_u"], ref["area_r"])

        z = z_test(ref.get("sample_mean", nd), 0.0,
                   ref.get("std", 1.0), ref.get("n", 1))
        consistent = abs(z) <= self.Z_CRITICAL

        # Skor gabungan biner sederhana (tiap metrik menyumbang 1 poin).
        s_cr = 1 if cr >= self.CR_MIN else 0
        s_nd = 1 if nd <= self.NEAR_MAX else 0
        s_z = 1 if consistent else 0
        ikb = (s_cr + s_nd + s_z) / 3.0

        return IKBResult(
            element=self.element,
            ikb_value=round(ikb, 4),
            detail={"circularity_ratio": round(cr, 4),
                    "near_distance_m": round(nd, 4),
                    "area_diff_m2": round(da, 4),
                    "z_value": round(z, 4),
                    "consistent": consistent},
        )
