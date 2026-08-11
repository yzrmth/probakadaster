# -*- coding: utf-8 -*-
"""Test Fase 0: muat, bersihkan, deteksi duplikat master table DetailKW."""
from pathlib import Path

import pytest

from probakadaster.core.data_loader import (extract_tahun_su,
                                             flag_duplicates_master,
                                             join_master_spatial, load_master,
                                             master_quality_report)
from probakadaster.core.quality.completeness import compute_completeness

EXCEL_PATH = Path(__file__).parent / "test bahan" / "DetilKualitasData(7).xlsx"

pytestmark = pytest.mark.skipif(not EXCEL_PATH.exists(),
                                reason="data asli tidak tersedia")


def test_load_master_shape():
    df = load_master(EXCEL_PATH)
    assert df.shape[0] == 761
    assert "Tahun_SU" in df.columns


def test_tahun_su_parsing():
    assert extract_tahun_su("SU.00043/2013") == 2013
    assert extract_tahun_su("SU.00416/SAMUDA/2022") == 2022
    assert extract_tahun_su("GS.00480/1981") == 1981
    assert extract_tahun_su(None) is None

    df = load_master(EXCEL_PATH)
    assert df["Tahun_SU"].notna().sum() == 760


def test_duplicate_flags():
    df = load_master(EXCEL_PATH)
    flagged = flag_duplicates_master(df)
    assert flagged["nib_missing"].sum() == 1
    assert flagged["dup_nib"].sum() == 4          # 2 pasang NIB ganda
    assert df["NIB"].nunique() == 758
    assert len(df) - df["NIB"].nunique() == 3      # 1 kosong + 2 ganda


def test_quality_report():
    df = load_master(EXCEL_PATH)
    report = master_quality_report(df)
    assert report["total_baris"] == 761
    assert report["nib_kosong"] == 1
    assert report["nib_ganda_baris"] == 4
    assert report["tahun_su_terparse"] == 760
    assert report["belum_terpetakan"] == 101       # 761 - 660 ber-Luas_Peta


def test_join_spatial_noop_without_data():
    df = load_master(EXCEL_PATH)
    joined = join_master_spatial(df, spatial_records=None)
    assert joined.shape == df.shape


def test_join_spatial_matches_normalized_nib():
    df = load_master(EXCEL_PATH)
    joined = join_master_spatial(
        df, spatial_records=[{"NIB": "00049", "fid": 111},
                             {"NIB": "01085", "fid": 222}])
    matched = joined[joined["NIB"] == 49.0]["fid"]
    assert (matched == 111).all()
    unmatched = joined[joined["NIB"] == 3.0]["fid"]
    assert unmatched.isna().all()


def test_compute_completeness_duplicate_scores_low():
    df = load_master(EXCEL_PATH)
    res = compute_completeness(df)
    row = res[res["Nomor_Hak"] == "17.09.07.05.1.00050"].iloc[0]
    assert row["ikb_commission"] == 0.0          # ganda di NIB+Nomor_Hak+Surat_Ukur
    assert 0.0 <= row["ikb_completeness"] <= 1.0


def test_compute_completeness_range_and_missing_nib():
    df = load_master(EXCEL_PATH)
    res = compute_completeness(df)
    assert res["ikb_completeness"].between(0.0, 1.0).all()
    row = res[res["Nomor_Hak"] == "17.09.07.05.1.00051"].iloc[0]
    assert row["kw_value"] == 0.17                # KW6


def test_compute_completeness_flags_unsur_bermasalah():
    df = load_master(EXCEL_PATH)
    res = compute_completeness(df)
    row = res[res["Nomor_Hak"] == "17.09.07.05.1.00050"].iloc[0]
    assert "ganda" in row["unsur_bermasalah"]      # baris data ganda -> ditandai
    clean = res[res["ikb_omission"] == 1.0]
    if len(clean):
        assert clean.iloc[0]["unsur_bermasalah"] == ""
