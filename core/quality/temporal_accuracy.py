# -*- coding: utf-8 -*-
"""Elemen TEMPORAL ACCURACY (Akurasi Waktu) - ISO 19157.

Dinilai berdasarkan usia data (tahun sejak penerbitan/pemutakhiran) dengan bobot
kualitas hasil AHP (pairwise comparison) dari judgement narasumber:

    < 5 tahun   -> Sangat Baik (0.313)
    5-10 tahun  -> Baik        (0.289)
    10-20 tahun -> Sedang      (0.224)
    > 20 tahun  -> Rendah      (0.174)

Bobot dinormalisasi ke rentang 0-1 (dibagi bobot maksimum) agar konsisten dgn IKB.
"""

from datetime import date

from . import BaseAssessor
from ...models.schema import IKBResult, Parcel, QualityElement

AGE_BANDS = [
    (5, 0.313, "Sangat Baik"),
    (10, 0.289, "Baik"),
    (20, 0.224, "Sedang"),
    (9999, 0.174, "Rendah"),
]
_MAX_W = max(w for _, w, _ in AGE_BANDS)


class TemporalAccuracyAssessor(BaseAssessor):
    element = QualityElement.TEMPORAL_ACCURACY

    def assess(self, parcel: Parcel, context: dict) -> IKBResult:
        year = self._issue_year(parcel)
        if year is None:
            return IKBResult(self.element, 0.0, {"note": "date_missing"})

        ref_year = context.get("reference_year", date.today().year)
        age = max(ref_year - year, 0)

        for max_year, weight, label in AGE_BANDS:
            if age <= max_year:
                ikb = weight / _MAX_W       # normalisasi 0-1
                return IKBResult(self.element, round(ikb, 4),
                                 {"usia_tahun": age, "kategori": label,
                                  "bobot_ahp": weight})
        return IKBResult(self.element, 0.0, {"usia_tahun": age})

    @staticmethod
    def _issue_year(parcel: Parcel):
        raw = parcel.attributes.get("tanggal_penerbitan")
        if raw is None:
            return None
        if isinstance(raw, date):
            return raw.year
        try:
            return int(str(raw)[:4])
        except (ValueError, TypeError):
            return None
