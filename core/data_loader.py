# -*- coding: utf-8 -*-
"""Pemuat & validator data bidang tanah dari layer vektor QGIS (sumber KKP ATR/BPN).

Bertanggung jawab:
  * memetakan kolom layer -> field standar plugin,
  * membangun objek Parcel,
  * menyiapkan konteks (duplikat atribut, overlay kawasan, error topologi)
    yang dipakai para assessor.

Modul ini juga memuat *master table* tekstual (Excel `DetailKW`) yang jadi
sumber utama Fase 0-2 - murni pandas, tidak menyentuh QGIS sama sekali agar
bisa dites dan dijalankan lewat CLI tanpa membuka QGIS.
"""

import re

import pandas as pd

from . import reference_layers
from ..models.schema import Parcel

# Kolom wajib pada sheet DetailKW (lihat dokumen data asli).
MASTER_REQUIRED_COLUMNS = (
    "Nomor_Hak", "Surat_Ukur", "NIB", "Luas", "Produk", "Luas_Peta",
    "Validator_Tekstual", "Validator_Peta", "Blokir_Internal", "KW",
    "Pemilik_Pertama", "Pemilik_Akhir", "Tipe_Hak",
)

_TAHUN_SU_RE = re.compile(r"(\d{4})\s*$")


def extract_tahun_su(surat_ukur):
    """Ambil tahun (4 digit di akhir) dari nomor Surat Ukur.

    Contoh: 'SU.00043/2013' -> 2013, 'SU.00416/SAMUDA/2022' -> 2022.
    Mengembalikan None bila kosong/tidak ada 4 digit di akhir.
    """
    if pd.isna(surat_ukur):
        return None
    m = _TAHUN_SU_RE.search(str(surat_ukur).strip())
    return int(m.group(1)) if m else None


def load_master(path, sheet_name="DetailKW") -> pd.DataFrame:
    """Baca sheet DetailKW dari Excel & tambahkan kolom Tahun_SU.

    Tidak memodifikasi file asal. Kolom wajib divalidasi keberadaannya agar
    kesalahan sheet/format ketahuan lebih awal daripada gagal di tengah
    penilaian.
    """
    df = pd.read_excel(path, sheet_name=sheet_name)
    missing = [c for c in MASTER_REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Kolom wajib tidak ditemukan pada '{sheet_name}': {missing}")
    df["Tahun_SU"] = df["Surat_Ukur"].apply(extract_tahun_su)
    return df


def flag_duplicates_master(df: pd.DataFrame) -> pd.DataFrame:
    """Tandai baris dengan NIB kosong & data ganda (NIB/Nomor_Hak/Surat_Ukur).

    * nib_missing   : NIB tidak terisi.
    * dup_nib       : NIB terisi tapi dipakai >1 baris (bukan data ganda bila kosong).
    * dup_nomor_hak : Nomor_Hak dipakai >1 baris.
    * dup_surat_ukur: Surat_Ukur dipakai >1 baris.
    """
    out = df.copy()
    out["nib_missing"] = out["NIB"].isna()
    out["dup_nib"] = (~out["nib_missing"]) & out["NIB"].duplicated(keep=False)
    out["dup_nomor_hak"] = out["Nomor_Hak"].duplicated(keep=False)
    out["dup_surat_ukur"] = out["Surat_Ukur"].notna() & out["Surat_Ukur"].duplicated(keep=False)
    return out


def master_quality_report(df: pd.DataFrame) -> dict:
    """Ringkasan kualitas join/pembersihan master table (untuk log & CLI)."""
    flagged = flag_duplicates_master(df)
    return {
        "total_baris": len(df),
        "nib_unik": int(df["NIB"].nunique()),
        "nib_kosong": int(flagged["nib_missing"].sum()),
        "nib_ganda_baris": int(flagged["dup_nib"].sum()),
        "nomor_hak_ganda_baris": int(flagged["dup_nomor_hak"].sum()),
        "surat_ukur_ganda_baris": int(flagged["dup_surat_ukur"].sum()),
        "tahun_su_terparse": int(df["Tahun_SU"].notna().sum()),
        "belum_terpetakan": int(df["Luas_Peta"].isna().sum()),
    }


def extract_layer_nib(layer, nib_field="NIB"):
    """Baca kolom NIB & fid dari layer vektor (duck-typed, tanpa `import qgis`).

    Dipakai untuk join master Excel <-> layer spasial via NIB. `layer` cukup
    punya `.fields()` dan `.getFeatures()` seperti QgsVectorLayer.
    """
    available = [f.name() for f in layer.fields()]
    if nib_field not in available:
        raise ValueError(f"Field '{nib_field}' tidak ditemukan pada layer "
                         f"(field tersedia: {available})")
    return [{"NIB": feat[nib_field], "fid": feat.id()} for feat in layer.getFeatures()]


def _normalize_nib(value):
    """Normalisasi NIB ke string 5 digit (format layer spasial, mis. '00049').

    Excel menyimpan NIB sebagai angka (49.0), layer spasial sebagai teks
    berpadding-nol ('00049') - disamakan di sini agar join tidak meleset.
    """
    if pd.isna(value):
        return None
    try:
        return f"{int(float(value)):05d}"
    except (TypeError, ValueError):
        return str(value).strip() or None


def join_master_spatial(master_df: pd.DataFrame, spatial_records=None) -> pd.DataFrame:
    """Gabungkan master table ke data spasial via NIB (dinormalisasi 5 digit).

    `spatial_records` bisa berupa DataFrame/list[dict] berkolom 'NIB' (mis.
    hasil `extract_layer_nib()` di plugin, atau geopandas di CLI). Bila None
    (default), join belum dilakukan - master_df dikembalikan apa adanya
    sehingga Fase 0 tetap bisa berjalan tanpa data spasial.
    """
    if spatial_records is None:
        return master_df.copy()
    spatial_df = (spatial_records if isinstance(spatial_records, pd.DataFrame)
                  else pd.DataFrame(spatial_records)).copy()

    out = master_df.copy()
    out["_nib_key"] = out["NIB"].apply(_normalize_nib)
    spatial_df["_nib_key"] = spatial_df["NIB"].apply(_normalize_nib)
    merged = out.merge(spatial_df.drop(columns=["NIB"]), on="_nib_key", how="left",
                       suffixes=("", "_spatial"))
    return merged.drop(columns=["_nib_key"])

# Pemetaan default nama field layer -> field internal. Dapat dioverride via GUI.
DEFAULT_FIELD_MAP = {
    "parcel_id": "nib",
    "area_kkp": "luas_kkp",
    "area_certificate": "luas_su",
    "kw_class": "kw",
    "jenis_hak": "jenis_hak",
    "nomor_hak": "no_hak",
    "nomor_su": "no_su",
    "tanggal_penerbitan": "tgl_terbit",
}


class DataLoader:
    def __init__(self, field_map=None):
        self.field_map = field_map or DEFAULT_FIELD_MAP

    # ------------------------------------------------------------------ #
    def load(self, layer):
        """Kembalikan list[Parcel] dari QgsVectorLayer."""
        parcels = []
        fmap = self.field_map
        available = [f.name() for f in layer.fields()] if hasattr(layer, "fields") else []

        for feat in layer.getFeatures():
            attrs = {name: feat[fmap[name]]
                     for name in fmap
                     if fmap.get(name) in available}
            kw_raw = attrs.get("kw_class")
            parcel = Parcel(
                parcel_id=str(attrs.get("parcel_id", feat.id())),
                fid=feat.id(),
                area_kkp=_to_float(attrs.get("area_kkp")),
                area_certificate=_to_float(attrs.get("area_certificate")),
                kw_class=_parse_kw(kw_raw),
                attributes=attrs,
            )
            parcels.append(parcel)
        return parcels

    # ------------------------------------------------------------------ #
    def build_context(self, layer, parcels, progress_cb=None):
        """Siapkan konteks penilaian (duplikat, kawasan, topologi).

        Overlay kawasan dibaca dari file di resources/reference_layers/ (lihat
        `reference_layers.py`) - tidak perlu layer referensi dimuat manual ke
        QGIS. Topologi belum diimplementasikan (kerangka kosong/aman).
        """
        progress_cb = progress_cb or (lambda pct, msg="": None)
        discovered = reference_layers.discover_reference_files()
        found = sorted(k for k, v in discovered.items() if v)
        missing = sorted(k for k, v in discovered.items() if not v)
        progress_cb(8, f"[INFO] Referensi kawasan ditemukan: {found or '-'} "
                       f"| tidak ada: {missing or '-'}.")
        kawasan_overlay = (reference_layers.build_kawasan_overlay(layer, parcels, discovered)
                           if reference_layers.QGIS_AVAILABLE else {})

        return {
            "duplicate_flags": self._detect_duplicates(parcels),
            "kawasan_overlay": kawasan_overlay,
            "topology_errors": {},      # diisi hasil cek topologi
            "reference": {},            # diisi hasil interpretasi ortofoto
            "reference_year": None,
        }

    @staticmethod
    def _detect_duplicates(parcels):
        flags, seen = {}, {"nomor_hak": {}, "nomor_su": {}, "nib": {}}
        for p in parcels:
            flags[p.parcel_id] = {}
            for attr in ("nomor_hak", "nomor_su"):
                val = p.attributes.get(attr)
                if val in seen[attr]:
                    flags[p.parcel_id][attr] = True
                    flags[seen[attr][val]][attr] = True
                elif val is not None:
                    seen[attr][val] = p.parcel_id
            if p.parcel_id in seen["nib"]:
                flags[p.parcel_id]["nib"] = True
            seen["nib"][p.parcel_id] = p.parcel_id
        return flags


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_kw(v):
    """Terima 'KW1'/'1'/1 -> int 1..6."""
    if v is None:
        return None
    s = str(v).upper().replace("KW", "").strip()
    try:
        k = int(float(s))
        return k if 1 <= k <= 6 else None
    except (TypeError, ValueError):
        return None
