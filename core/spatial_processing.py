# -*- coding: utf-8 -*-
"""Eksekusi GIS: styling Heatmap ADQR dan pembuatan Positional Confidence Buffer.

Bergantung pada QGIS Python API (qgis.core). Fungsi di sini mengubah layer
bidang tanah menjadi dua produk visual Peta Kadaster Probabilistik:

  1. Heatmap ADQR              -> graduated symbol (gradasi Merah-Kuning-Hijau).
  2. Positional Confidence Buffer -> layer poligon buffer variabel per confidence.
"""

import json
import os

import pandas as pd

try:  # QGIS hanya tersedia di dalam aplikasi QGIS.
    from qgis.core import (QgsCategorizedSymbolRenderer, QgsFeature,
                           QgsField, QgsFields, QgsGeometry,
                           QgsGraduatedSymbolRenderer, QgsProject,
                           QgsRendererCategory, QgsRendererRange,
                           QgsSymbol, QgsVectorLayer, QgsWkbTypes)
    from qgis.PyQt.QtCore import QVariant
    from qgis.PyQt.QtGui import QColor
    QGIS_AVAILABLE = True
except ImportError:  # memungkinkan unit test di luar QGIS
    QGIS_AVAILABLE = False

_CONFIG = os.path.join(os.path.dirname(__file__), "..", "resources", "config",
                       "classification.json")


def _load_cfg():
    with open(_CONFIG, encoding="utf-8") as fh:
        return json.load(fh)


def _qgis_field_for(name, series):
    """Tentukan tipe QgsField dari dtype kolom pandas (NIB selalu String)."""
    if name == "NIB":
        return QgsField(name, QVariant.String)
    if pd.api.types.is_bool_dtype(series):
        return QgsField(name, QVariant.Int)
    if pd.api.types.is_integer_dtype(series):
        return QgsField(name, QVariant.Int)
    if pd.api.types.is_float_dtype(series):
        return QgsField(name, QVariant.Double)
    return QgsField(name, QVariant.String)


def _qgis_value_for(name, value):
    if pd.isna(value):
        return None
    if name == "NIB":
        return str(int(value))
    if isinstance(value, bool):
        return int(value)
    return value if isinstance(value, (int, float)) else str(value)


class SpatialProcessor:
    """Membuat produk visual probabilistik dari layer bidang tanah ber-ADQR."""

    def __init__(self, iface=None):
        self.iface = iface
        self.cfg = _load_cfg()

    # ------------------------------------------------------------------ #
    # 1. HEATMAP ADQR
    # ------------------------------------------------------------------ #
    def apply_heatmap(self, layer, field_adqr="adqr"):
        """Terapkan renderer graduated (5 kelas) berbasis nilai ADQR ke layer."""
        if not QGIS_AVAILABLE:
            raise RuntimeError("QGIS API tidak tersedia di lingkungan ini.")

        ranges = []
        for band in self.cfg["adqr_confidence_heatmap"]:
            sym = QgsSymbol.defaultSymbol(layer.geometryType())
            sym.setColor(QColor(band["color"]))
            hi = min(band["max"], 1.0)
            label = f"{band['class'].replace('_', ' ').title()} ({band['min']:.2f}-{hi:.2f})"
            rng = QgsRendererRange(band["min"], band["max"], sym, label)
            ranges.append(rng)
        renderer = QgsGraduatedSymbolRenderer(field_adqr, ranges)
        renderer.setMode(QgsGraduatedSymbolRenderer.Custom)
        layer.setRenderer(renderer)
        layer.triggerRepaint()
        return layer

    # ------------------------------------------------------------------ #
    # 2. POSITIONAL CONFIDENCE BUFFER
    # ------------------------------------------------------------------ #
    def build_confidence_buffer(self, layer, field_buffer="buffer_m",
                                field_conf="pos_conf",
                                out_name="confidence_buffer"):
        """Bangun layer buffer variabel (zone of uncertainty) per bidang.

        Lebar buffer diambil dari kolom `buffer_m` (0.25 .. 3.00 m) yang telah
        diisi ADQRCalculator sesuai kelas positional confidence.
        """
        if not QGIS_AVAILABLE:
            raise RuntimeError("QGIS API tidak tersedia di lingkungan ini.")

        crs = layer.crs().authid()
        buf = QgsVectorLayer(f"Polygon?crs={crs}", out_name, "memory")
        provider = buf.dataProvider()
        provider.addAttributes([
            QgsField("parcel_id", QVariant.String),
            QgsField(field_buffer, QVariant.Double),
            QgsField(field_conf, QVariant.String),
        ])
        buf.updateFields()

        feats = []
        for f in layer.getFeatures():
            width = float(f[field_buffer]) if f[field_buffer] else 0.0
            geom = f.geometry()
            # buffer batas: selisih geometri diperbesar & diperkecil (ring).
            outer = geom.buffer(width, 12)
            ring = outer.difference(geom.buffer(-width, 12))
            nf = QgsFeature(buf.fields())
            nf.setGeometry(ring if not ring.isEmpty() else outer)
            nf.setAttributes([f["parcel_id"] if "parcel_id" in
                              [fld.name() for fld in layer.fields()] else str(f.id()),
                              width, f[field_conf] if field_conf in
                              [fld.name() for fld in layer.fields()] else ""])
            feats.append(nf)
        provider.addFeatures(feats)
        buf.updateExtents()
        self._style_buffer(buf, field_conf)
        return buf

    def _style_buffer(self, buf, field_conf):
        cats = []
        for band in self.cfg["positional_confidence"]:
            sym = QgsSymbol.defaultSymbol(buf.geometryType())
            sym.setColor(QColor(band["color"]))
            cats.append(QgsRendererCategory(band["class"], sym, band["label"]))
        buf.setRenderer(QgsCategorizedSymbolRenderer(field_conf, cats))
        buf.triggerRepaint()

    # ------------------------------------------------------------------ #
    # 3. LAYER HASIL JOIN (Fase 1 - Completeness)
    # ------------------------------------------------------------------ #
    def build_join_result_layer(self, source_layer, df, fid_col="fid",
                                out_name="Completeness"):
        """Bangun layer spasial baru dari hasil join master Excel <-> layer.

        Atributnya sama persis dengan `df` (semua kolom master + hasil IKB
        Completeness). Hanya baris yang cocok (`fid_col` terisi) yang
        diikutkan - baris tanpa kecocokan tidak punya geometri untuk diplot.
        """
        if not QGIS_AVAILABLE:
            raise RuntimeError("QGIS API tidak tersedia di lingkungan ini.")

        matched = df[df[fid_col].notna()].copy()
        geometries = {f.id(): f.geometry() for f in source_layer.getFeatures()}

        crs = source_layer.crs().authid()
        out = QgsVectorLayer(f"Polygon?crs={crs}", out_name, "memory")
        provider = out.dataProvider()
        cols = list(df.columns)
        provider.addAttributes([_qgis_field_for(c, matched[c]) for c in cols])
        out.updateFields()

        feats = []
        for _, row in matched.iterrows():
            geom = geometries.get(int(row[fid_col]))
            if geom is None:
                continue
            nf = QgsFeature(out.fields())
            nf.setGeometry(geom)
            nf.setAttributes([_qgis_value_for(c, row[c]) for c in cols])
            feats.append(nf)
        provider.addFeatures(feats)
        out.updateExtents()
        return out

    # ------------------------------------------------------------------ #
    def add_to_project(self, *layers):
        if QGIS_AVAILABLE:
            for lyr in layers:
                QgsProject.instance().addMapLayer(lyr)
