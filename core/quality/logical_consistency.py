# -*- coding: utf-8 -*-
"""Elemen LOGICAL CONSISTENCY (Konsistensi Logis) - ISO 19157.

Dua sub-elemen utama:
  * Konsistensi Konseptual: kesesuaian jenis hak atas tanah terhadap fungsi
    kawasan/peruntukan ruang berdasarkan aturan yang dikelola lewat tab
    Pengaturan GUI (lihat `core/reference_layers.py`).
  * Konsistensi Topologi: bebas overlap, gap, self-intersection antar persil.

Skor biner S_ij (1 = konsisten/sesuai, 0 = tidak).
"""

from . import BaseAssessor, ikb_from_scores
from .. import reference_layers
from ...models.schema import IKBResult, Parcel, QualityElement

# Aturan konseptual saat ini: {slug: {label, file, atribut, jenis_hak_dilarang,
# catatan}}. Dicache di sini (bukan dibaca ulang tiap parcel); refresh lewat
# reload_rules() setelah GUI menambah/mengubah/menghapus aturan.
CONCEPTUAL_RULES = reference_layers.load_rules()


def reload_rules(rules_path: str = None) -> None:
    global CONCEPTUAL_RULES
    CONCEPTUAL_RULES = (reference_layers.load_rules(rules_path) if rules_path
                        else reference_layers.load_rules())


class LogicalConsistencyAssessor(BaseAssessor):
    element = QualityElement.LOGICAL_CONSISTENCY

    def assess(self, parcel: Parcel, context: dict) -> IKBResult:
        conceptual = self._conceptual(parcel, context)
        topology = self._topology(parcel, context)
        ikb = (conceptual + topology) / 2.0
        return IKBResult(
            element=self.element,
            ikb_value=round(ikb, 4),
            detail={"konsistensi_konseptual": round(conceptual, 4),
                    "konsistensi_topologi": round(topology, 4)},
        )

    def _conceptual(self, parcel: Parcel, context: dict) -> int:
        """1 bila jenis hak sesuai peruntukan kawasan, 0 bila melanggar."""
        overlays = context.get("kawasan_overlay", {}).get(parcel.parcel_id, [])
        hak = str(parcel.attributes.get("jenis_hak", "")).upper()
        for kawasan in overlays:
            forbidden = CONCEPTUAL_RULES.get(kawasan, {}).get("jenis_hak_dilarang", [])
            if "*" in forbidden or hak in forbidden:
                return 0
        return 1

    def _topology(self, parcel: Parcel, context: dict) -> int:
        """1 bila tidak ada error topologi (overlap/gap/self-intersect)."""
        errors = context.get("topology_errors", {}).get(parcel.parcel_id, [])
        return 0 if errors else 1
