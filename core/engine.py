# -*- coding: utf-8 -*-
"""Orkestrator utama: menjalankan seluruh alur penilaian kualitas -> ADQR.

Alur:
  load -> build_context -> assess tiap elemen -> hitung IKB -> ADQR
       -> klasifikasi Jenks (GVF) -> siap divisualisasikan.
"""

from typing import Dict, List

from .adqr_calculator import ADQRCalculator
from .classification import classify
from .data_loader import DataLoader
from .quality import ASSESSOR_REGISTRY
from ..models.schema import IKBResult, Parcel, QualityElement


class QualityEngine:
    def __init__(self, weights=None, field_map=None, progress_cb=None):
        self.loader = DataLoader(field_map)
        self.assessors = {el: cls() for el, cls in ASSESSOR_REGISTRY.items()}
        self.adqr = ADQRCalculator(weights=weights)
        self.progress_cb = progress_cb or (lambda pct, msg="": None)

    # ------------------------------------------------------------------ #
    def run(self, layer) -> Dict[str, object]:
        """Jalankan pipeline penuh, kembalikan ringkasan + list Parcel."""
        self.progress_cb(5, "Memuat data bidang tanah...")
        parcels: List[Parcel] = self.loader.load(layer)
        context = self.loader.build_context(layer, parcels, progress_cb=self.progress_cb)

        n = len(parcels) or 1
        for idx, parcel in enumerate(parcels, 1):
            pct = 10 + int(80 * idx / n)
            for element, assessor in self.assessors.items():
                label = element.value.replace("_", " ").title()
                self.progress_cb(pct, f"[INFO] Bidang {parcel.parcel_id}: menilai {label}...")
                try:
                    parcel.ikb[element] = assessor.assess(parcel, context)
                except Exception as exc:  # noqa: BLE001 - jangan hentikan seluruh batch
                    self.progress_cb(pct, f"[ERROR] Bidang {parcel.parcel_id} - {label}: {exc}")
                    parcel.ikb[element] = IKBResult(element, 0.0, {"note": f"error: {exc}"})
            parcel.adqr = self.adqr.compute(parcel)
            self.progress_cb(pct, f"[OK] Bidang {parcel.parcel_id} selesai (ADQR={parcel.adqr.adqr_value})")

        self.progress_cb(92, "Klasifikasi Natural Breaks (Jenks)...")
        adqr_values = [p.adqr.adqr_value for p in parcels if p.adqr]
        breaks, gvf = classify(adqr_values, n_classes=5) if adqr_values else ([], 0.0)

        self.progress_cb(100, "Selesai.")
        return {
            "parcels": parcels,
            "summary": self._summary(parcels, breaks, gvf),
        }

    # ------------------------------------------------------------------ #
    @staticmethod
    def _summary(parcels, breaks, gvf):
        vals = [p.adqr.adqr_value for p in parcels if p.adqr]
        if not vals:
            return {}
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / len(vals)
        dist = {}
        for p in parcels:
            cls = p.adqr.confidence_class.value
            dist[cls] = dist.get(cls, 0) + 1
        return {
            "count": len(vals),
            "mean_adqr": round(mean, 4),
            "min_adqr": round(min(vals), 4),
            "max_adqr": round(max(vals), 4),
            "std_sdam": round(variance ** 0.5, 4),
            "gvf": gvf,
            "jenks_breaks": [round(b, 4) for b in breaks],
            "distribution": dist,
        }
