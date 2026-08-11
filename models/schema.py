# -*- coding: utf-8 -*-
"""Model domain plugin: representasi bidang tanah, skor kualitas, dan hasil ADQR.

Model ini adalah *plain data object* (tidak bergantung QGIS) supaya mudah diuji
unit dan dipisahkan dari lapisan GIS.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class QualityElement(str, Enum):
    """5 elemen kualitas data ISO 19157 yang dipakai untuk ADQR."""
    COMPLETENESS = "completeness"          # IKB_C
    LOGICAL_CONSISTENCY = "logical"        # IKB_LC
    POSITIONAL_ACCURACY = "positional"     # IKB_PA
    THEMATIC_ACCURACY = "thematic"         # IKB_TH
    TEMPORAL_ACCURACY = "temporal"         # IKB_TE


class ConfidenceClass(str, Enum):
    """Kelas kepercayaan hasil klasifikasi ADQR / positional accuracy."""
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


# 13 unsur wajib (7 fisik + 6 yuridis efektif) mengikuti Permen ATR/BPN 3/2023.
FISIK_UNITS = ["A1", "A2", "A3", "A4", "A5", "A6", "A7"]
YURIDIS_UNITS = ["B1", "B2", "B3", "B4", "B5", "B6", "B7"]


@dataclass
class QualityScore:
    """Skor biner S_ij satu sub-elemen kualitas untuk satu unsur data.

    S_ij bernilai 1 (valid/sesuai) atau 0 (tidak valid/tidak sesuai).
    """
    element: QualityElement
    sub_element: str          # mis. "commission", "omission", "konsistensi_topologi"
    unit: str                 # mis. "A1".."A7", "B1".."B7"
    value: int                # 0 atau 1


@dataclass
class IKBResult:
    """Indeks Kelas Bidang untuk satu elemen kualitas (rentang 0-1)."""
    element: QualityElement
    ikb_value: float
    detail: Dict[str, float] = field(default_factory=dict)


@dataclass
class ADQRResult:
    """Hasil agregasi ADQR sebuah bidang tanah."""
    adqr_value: float                       # 0-1
    quality_category: str                   # Sangat Baik .. Sangat Rendah
    confidence_class: ConfidenceClass       # untuk heatmap
    positional_confidence: ConfidenceClass  # untuk buffer
    buffer_width_m: float                   # lebar buffer (meter)
    ikb_breakdown: Dict[str, float] = field(default_factory=dict)


@dataclass
class Parcel:
    """Representasi satu bidang tanah (feature vektor)."""
    parcel_id: str                          # NIB / feature id
    fid: int                                # feature id internal layer
    area_kkp: Optional[float] = None        # luas dari sistem KKP (m2)
    area_certificate: Optional[float] = None  # luas dari sertipikat (m2)
    kw_class: Optional[int] = None          # 1..6 (KW1..KW6)
    attributes: Dict[str, object] = field(default_factory=dict)

    scores: List[QualityScore] = field(default_factory=list)
    ikb: Dict[QualityElement, IKBResult] = field(default_factory=dict)
    adqr: Optional[ADQRResult] = None

    def scores_of(self, element: QualityElement) -> List[QualityScore]:
        return [s for s in self.scores if s.element == element]
