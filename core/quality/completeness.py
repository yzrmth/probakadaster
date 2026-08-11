# -*- coding: utf-8 -*-
"""Elemen COMPLETENESS (Kelengkapan) - ISO 19157.

Terdiri dari dua sub-elemen:
  * Omission  (IKB_co): data/atribut yang seharusnya ada namun tidak tersedia.
  * Commission (IKB_cc): data berlebih/tidak sesuai struktur (mis. data ganda
                         pada Nomor Hak, Nomor Surat Ukur, NIB).

Menggabungkan pula skor Kelengkapan Dokumen (KW1..KW6):
  KW1=6/6=1.00 ... KW6=1/6=0.17
"""

import pandas as pd

from . import BaseAssessor, ikb_from_scores
from ..data_loader import _parse_kw, flag_duplicates_master
from ...models.schema import IKBResult, Parcel, QualityElement, QualityScore

KW_VALUE = {1: 1.00, 2: 0.83, 3: 0.67, 4: 0.50, 5: 0.33, 6: 0.17}

# Kolom yang keberadaannya dicek untuk sub-elemen omission (Fase 1 - master Excel).
_REQUIRED_MASTER_ATTRS = ("Nomor_Hak", "Surat_Ukur", "NIB", "Luas")


def compute_completeness(df: pd.DataFrame) -> pd.DataFrame:
    """Hitung IKB Completeness per baris dari master table Excel (Fase 1).

    Omission   = rata-rata (Validator_Tekstual, Validator_Peta, kelengkapan
                 atribut wajib).
    Commission = rata-rata (tidak ganda Nomor_Hak, Surat_Ukur, NIB).
    KW         = KW_VALUE sesuai kolom 'KW'.
    IKB        = ((Omission + Commission) / 2 + KW) / 2.

    Mengembalikan df + kolom: ikb_omission, ikb_commission, kw_value,
    ikb_completeness. Murni pandas - tidak menyentuh QGIS.
    """
    out = flag_duplicates_master(df)

    attr_present = out[list(_REQUIRED_MASTER_ATTRS)].notna().all(axis=1).astype(float)
    omission = (out["Validator_Tekstual"].astype(float)
                + out["Validator_Peta"].astype(float)
                + attr_present) / 3.0

    commission = ((~out["dup_nomor_hak"]).astype(float)
                  + (~out["dup_surat_ukur"]).astype(float)
                  + (~out["dup_nib"]).astype(float)) / 3.0

    kw_value = out["KW"].map(lambda v: KW_VALUE.get(_parse_kw(v), 0.0))
    core = (omission + commission) / 2.0
    ikb = (core + kw_value) / 2.0

    out["ikb_omission"] = omission.round(4)
    out["ikb_commission"] = commission.round(4)
    out["kw_value"] = kw_value
    out["ikb_completeness"] = ikb.round(4)
    out["unsur_bermasalah"] = _flag_unsur_bermasalah(out)
    return out


# Label unsur per kondisi bermasalah: (kolom_flag, label, jenis).
_OMISSION_FLAGS = [
    ("Validator_Tekstual", "Validasi Tekstual", lambda v: not bool(v)),
    ("Validator_Peta", "Validasi Peta", lambda v: not bool(v)),
]
_COMMISSION_FLAGS = [
    ("dup_nomor_hak", "Nomor Hak (ganda)"),
    ("dup_surat_ukur", "Surat Ukur (ganda)"),
    ("dup_nib", "NIB (ganda)"),
]


def _flag_unsur_bermasalah(out: pd.DataFrame) -> pd.Series:
    """Daftar (dipisah koma) unsur/atribut yang belum lengkap (omission) atau
    berlebih/ganda (commission) per baris. Kosong bila tidak ada masalah."""
    def per_row(row):
        labels = [attr.replace("_", " ") for attr in _REQUIRED_MASTER_ATTRS
                  if pd.isna(row[attr])]
        labels += [label for col, label, is_bad in _OMISSION_FLAGS
                   if is_bad(row[col])]
        labels += [label for col, label in _COMMISSION_FLAGS if row[col]]
        return ", ".join(labels)

    return out.apply(per_row, axis=1)

# Atribut unik yang diperiksa untuk data ganda (commission).
UNIQUE_ATTRS = ("nomor_hak", "nomor_su", "nib")


class CompletenessAssessor(BaseAssessor):
    element = QualityElement.COMPLETENESS

    def assess(self, parcel: Parcel, context: dict) -> IKBResult:
        omission = self._omission(parcel)
        commission = self._commission(parcel, context)
        kw = self._kw_value(parcel)

        # Kelengkapan = rata-rata omission & commission, dipadukan skor dokumen KW.
        core = (omission + commission) / 2.0
        ikb = (core + kw) / 2.0 if parcel.kw_class else core

        return IKBResult(
            element=self.element,
            ikb_value=round(ikb, 4),
            detail={"ikb_omission": round(omission, 4),
                    "ikb_commission": round(commission, 4),
                    "kw_value": kw},
        )

    # -- sub-elemen -------------------------------------------------------- #
    def _omission(self, parcel: Parcel) -> float:
        """Skor 1 bila unsur tersedia & valid, 0 bila tidak (13 unsur wajib)."""
        scores = parcel.scores_of(self.element)
        omi = [s for s in scores if s.sub_element == "omission"]
        return ikb_from_scores(omi) if omi else 1.0

    def _commission(self, parcel: Parcel, context: dict) -> float:
        """Skor 1 bila TIDAK ada data ganda, 0 bila ada (per atribut unik)."""
        ganda = context.get("duplicate_flags", {}).get(parcel.parcel_id, {})
        vals = [0 if ganda.get(attr, False) else 1 for attr in UNIQUE_ATTRS]
        return sum(vals) / len(vals) if vals else 1.0

    def _kw_value(self, parcel: Parcel) -> float:
        return KW_VALUE.get(parcel.kw_class, 0.0)

    @staticmethod
    def make_omission_score(unit: str, available: bool) -> QualityScore:
        return QualityScore(QualityElement.COMPLETENESS, "omission", unit,
                            1 if available else 0)
