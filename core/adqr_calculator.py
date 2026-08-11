# -*- coding: utf-8 -*-
"""Aggregate Data Quality Rating (ADQR).

Menjumlahkan seluruh IKB elemen kualitas dengan bobot eigenvector AHP:

    ADQR = (IKB_LC x Egv_LC) + (IKB_PA x Egv_PA) + (IKB_C x Egv_C)
         + (IKB_TH x Egv_TH) + (IKB_TE x Egv_TE)

Hasil 0-1: mendekati 1 = kualitas data sangat baik.
"""

import json
import os
from typing import Dict

from ..models.schema import (ADQRResult, ConfidenceClass, Parcel,
                             QualityElement)

_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "resources", "config")


def _load_json(name):
    with open(os.path.join(_CONFIG_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)


class ADQRCalculator:
    def __init__(self, weights: Dict[str, float] = None,
                 classification: dict = None):
        cfg = _load_json("ahp_weights.json")
        self.weights = weights or cfg["elements"]
        self.classification = classification or _load_json("classification.json")

    # ------------------------------------------------------------------ #
    def compute(self, parcel: Parcel) -> ADQRResult:
        """Hitung ADQR + klasifikasi confidence/buffer satu bidang."""
        w = self.weights
        breakdown, adqr = {}, 0.0
        key_map = {
            QualityElement.LOGICAL_CONSISTENCY: "logical",
            QualityElement.POSITIONAL_ACCURACY: "positional",
            QualityElement.COMPLETENESS: "completeness",
            QualityElement.THEMATIC_ACCURACY: "thematic",
            QualityElement.TEMPORAL_ACCURACY: "temporal",
        }
        for element, wkey in key_map.items():
            ikb = parcel.ikb.get(element)
            val = ikb.ikb_value if ikb else 0.0
            contribution = val * w.get(wkey, 0.0)
            adqr += contribution
            breakdown[wkey] = round(val, 4)

        adqr = round(min(max(adqr, 0.0), 1.0), 4)
        category = self._category(adqr)
        heat_cls = self._heatmap_class(adqr)
        pos_cls, buffer_m = self._positional_confidence(parcel, adqr)

        return ADQRResult(
            adqr_value=adqr,
            quality_category=category,
            confidence_class=heat_cls,
            positional_confidence=pos_cls,
            buffer_width_m=buffer_m,
            ikb_breakdown=breakdown,
        )

    # ------------------------------------------------------------------ #
    def _category(self, adqr: float) -> str:
        for band in self.classification["adqr_category"]:
            if band["min"] <= adqr < band["max"]:
                return band["label"]
        return "Sangat Rendah"

    def _heatmap_class(self, adqr: float) -> ConfidenceClass:
        for band in self.classification["adqr_confidence_heatmap"]:
            if band["min"] <= adqr < band["max"]:
                return ConfidenceClass(band["class"])
        return ConfidenceClass.VERY_LOW

    def _positional_confidence(self, parcel: Parcel, adqr: float):
        """Lebar buffer ditentukan dari positional accuracy bila ada, jika tidak
        gunakan ADQR sebagai proksi."""
        pa = parcel.ikb.get(QualityElement.POSITIONAL_ACCURACY)
        driver = pa.ikb_value if pa else adqr
        for band in self.classification["positional_confidence"]:
            if band["min"] <= driver < band["max"]:
                return ConfidenceClass(band["class"]), band["buffer_m"]
        return ConfidenceClass.VERY_LOW, 3.00
