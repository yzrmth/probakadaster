# -*- coding: utf-8 -*-
"""Unit test aturan referensi kawasan (berjalan tanpa QGIS)."""
import json
import os
import tempfile

from probakadaster.core.reference_layers import (discover_reference_files,
                                                  load_rules, read_field_names,
                                                  remove_rule, save_reference_file,
                                                  slugify, unique_slug, upsert_rule)
from probakadaster.core.quality import logical_consistency


def test_load_rules_empty_by_default():
    assert logical_consistency.CONCEPTUAL_RULES == {}   # conceptual_rules.json mulai kosong


def test_load_rules_strips_comment():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "rules.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"_comment": "x", "kawasan_hutan": {"label": "Kawasan Hutan"}}, fh)
        rules = load_rules(rules_path=path)
        assert rules == {"kawasan_hutan": {"label": "Kawasan Hutan"}}


def test_slugify_basic():
    assert slugify("Kawasan Hutan!") == "kawasan_hutan"
    assert slugify("   ") == "referensi"


def test_unique_slug_dedupes_on_collision():
    existing = {"kawasan_hutan": {}}
    assert unique_slug("Kawasan Hutan", existing) == "kawasan_hutan_2"
    assert unique_slug("Sempadan Sungai", existing) == "sempadan_sungai"


def test_upsert_rule_adds_and_edits_in_place():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "rules.json")
        upsert_rule("kawasan_hutan", "Kawasan Hutan", "kawasan_hutan.gpkg",
                   "FUNGSI", ["HM", "HGU"], rules_path=path)
        upsert_rule("kawasan_hutan", "Kawasan Hutan", "kawasan_hutan.gpkg",
                   "FUNGSI", ["HM"], rules_path=path)   # edit: kurangi satu hak
        rules = load_rules(rules_path=path)
        assert len(rules) == 1   # edit menimpa, bukan menambah baris baru
        assert rules["kawasan_hutan"]["jenis_hak_dilarang"] == ["HM"]


def test_remove_rule():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "rules.json")
        upsert_rule("kawasan_hutan", "Kawasan Hutan", None, None, [], rules_path=path)
        remove_rule("kawasan_hutan", rules_path=path)
        assert load_rules(rules_path=path) == {}
        remove_rule("tidak_ada", rules_path=path)   # no-op, tidak error


def test_reload_rules_refreshes_module_global():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "rules.json")
        upsert_rule("x", "X", None, None, ["HM"], rules_path=path)
        try:
            logical_consistency.reload_rules(path)
            assert logical_consistency.CONCEPTUAL_RULES["x"]["jenis_hak_dilarang"] == ["HM"]
        finally:
            logical_consistency.reload_rules()   # kembalikan ke state asli untuk test lain


def test_discover_reference_files_stem_match():
    with tempfile.TemporaryDirectory() as d:
        rules_path = os.path.join(d, "rules.json")
        upsert_rule("kawasan_hutan", "Kawasan Hutan", "kawasan_hutan.gpkg",
                   None, [], rules_path=rules_path)
        upsert_rule("kawasan_lindung", "Kawasan Lindung", None, None, [], rules_path=rules_path)
        open(os.path.join(d, "kawasan_hutan.gpkg"), "w").close()

        found = discover_reference_files(ref_dir=d, rules_path=rules_path)
        assert found["kawasan_hutan"].endswith("kawasan_hutan.gpkg")
        assert found["kawasan_lindung"] is None   # entry tanpa 'file' -> None


def test_discover_reference_files_missing_file_on_disk_returns_none():
    with tempfile.TemporaryDirectory() as d:
        rules_path = os.path.join(d, "rules.json")
        upsert_rule("kawasan_hutan", "Kawasan Hutan", "kawasan_hutan.gpkg",
                   None, [], rules_path=rules_path)
        # file tidak benar-benar ada di ref_dir
        found = discover_reference_files(ref_dir=d, rules_path=rules_path)
        assert found["kawasan_hutan"] is None


def test_save_reference_file_copies_sidecars_and_replaces_old():
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as ref_dir:
        shp = os.path.join(src_dir, "hutan_prov.shp")
        open(shp, "w").close()
        open(os.path.join(src_dir, "hutan_prov.shx"), "w").close()
        open(os.path.join(src_dir, "hutan_prov.dbf"), "w").close()

        dest = save_reference_file("kawasan_hutan", shp, ref_dir=ref_dir)
        assert dest.endswith("kawasan_hutan.shp")
        assert os.path.isfile(os.path.join(ref_dir, "kawasan_hutan.shx"))
        assert os.path.isfile(os.path.join(ref_dir, "kawasan_hutan.dbf"))

        gpkg = os.path.join(src_dir, "hutan_v2.gpkg")
        open(gpkg, "w").close()
        dest2 = save_reference_file("kawasan_hutan", gpkg, ref_dir=ref_dir)
        assert dest2.endswith("kawasan_hutan.gpkg")
        assert not os.path.isfile(os.path.join(ref_dir, "kawasan_hutan.shp"))  # file lama diganti


def test_save_reference_file_rejects_invalid_slug_and_format():
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "x.gpkg")
        open(f, "w").close()
        try:
            save_reference_file("Bukan Slug!", f, ref_dir=d)
            assert False, "harus raise ValueError untuk slug tak valid"
        except ValueError:
            pass

        bad = os.path.join(d, "kawasan_hutan.txt")
        open(bad, "w").close()
        try:
            save_reference_file("kawasan_hutan", bad, ref_dir=d)
            assert False, "harus raise ValueError untuk format tak didukung"
        except ValueError:
            pass


def test_read_field_names_empty_without_qgis():
    assert read_field_names("does_not_matter.gpkg") == []   # no QGIS in test env
