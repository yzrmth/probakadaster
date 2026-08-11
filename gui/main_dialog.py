# -*- coding: utf-8 -*-
"""Dialog utama ProbaKadaster.

Controller GUI: memilih layer, mengatur bobot AHP, menjalankan penilaian,
lalu mem-visualisasikan Heatmap ADQR & Positional Confidence Buffer, serta
mengekspor laporan.

UI dibangun programatik agar skeleton ini mandiri (tanpa file .ui terpisah).
Pada implementasi produksi disarankan memakai Qt Designer (main_dialog_base.ui).
"""

from qgis.PyQt.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox,
                                 QFileDialog, QFormLayout, QGroupBox,
                                 QHBoxLayout, QLabel, QLineEdit, QMenu,
                                 QPlainTextEdit, QProgressBar, QPushButton,
                                 QTableWidget, QTableWidgetItem, QTabWidget,
                                 QVBoxLayout, QWidget, QMessageBox)

from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

import os

import pandas as pd

from ..core import reference_layers
from ..core.adqr_calculator import ADQRCalculator
from ..core.data_loader import (extract_layer_nib, join_master_spatial,
                                load_master, master_quality_report)
from ..core.engine import QualityEngine
from ..core.quality import logical_consistency
from ..core.quality.completeness import compute_completeness
from ..core.spatial_processing import SpatialProcessor

ELEMENT_LABELS = [
    ("completeness", "Completeness"),
    ("logical", "Logical Consistency"),
    ("positional", "Positional Accuracy"),
    ("thematic", "Thematic Accuracy"),
    ("temporal", "Temporal Accuracy"),
]

# Kode jenis hak baku (basis data pertanahan) - "*" = seluruh jenis hak.
HAK_OPTIONS = [
    ("*", "Semua Jenis Hak (mis. RTRW tidak sesuai)"),
    ("HM", "1 - Hak Milik (HM)"),
    ("HGU", "2 - Hak Guna Usaha (HGU)"),
    ("HGB", "3 - Hak Guna Bangunan (HGB)"),
    ("HP", "4 - Hak Pakai (HP)"),
    ("HPL", "5 - Hak Pengelolaan (HPL)"),
    ("HMSRS", "6 - Hak Milik Satuan Rumah Susun (HMSRS)"),
    ("HT", "7 - Hak Tanggungan (HT)"),
    ("TN_WAKAF", "8 - Tanah Negara / Wakaf"),
]


class ReferenceRuleDialog(QDialog):
    """Dialog Tambah/Edit satu aturan referensi kawasan (Fase 2). Alur: pilih
    file -> atribut acuan terbaca otomatis -> pilih jenis hak dilarang."""

    def __init__(self, parent=None, slug=None, entry=None):
        super().__init__(parent)
        self.slug = slug
        self.entry = entry or {}
        self._picked_path = None
        self.result_data = None
        self.setWindowTitle("Edit Referensi" if slug else "Tambah Referensi")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.label_edit = QLineEdit(self.entry.get("label", ""))
        form.addRow("Nama:", self.label_edit)

        file_row = QHBoxLayout()
        self.file_status = QLabel(self.entry.get("file") or "Belum ada file")
        pick_btn = QPushButton("Pilih File...")
        pick_btn.clicked.connect(self._on_pick_file)
        file_row.addWidget(self.file_status)
        file_row.addWidget(pick_btn)
        form.addRow("Data Referensi:", file_row)

        self.attr_combo = QComboBox()
        form.addRow("Atribut Acuan:", self.attr_combo)

        self.hak_btn = QPushButton()
        hak_menu = QMenu(self.hak_btn)
        self._hak_actions = {}
        forbidden = self.entry.get("jenis_hak_dilarang", [])
        for code, hak_label in HAK_OPTIONS:
            act = hak_menu.addAction(hak_label)
            act.setCheckable(True)
            act.setChecked(code in forbidden)
            act.toggled.connect(self._update_hak_button)
            self._hak_actions[code] = act
        self.hak_btn.setMenu(hak_menu)
        self._update_hak_button()
        form.addRow("Jenis Hak Tidak Sesuai:", self.hak_btn)

        self.catatan_edit = QPlainTextEdit(self.entry.get("catatan") or "")
        self.catatan_edit.setMaximumHeight(60)
        form.addRow("Catatan (opsional):", self.catatan_edit)

        layout.addLayout(form)

        existing_path = (reference_layers.discover_reference_files().get(self.slug)
                         if self.slug else None)
        self._populate_attr_combo(existing_path, self.entry.get("atribut"))

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Simpan")
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("Batal")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _update_hak_button(self, *_args):
        selected = [code for code, act in self._hak_actions.items() if act.isChecked()]
        self.hak_btn.setText(", ".join(selected) or "Pilih Jenis Hak...")

    def _on_pick_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih Data Referensi", "",
            "Vektor (*.gpkg *.shp *.geojson *.json)")
        if not path:
            return
        self._picked_path = path
        self.file_status.setText(os.path.basename(path))
        self._populate_attr_combo(path, None)

    def _populate_attr_combo(self, path, preselect):
        self.attr_combo.clear()
        fields = reference_layers.read_field_names(path) if path else []
        self.attr_combo.addItems(fields)
        self.attr_combo.setEnabled(bool(fields))
        if preselect and preselect in fields:
            self.attr_combo.setCurrentText(preselect)

    def _on_save(self):
        label = self.label_edit.text().strip()
        if not label:
            QMessageBox.warning(self, "ProbaKadaster", "Nama referensi wajib diisi.")
            return
        if not self._picked_path and not self.entry.get("file"):
            QMessageBox.warning(self, "ProbaKadaster", "Pilih file data referensi dulu.")
            return
        codes = [code for code, act in self._hak_actions.items() if act.isChecked()]
        self.result_data = {
            "label": label,
            "picked_path": self._picked_path,
            "atribut": self.attr_combo.currentText() or None,
            "hak_codes": codes,
            "catatan": self.catatan_edit.toPlainText().strip() or None,
        }
        self.accept()


class MainDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("ProbaKadaster - Penilaian Kualitas & Peta Probabilistik")
        self.setMinimumWidth(560)
        self._weight_spins = {}
        self._heatmap_bands = ADQRCalculator().classification["adqr_confidence_heatmap"]
        self._build_ui()

    # ------------------------------------------------------------------ #
    def _build_ui(self):
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)

        run_tab = QWidget()
        root = QVBoxLayout(run_tab)
        tabs.addTab(run_tab, "Penilaian")
        tabs.addTab(self._build_requirements_tab(), "Requirement Atribut")
        tabs.addTab(self._build_settings_tab(), "Pengaturan")
        tabs.addTab(self._build_completeness_tab(), "Hasil Completeness")
        tabs.addTab(self._build_log_tab(), "Log")

        # 1. Sumber data
        src = QGroupBox("1. Sumber Data (Layer Bidang Tanah - KKP)")
        src_l = QFormLayout(src)
        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        src_l.addRow("Layer:", self.layer_combo)
        root.addWidget(src)

        # 1b. Data kualitas (Excel DetailKW)
        xls = QGroupBox("1b. Data Kualitas (Excel - sheet DetailKW)")
        xls_l = QHBoxLayout(xls)
        self.excel_edit = QLineEdit()
        self.excel_edit.setReadOnly(True)
        self.excel_edit.setPlaceholderText("Belum dipilih...")
        browse_btn = QPushButton("Pilih File...")
        browse_btn.clicked.connect(self.on_browse_excel)
        xls_l.addWidget(self.excel_edit)
        xls_l.addWidget(browse_btn)
        root.addWidget(xls)

        self.completeness_btn = QPushButton("Join Spasial + Analisis Completeness (Fase 1)")
        self.completeness_btn.clicked.connect(self.on_completeness)
        root.addWidget(self.completeness_btn)

        # 2. Bobot AHP
        w = QGroupBox("2. Bobot Elemen Kualitas (Eigenvector AHP - total = 1)")
        wl = QFormLayout(w)
        default_w = {"completeness": 0.20, "logical": 0.20, "positional": 0.25,
                     "thematic": 0.15, "temporal": 0.20}
        for key, label in ELEMENT_LABELS:
            sp = QDoubleSpinBox()
            sp.setRange(0.0, 1.0)
            sp.setSingleStep(0.01)
            sp.setValue(default_w[key])
            self._weight_spins[key] = sp
            wl.addRow(label + ":", sp)
        root.addWidget(w)

        # 3. Aksi
        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("Jalankan Penilaian + Buat Peta Probabilistik")
        self.run_btn.clicked.connect(self.on_run)
        self.export_btn = QPushButton("Ekspor Laporan")
        self.export_btn.clicked.connect(self.on_export)
        self.export_btn.setEnabled(False)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.export_btn)
        root.addLayout(btn_row)

        self.progress = QProgressBar()
        root.addWidget(self.progress)
        self.status = QLabel("Siap.")
        root.addWidget(self.status)

        # 4. Ringkasan hasil
        self.summary_table = QTableWidget(0, 2)
        self.summary_table.setHorizontalHeaderLabels(["Statistik", "Nilai"])
        self.summary_table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.summary_table)

        self._result = None
        self._completeness_result = None

    # ------------------------------------------------------------------ #
    REQUIRED_ATTRIBUTES = [
        ("nib", "NIB", "Identitas bidang & deteksi data ganda (Completeness)"),
        ("luas_kkp", "Luas KKP (m2)", "Ketelitian Luas / Thematic Accuracy"),
        ("luas_su", "Luas Surat Ukur (m2)", "Ketelitian Luas / Thematic Accuracy"),
        ("kw", "Klasifikasi KW1-KW6", "Kelengkapan Dokumen (Completeness)"),
        ("jenis_hak", "Jenis Hak (HM/HGB/HGU/dll)", "Konsistensi Konseptual (Logical Consistency)"),
        ("no_hak", "Nomor Hak", "Deteksi data ganda (Completeness)"),
        ("no_su", "Nomor Surat Ukur", "Deteksi data ganda (Completeness)"),
        ("tgl_terbit", "Tanggal Penerbitan/Pemutakhiran", "Akurasi Waktu (Temporal Accuracy)"),
    ]

    def _build_requirements_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel(
            "Layer bidang tanah wajib memiliki atribut berikut agar seluruh "
            "elemen kualitas dapat dihitung (bukan nilai default/kosong):"))

        table = QTableWidget(len(self.REQUIRED_ATTRIBUTES), 3)
        table.setHorizontalHeaderLabels(
            ["Field Internal", "Nama Kolom Default", "Dipakai Untuk"])
        table.horizontalHeader().setStretchLastSection(True)
        for r, (internal, col, usage) in enumerate(self.REQUIRED_ATTRIBUTES):
            table.setItem(r, 0, QTableWidgetItem(internal))
            table.setItem(r, 1, QTableWidgetItem(col))
            table.setItem(r, 2, QTableWidgetItem(usage))
        table.resizeColumnsToContents()
        layout.addWidget(table)

        layout.addWidget(QLabel(
            "Catatan: Positional Accuracy membutuhkan data referensi ortofoto "
            "terpisah (bukan atribut tabel), belum tersedia pada versi ini.\n"
            "Nama kolom di atas adalah pemetaan default (DEFAULT_FIELD_MAP) - "
            "bisa disesuaikan bila nama kolom pada layer Anda berbeda."))
        return w

    # ------------------------------------------------------------------ #
    # Fase 2: Konsistensi Konseptual - aturan referensi kawasan (dinamis,
    # dibaca dari conceptual_rules.json lewat reference_layers.py).
    SETTINGS_COLUMNS = ["Nama", "File Referensi", "Atribut Acuan",
                        "Jenis Hak Tidak Sesuai", "Catatan", "Aksi"]

    def _build_settings_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel(
            "Aturan Konsistensi Konseptual (Fase 2) - daftar di bawah dibaca "
            "langsung dari conceptual_rules.json. Tambah Referensi untuk "
            "upload data kawasan baru: pilih file, atribut acuan terbaca "
            "otomatis, lalu pilih jenis hak yang dilarang."))

        self._settings_table = QTableWidget(0, len(self.SETTINGS_COLUMNS))
        self._settings_table.setHorizontalHeaderLabels(self.SETTINGS_COLUMNS)
        self._settings_table.horizontalHeader().setStretchLastSection(True)
        self._settings_table.verticalHeader().setVisible(False)
        self._settings_table.setWordWrap(True)
        layout.addWidget(self._settings_table)

        add_btn = QPushButton("+ Tambah Referensi")
        add_btn.clicked.connect(self.on_add_reference)
        layout.addWidget(add_btn)

        self._refresh_settings_table()
        return w

    def _refresh_settings_table(self):
        rules = reference_layers.load_rules()
        table = self._settings_table
        table.setRowCount(len(rules))
        for r, (slug, entry) in enumerate(rules.items()):
            values = (entry.get("label", slug), entry.get("file") or "-",
                      entry.get("atribut") or "-",
                      ", ".join(entry.get("jenis_hak_dilarang", [])) or "-",
                      entry.get("catatan") or "")
            for c, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                table.setItem(r, c, item)

            cell = QWidget()
            cell_l = QHBoxLayout(cell)
            cell_l.setContentsMargins(2, 2, 2, 2)
            edit_btn = QPushButton("Edit")
            edit_btn.clicked.connect(lambda _, s=slug: self.on_edit_reference(s))
            del_btn = QPushButton("Hapus")
            label = entry.get("label", slug)
            del_btn.clicked.connect(lambda _, s=slug, lbl=label: self.on_delete_reference(s, lbl))
            cell_l.addWidget(edit_btn)
            cell_l.addWidget(del_btn)
            table.setCellWidget(r, 5, cell)

        table.resizeRowsToContents()
        table.resizeColumnsToContents()

    def on_add_reference(self):
        dlg = ReferenceRuleDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        self._save_reference_dialog_result(dlg.result_data, existing_slug=None)

    def on_edit_reference(self, slug):
        entry = reference_layers.load_rules().get(slug, {})
        dlg = ReferenceRuleDialog(self, slug=slug, entry=entry)
        if dlg.exec_() != QDialog.Accepted:
            return
        self._save_reference_dialog_result(dlg.result_data, existing_slug=slug)

    def _save_reference_dialog_result(self, data, existing_slug):
        try:
            rules = reference_layers.load_rules()
            slug = existing_slug or reference_layers.unique_slug(data["label"], rules)
            file_field = rules.get(slug, {}).get("file")
            if data["picked_path"]:
                dest = reference_layers.save_reference_file(slug, data["picked_path"])
                file_field = os.path.basename(dest)
            reference_layers.upsert_rule(slug, data["label"], file_field,
                                         data["atribut"], data["hak_codes"], data["catatan"])
            logical_consistency.reload_rules()
            self._log(f"[OK] Referensi '{data['label']}' disimpan.")
        except Exception as exc:  # noqa: BLE001 - tampilkan ke pengguna
            self._log(f"[ERROR] Gagal menyimpan referensi: {exc}")
            QMessageBox.critical(self, "ProbaKadaster", f"Gagal: {exc}")
            return
        self._refresh_settings_table()

    def on_delete_reference(self, slug, label):
        confirm = QMessageBox.question(
            self, "ProbaKadaster", f"Hapus aturan '{label}'? File referensi di "
            "resources/reference_layers/ tidak akan dihapus.",
            QMessageBox.Yes | QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        reference_layers.remove_rule(slug)
        logical_consistency.reload_rules()
        self._log(f"[OK] Referensi '{label}' dihapus.")
        self._refresh_settings_table()

    COMPLETENESS_COLUMNS = [
        ("NIB", "NIB"), ("Nomor_Hak", "Nomor Hak"), ("KW", "KW"),
        ("Luas", "Luas (m2)"),
        ("ikb_omission", "IKB Omission"), ("ikb_commission", "IKB Commission"),
        ("kw_value", "Skor KW"), ("ikb_completeness", "IKB Completeness"),
        ("unsur_bermasalah", "Unsur Belum Lengkap/Berlebih"),
        ("plotting", "Plotting"),
    ]

    def _build_completeness_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel(
            "Hasil per bidang: IKB Omission, IKB Commission, Skor KW -> IKB Completeness. "
            "'Plotting' = Belum Plotting bila bidang tidak ditemukan di layer spasial saat join."))
        layout.addLayout(self._build_legend_row())
        self.completeness_table = QTableWidget(0, len(self.COMPLETENESS_COLUMNS))
        self.completeness_table.setHorizontalHeaderLabels(
            [label for _, label in self.COMPLETENESS_COLUMNS])
        self.completeness_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.completeness_table)

        export_btn = QPushButton("Ekspor Hasil Completeness (CSV)...")
        export_btn.clicked.connect(self.on_export_completeness)
        layout.addWidget(export_btn)
        return w

    def _build_legend_row(self):
        """Keterangan warna: label + rentang nilai tiap kelas (very_low..very_high)."""
        row = QHBoxLayout()
        for band in reversed(self._heatmap_bands):
            label_text = band["class"].replace("_", " ").title()
            hi = min(band["max"], 1.0)
            chip = QLabel(f" {label_text} ({band['min']:.2f}-{hi:.2f}) ")
            chip.setStyleSheet(
                f"background-color:{band['color']}; border-radius:3px; padding:2px;")
            row.addWidget(chip)
        row.addStretch()
        return row

    @staticmethod
    def _format_cell(col, value):
        if pd.isna(value):
            return ""
        if col == "NIB":
            return str(int(value))
        if isinstance(value, float):
            return f"{value:.4f}".rstrip("0").rstrip(".")
        return str(value)

    def _color_for_ikb(self, value):
        """Warna sesuai band 'adqr_confidence_heatmap' (sama dgn heatmap peta)."""
        if pd.isna(value):
            return None
        for band in self._heatmap_bands:
            if band["min"] <= value < band["max"]:
                return band["color"]
        return self._heatmap_bands[0]["color"] if value < 0 else self._heatmap_bands[-1]["color"]

    def _fill_completeness_table(self, df):
        self.completeness_table.setRowCount(len(df))
        cols = [c for c, _ in self.COMPLETENESS_COLUMNS]
        for r, (_, row) in enumerate(df[cols].iterrows()):
            color = self._color_for_ikb(row["ikb_completeness"])
            for c, col in enumerate(cols):
                item = QTableWidgetItem(self._format_cell(col, row[col]))
                if color:
                    item.setBackground(QColor(color))
                self.completeness_table.setItem(r, c, item)
        self.completeness_table.resizeColumnsToContents()

    def _build_log_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        return w

    _LOG_COLOR = {"[ERROR]": "#d73027", "[OK]": "#1a9850", "[INFO]": "#555555"}

    def _log(self, msg):
        color = next((c for tag, c in self._LOG_COLOR.items() if msg.startswith(tag)),
                     "#000000")
        self.log_view.appendHtml(f'<span style="color:{color}">{msg}</span>')

    # ------------------------------------------------------------------ #
    def _weights(self):
        w = {k: sp.value() for k, sp in self._weight_spins.items()}
        total = sum(w.values()) or 1.0
        return {k: v / total for k, v in w.items()}   # normalisasi ke 1

    def _progress(self, pct, msg=""):
        self.progress.setValue(pct)
        if msg:
            self.status.setText(msg)
            self._log(msg)

    def on_browse_excel(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih Data Kualitas (Excel)", "", "Excel (*.xlsx)")
        if path:
            self.excel_edit.setText(path)

    def on_completeness(self):
        """Alur Fase 1: pilih layer spasial -> pilih Excel -> join by NIB -> Completeness."""
        layer = self.layer_combo.currentLayer()
        excel_path = self.excel_edit.text()
        if layer is None:
            QMessageBox.warning(self, "ProbaKadaster", "Pilih layer bidang tanah dulu.")
            return
        if not excel_path:
            QMessageBox.warning(self, "ProbaKadaster", "Pilih file Excel data kualitas dulu.")
            return

        self.log_view.clear()
        try:
            self._log("[INFO] Membaca atribut NIB dari layer spasial...")
            spatial_records = extract_layer_nib(layer)
            self._log(f"[OK] {len(spatial_records)} fitur spasial terbaca.")

            self._log(f"[INFO] Memuat data kualitas: {excel_path}")
            master = load_master(excel_path)
            report = master_quality_report(master)
            self._log(f"[OK] {report['total_baris']} baris dimuat "
                     f"(NIB kosong={report['nib_kosong']}, "
                     f"NIB ganda={report['nib_ganda_baris']}, "
                     f"belum terpetakan={report['belum_terpetakan']}).")

            self._log("[INFO] Join data kualitas <-> layer spasial via NIB...")
            joined = join_master_spatial(master, spatial_records)
            matched = joined["fid"].notna().sum()
            self._log(f"[OK] {matched}/{len(joined)} bidang cocok dengan fitur spasial.")

            self._log("[INFO] Menilai Completeness...")
            self._completeness_result = compute_completeness(joined)
            self._completeness_result["plotting"] = self._completeness_result["fid"].notna().map(
                {True: "Sudah Plotting", False: "Belum Plotting"})
            mean_ikb = self._completeness_result["ikb_completeness"].mean()
            self._log(f"[OK] Completeness selesai untuk {len(self._completeness_result)} "
                     f"bidang (rata-rata IKB={mean_ikb:.4f}).")
            self._fill_completeness_table(self._completeness_result)

            self._log("[INFO] Membuat layer 'Completeness' dari hasil join...")
            sp = SpatialProcessor(self.iface)
            sub_layer = sp.build_join_result_layer(layer, self._completeness_result,
                                                    out_name="Completeness")
            sp.apply_heatmap(sub_layer, field_adqr="ikb_completeness")
            sp.add_to_project(sub_layer)
            self._log(f"[OK] Layer 'Completeness' dibuat ({sub_layer.featureCount()} fitur), "
                     f"diwarnai berdasarkan IKB Completeness.")

            self._fill_summary({
                "count": len(self._completeness_result),
                "mean_adqr": round(mean_ikb, 4),
                "min_adqr": round(self._completeness_result["ikb_completeness"].min(), 4),
                "max_adqr": round(self._completeness_result["ikb_completeness"].max(), 4),
                "std_sdam": round(self._completeness_result["ikb_completeness"].std(), 4),
                "gvf": "-",
            })
            self.export_btn.setEnabled(True)
        except Exception as exc:  # noqa: BLE001 - tampilkan ke pengguna
            self._log(f"[ERROR] Gagal: {exc}")
            QMessageBox.critical(self, "ProbaKadaster", f"Gagal: {exc}")

    # ------------------------------------------------------------------ #
    def on_run(self):
        layer = self.layer_combo.currentLayer()
        if layer is None:
            QMessageBox.warning(self, "ProbaKadaster", "Pilih layer bidang tanah dulu.")
            return
        self.log_view.clear()
        try:
            engine = QualityEngine(weights=self._weights(),
                                   progress_cb=self._progress)
            self._result = engine.run(layer)
            self._write_adqr_fields(layer)
            self._visualize(layer)
            self._fill_summary(self._result["summary"])
            self.export_btn.setEnabled(True)
        except Exception as exc:  # noqa: BLE001 - tampilkan ke pengguna
            self._log(f"[ERROR] Gagal: {exc}")
            QMessageBox.critical(self, "ProbaKadaster", f"Gagal: {exc}")

    def _write_adqr_fields(self, layer):
        """Tulis kolom adqr, pos_conf, buffer_m ke layer sumber (in-memory edit)."""
        from qgis.core import QgsField
        from qgis.PyQt.QtCore import QVariant
        prov = layer.dataProvider()
        existing = [f.name() for f in layer.fields()]
        to_add = [("adqr", QVariant.Double), ("pos_conf", QVariant.String),
                  ("buffer_m", QVariant.Double), ("kualitas", QVariant.String)]
        prov.addAttributes([QgsField(n, t) for n, t in to_add if n not in existing])
        layer.updateFields()
        idx = {n: layer.fields().indexOf(n) for n, _ in to_add}

        by_fid = {p.fid: p for p in self._result["parcels"]}
        layer.startEditing()
        for feat in layer.getFeatures():
            p = by_fid.get(feat.id())
            if not p or not p.adqr:
                continue
            layer.changeAttributeValue(feat.id(), idx["adqr"], p.adqr.adqr_value)
            layer.changeAttributeValue(feat.id(), idx["pos_conf"],
                                       p.adqr.positional_confidence.value)
            layer.changeAttributeValue(feat.id(), idx["buffer_m"], p.adqr.buffer_width_m)
            layer.changeAttributeValue(feat.id(), idx["kualitas"], p.adqr.quality_category)
        layer.commitChanges()

    def _visualize(self, layer):
        sp = SpatialProcessor(self.iface)
        sp.apply_heatmap(layer, field_adqr="adqr")
        buffer_layer = sp.build_confidence_buffer(layer)
        sp.add_to_project(buffer_layer)
        self.status.setText("Heatmap ADQR & Confidence Buffer dibuat.")

    def _fill_summary(self, summary):
        rows = [
            ("Jumlah Bidang", summary.get("count")),
            ("Rata-rata ADQR", summary.get("mean_adqr")),
            ("Nilai Minimum", summary.get("min_adqr")),
            ("Nilai Maksimum", summary.get("max_adqr")),
            ("Standar Deviasi (SDAM)", summary.get("std_sdam")),
            ("Goodness of Variance Fit (GVF)", summary.get("gvf")),
        ]
        self.summary_table.setRowCount(len(rows))
        for r, (k, v) in enumerate(rows):
            self.summary_table.setItem(r, 0, QTableWidgetItem(str(k)))
            self.summary_table.setItem(r, 1, QTableWidgetItem(str(v)))

    def on_export(self):
        # Placeholder: sambungkan ke report generator (CSV/PDF/HTML) untuk pipeline lama.
        QMessageBox.information(self, "ProbaKadaster",
                               "Ekspor laporan akan disambungkan ke report generator.")

    def on_export_completeness(self):
        if self._completeness_result is None:
            QMessageBox.information(self, "ProbaKadaster",
                                   "Belum ada hasil Completeness untuk diekspor.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Ekspor Hasil Completeness", "completeness.csv", "CSV (*.csv)")
        if not path:
            return
        self._completeness_result.to_csv(path, index=False)
        self._log(f"[OK] Hasil Completeness diekspor ke {path}")
        QMessageBox.information(self, "ProbaKadaster", f"Hasil diekspor ke:\n{path}")
