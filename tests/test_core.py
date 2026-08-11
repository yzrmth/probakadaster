# -*- coding: utf-8 -*-
"""Unit test logika inti (berjalan tanpa QGIS)."""
import math
from probakadaster.core.ahp import AHPCalculator
from probakadaster.core.classification import classify, jenks_breaks
from probakadaster.core.adqr_calculator import ADQRCalculator
from probakadaster.core.quality.thematic_accuracy import area_tolerance, area_delta
from probakadaster.core.quality.positional_accuracy import (
    circularity_ratio, slovin_sample_size)
from probakadaster.core.quality import ASSESSOR_REGISTRY
from probakadaster.models.schema import Parcel, QualityElement


def test_ahp_perfectly_consistent():
    m = [[1, 3, 5], [1/3, 1, 3], [1/5, 1/3, 1]]
    r = AHPCalculator().compute(m)
    assert abs(sum(r.weights) - 1.0) < 1e-9
    assert r.cr <= 0.10 and r.consistent


def test_jenks_and_gvf():
    vals = [0.1, 0.2, 0.25, 0.5, 0.55, 0.6, 0.8, 0.82, 0.9, 0.95]
    breaks, gvf = classify(vals, 5)
    assert breaks[0] == min(vals) and breaks[-1] == max(vals)
    assert 0.0 <= gvf <= 1.0


def test_thematic_tolerance():
    assert area_tolerance(100.0) == 0.5 * math.sqrt(100.0)  # = 5.0
    assert area_delta(1000, 1004) == 4


def test_positional_helpers():
    assert circularity_ratio(0, 10) == 0.0
    assert slovin_sample_size(100, 0.1) == 50


def test_full_parcel_adqr():
    p = Parcel(parcel_id="X", fid=1, area_kkp=1000.0,
               area_certificate=1002.0, kw_class=1)
    p.attributes = {"jenis_hak": "HM", "tanggal_penerbitan": "2024-01-01"}
    ctx = {"duplicate_flags": {}, "kawasan_overlay": {}, "topology_errors": {},
           "reference": {}, "reference_year": 2026}
    for el, cls in ASSESSOR_REGISTRY.items():
        p.ikb[el] = cls().assess(p, ctx)
    res = ADQRCalculator().compute(p)
    assert 0.0 <= res.adqr_value <= 1.0
    assert res.quality_category
    assert res.buffer_width_m in (0.25, 0.5, 1.0, 2.0, 3.0)
