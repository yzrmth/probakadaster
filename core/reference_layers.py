# -*- coding: utf-8 -*-
"""Data referensi kawasan (RTRW, kawasan hutan, sempadan sungai, dll.) untuk
sub-elemen Konsistensi Konseptual (Logical Consistency).

Aturan bersifat dinamis - dikelola lewat tab Pengaturan GUI (Tambah/Edit/
Hapus), disimpan di `resources/config/conceptual_rules.json`. Tiap entry
mencatat nama file referensinya sendiri (relatif ke
`resources/reference_layers/`) - upload ulang file yang sama = ganti data,
tanpa perlu reload apa pun di QGIS.
"""

import glob
import json
import os
import re
import shutil

try:  # QGIS hanya tersedia di dalam aplikasi QGIS.
    from qgis.core import (QgsCoordinateTransform, QgsGeometry, QgsProject,
                           QgsSpatialIndex, QgsVectorLayer)
    QGIS_AVAILABLE = True
except ImportError:  # memungkinkan unit test di luar QGIS
    QGIS_AVAILABLE = False

_REF_DIR = os.path.join(os.path.dirname(__file__), "..", "resources", "reference_layers")
_RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "resources", "config",
                           "conceptual_rules.json")
_ACCEPTED_EXT = (".gpkg", ".shp", ".geojson", ".json")
_RULES_COMMENT = ("Aturan konseptual: jenis hak yang TIDAK sesuai bila bidang berada "
                  "pada kawasan/objek referensi tertentu. 'file' = nama file (relatif "
                  "ke resources/reference_layers/) hasil upload. '*' pada "
                  "jenis_hak_dilarang = seluruh jenis hak dianggap tidak sesuai. "
                  "Dikelola lewat tab Pengaturan (Tambah/Edit/Hapus) - jangan edit "
                  "manual kecuali paham skemanya.")


def load_rules(rules_path: str = _RULES_PATH) -> dict:
    """{slug: {label, file, atribut, jenis_hak_dilarang, catatan}}. `_comment`
    disaring - satu-satunya sumber kebenaran untuk aturan kawasan."""
    if not os.path.isfile(rules_path):
        return {}
    with open(rules_path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def slugify(label: str) -> str:
    """'Kawasan Hutan!' -> 'kawasan_hutan'. 'referensi' bila hasilnya kosong."""
    s = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return s or "referensi"


def unique_slug(label: str, existing: dict) -> str:
    """slugify(label), tambahkan _2/_3/... bila bentrok dengan existing."""
    base = slugify(label)
    slug, n = base, 2
    while slug in existing:
        slug = f"{base}_{n}"
        n += 1
    return slug


def upsert_rule(slug: str, label: str, file_field, atribut, jenis_hak_dilarang,
                catatan=None, rules_path: str = _RULES_PATH) -> None:
    """Tambah entry baru (slug belum ada) atau timpa entry lama (slug sama) -
    dipakai untuk Tambah maupun Edit di GUI."""
    rules = load_rules(rules_path)
    rules[slug] = {"label": label, "file": file_field, "atribut": atribut,
                   "jenis_hak_dilarang": jenis_hak_dilarang, "catatan": catatan}
    _write_rules(rules, rules_path)


def remove_rule(slug: str, rules_path: str = _RULES_PATH) -> None:
    """Hapus entry dari JSON (file fisik di reference_layers/ tidak disentuh)."""
    rules = load_rules(rules_path)
    rules.pop(slug, None)
    _write_rules(rules, rules_path)


def _write_rules(rules: dict, rules_path: str) -> None:
    os.makedirs(os.path.dirname(rules_path), exist_ok=True)
    with open(rules_path, "w", encoding="utf-8") as fh:
        json.dump({"_comment": _RULES_COMMENT, **rules}, fh, ensure_ascii=False, indent=2)


def discover_reference_files(ref_dir: str = _REF_DIR, rules_path: str = _RULES_PATH) -> dict:
    """{slug: filepath or None} - resolusi field 'file' tiap entry terhadap
    ref_dir. None bila entry belum punya file atau filenya sudah tidak ada."""
    found = {}
    for slug, entry in load_rules(rules_path).items():
        name = entry.get("file")
        path = os.path.join(ref_dir, name) if name else None
        found[slug] = path if path and os.path.isfile(path) else None
    return found


def save_reference_file(slug: str, src_path: str, ref_dir: str = _REF_DIR) -> str:
    """Salin file referensi (& sidecar mis. .shp -> .shx/.dbf/.prj) ke ref_dir
    sebagai `slug.<ext>`, menggantikan file lama untuk slug ini (upload ulang =
    ganti seluruhnya). Kembalikan path file utama hasil salin."""
    if not slug or not re.fullmatch(r"[a-z0-9_]+", slug):
        raise ValueError(f"Slug tidak valid: {slug!r}")
    ext = os.path.splitext(src_path)[1].lower()
    if ext not in _ACCEPTED_EXT:
        raise ValueError(f"Format tidak didukung: {ext}")

    os.makedirs(ref_dir, exist_ok=True)
    for old in glob.glob(os.path.join(ref_dir, slug + ".*")):
        os.remove(old)

    src_stem = os.path.splitext(src_path)[0]
    result = None
    for sib in glob.glob(src_stem + ".*"):
        dest = os.path.join(ref_dir, slug + os.path.splitext(sib)[1])
        shutil.copyfile(sib, dest)
        if dest.lower().endswith(ext):
            result = dest
    return result


def read_field_names(path: str) -> list:
    """Nama field pada file vektor referensi (dibaca via OGR). List kosong
    bila file tidak valid atau QGIS tidak tersedia - dipakai GUI untuk
    mengisi pilihan "atribut acuan" setelah file dipilih."""
    if not path or not QGIS_AVAILABLE:
        return []
    layer = QgsVectorLayer(path, "_probe", "ogr")
    if not layer.isValid():
        return []
    return [f.name() for f in layer.fields()]


def build_kawasan_overlay(layer, parcels, discovered: dict = None) -> dict:
    """{parcel_id: [slug, ...]} - entry referensi tempat tiap bidang berada.

    Membutuhkan QGIS. `layer` = layer bidang tanah (sumber geometri via fid),
    `parcels` = list[Parcel].
    """
    if not QGIS_AVAILABLE:
        raise RuntimeError("QGIS API tidak tersedia di lingkungan ini.")

    discovered = discovered if discovered is not None else discover_reference_files()
    geometries = {f.id(): f.geometry() for f in layer.getFeatures()}
    overlay = {p.parcel_id: [] for p in parcels}

    for slug, path in discovered.items():
        if not path:
            continue
        ref_layer = QgsVectorLayer(path, slug, "ogr")
        if not ref_layer.isValid():
            continue  # file ada tapi tidak terbaca - lewati, jangan crash

        index = QgsSpatialIndex(ref_layer.getFeatures())
        transform = None
        if layer.crs() != ref_layer.crs():
            transform = QgsCoordinateTransform(layer.crs(), ref_layer.crs(),
                                               QgsProject.instance())

        for p in parcels:
            geom = geometries.get(p.fid)
            if geom is None:
                continue
            test_geom = QgsGeometry(geom)
            if transform:
                test_geom.transform(transform)
            for fid in index.intersects(test_geom.boundingBox()):
                if test_geom.intersects(ref_layer.getFeature(fid).geometry()):
                    overlay[p.parcel_id].append(slug)
                    break

    return overlay
