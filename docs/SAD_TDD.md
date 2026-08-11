# Software Architecture Document / Technical Design Document (SAD/TDD)
## Plugin ProbaKadaster

| | |
|---|---|
| **Produk** | ProbaKadaster (plugin QGIS) |
| **Versi** | 0.1.0 (draft) |
| **Penyusun** | Rizal Adhi Pratama |
| **Terkait** | SRS ProbaKadaster v0.1.0 |

---

## 1. Ringkasan Arsitektur

ProbaKadaster memakai arsitektur **berlapis (layered)** dengan pemisahan tegas antara antarmuka, logika, dan data GIS:

1. **Presentation Layer** (`gui/`) — dialog PyQt yang di-host QGIS; hanya menangani interaksi pengguna dan visual.
2. **Application/Orchestration Layer** (`core/engine.py`) — merangkai alur penilaian end-to-end.
3. **Domain/Logic Layer** (`core/quality/`, `core/ahp.py`, `core/adqr_calculator.py`, `core/classification.py`) — perhitungan murni, bebas QGIS, dapat diuji unit.
4. **GIS Execution Layer** (`core/spatial_processing.py`, `core/data_loader.py`) — jembatan ke QGIS API (baca layer, styling, buffer).
5. **AI Layer** (`ai/`) — pipeline pluggable OCR/Segmentation/Georeferencing/LLM.
6. **Model Layer** (`models/schema.py`) — objek domain (Parcel, IKBResult, ADQRResult).
7. **Configuration** (`resources/config/`) — bobot AHP & ambang klasifikasi (JSON).

Prinsip desain: *dependency rule* mengarah ke dalam — GUI bergantung pada logika, logika tidak bergantung pada GUI; logika inti tidak meng-import `qgis` sehingga dapat diuji tanpa QGIS.

---

## 2. Struktur Direktori (Module Architecture)

```
probakadaster/
├── __init__.py                 # classFactory untuk QGIS
├── metadata.txt                # metadata plugin
├── plugin_main.py              # entry point: initGui/unload/run
├── gui/
│   ├── main_dialog.py          # controller GUI (pilih layer, bobot, jalankan)
│   └── __init__.py
├── core/
│   ├── engine.py               # orkestrator pipeline penilaian
│   ├── data_loader.py          # baca layer KKP -> Parcel, bangun konteks
│   ├── ahp.py                  # eigenvector + Consistency Ratio
│   ├── adqr_calculator.py      # agregasi ADQR + klasifikasi confidence/buffer
│   ├── classification.py       # Jenks Natural Breaks + GVF
│   ├── spatial_processing.py   # Heatmap ADQR & Confidence Buffer (QGIS API)
│   └── quality/
│       ├── __init__.py         # BaseAssessor, ikb_from_scores, registry
│       ├── completeness.py
│       ├── logical_consistency.py
│       ├── positional_accuracy.py
│       ├── thematic_accuracy.py
│       └── temporal_accuracy.py
├── ai/
│   ├── __init__.py             # AIPipeline
│   ├── ocr_module.py
│   ├── segmentation_module.py
│   ├── georeferencing_module.py
│   └── llm_module.py
├── models/
│   └── schema.py               # Parcel, QualityScore, IKBResult, ADQRResult
├── resources/
│   └── config/
│       ├── ahp_weights.json
│       └── classification.json
└── docs/                       # SRS, SAD/TDD, diagram UML
```

**Pemetaan ke permintaan pengguna:** GUI di `gui/main_dialog.py`, perhitungan di `core/adqr_calculator.py` (+ modul quality), eksekusi GIS di `core/spatial_processing.py` — persis pemisahan `main_dialog.py` / `adqr_calculator.py` / `spatial_processing.py` yang diminta.

---

## 3. Alur Data (Data Flow)

Layer KKP → `DataLoader` → `list[Parcel]` + `context` → `QualityEngine` menjalankan lima `Assessor` → tiap `Parcel.ikb` terisi → `ADQRCalculator` menghasilkan `ADQRResult` (nilai, kategori, kelas confidence, lebar buffer) → `classification.classify` menghitung Jenks/GVF → `SpatialProcessor` menulis atribut & merender Heatmap + Buffer → GUI menampilkan peta & statistik.

Lihat `docs/01_system_flowchart.mermaid` untuk diagram alur sistem penuh.

---

## 4. Diagram UML

### 4.1 Use Case (`docs/02_use_case.mermaid`)
Memetakan aktor (Petugas Ukur, Analis GIS, Kepala Kantor, AI Engine) ke use case (memuat data, digitalisasi AI, lima penilaian, atur bobot AHP, hitung ADQR, buat heatmap/buffer, lihat peta, ekspor laporan).

### 4.2 Activity Diagram (`docs/03_activity_diagram.mermaid`)
Alur kerja langkah demi langkah: pilih layer → atur & validasi bobot → muat parcel → loop penilaian per bidang → klasifikasi Jenks → tulis atribut → render heatmap & buffer → tampilkan hasil → ekspor.

### 4.3 Class Diagram (`docs/04_class_diagram.mermaid`)
Relasi antar kelas: `ProbaKadasterPlugin → MainDialog → QualityEngine`; `QualityEngine` mengomposisikan `DataLoader`, `BaseAssessor` (5 turunan), `ADQRCalculator` (memakai `AHPCalculator`), `Classifier`; `SpatialProcessor` menghasilkan produk visual; `AIPipeline` memberi umpan data.

### 4.4 ERD / Data Schema (`docs/05_erd.mermaid`)
Entitas: `PARCEL`, `QUALITY_ELEMENT`, `QUALITY_SCORE`, `IKB_RESULT`, `AHP_WEIGHT`, `ADQR_RESULT`, `BUFFER_ZONE` beserta relasinya. Menampung nilai S_ij, IKB, bobot AHP, dan skor ADQR sebagaimana diminta.

---

## 5. Rancangan Komponen Kunci

### 5.1 BaseAssessor (Strategy Pattern)
Setiap elemen kualitas adalah *strategy* yang mengimplementasikan `assess(parcel, context) -> IKBResult`. `ASSESSOR_REGISTRY` memetakan `QualityElement` ke kelasnya sehingga menambah elemen baru cukup mendaftarkan kelas — tanpa mengubah engine (Open/Closed Principle).

### 5.2 ADQRCalculator
Menggabungkan IKB tiap elemen dengan bobot AHP:

```
ADQR = IKB_LC·Egv_LC + IKB_PA·Egv_PA + IKB_C·Egv_C + IKB_TH·Egv_TH + IKB_TE·Egv_TE
```

Lalu memetakan ADQR → kategori & kelas heatmap, dan positional accuracy → kelas confidence & lebar buffer.

### 5.3 SpatialProcessor
- **Heatmap**: `QgsGraduatedSymbolRenderer` 5 kelas dari `classification.json`.
- **Buffer**: buffer cincin (`geom.buffer(w) − geom.buffer(−w)`) dengan lebar variabel per bidang, disimbolkan `QgsCategorizedSymbolRenderer` per kelas confidence.
- Guard `QGIS_AVAILABLE` memungkinkan modul di-import tanpa QGIS (untuk test).

### 5.4 AIPipeline
Interface stabil `run(scanned_map, reference_layer)`. Backend nyata (PaddleOCR, Mask R-CNN, SuperPoint+SuperGlue, LLM) dihubungkan lewat metode `_engine_*`/`_infer` tanpa mengubah pemanggil.

---

## 6. Teknologi

| Kategori | Pilihan |
|---|---|
| Host & GIS | QGIS 3.28+, PyQGIS (`qgis.core`, `qgis.gui`) |
| GUI | PyQt5 (Qt Widgets) |
| Bahasa | Python 3.9+ |
| Geoproses | QGIS Processing, GEOS (buffer/overlay), GDAL/OGR |
| Klasifikasi | Jenks Natural Breaks (implementasi internal) |
| AHP | Implementasi numerik internal (opsional NumPy) |
| OCR | Tesseract / PaddleOCR / EasyOCR / TrOCR |
| Segmentation | U-Net / DeepLabV3+ / Mask R-CNN / SegFormer |
| Georeferencing | SuperPoint + SuperGlue, RANSAC, TPS |
| LLM | Prompt Engineering + RAG |
| Konfigurasi | JSON |
| Pengujian | pytest (logika inti) |

---

## 7. Penanganan Kesalahan & Kualitas
- Bidang tanpa referensi/atribut menghasilkan IKB konservatif (0) dengan `detail.note`, bukan crash.
- Validasi bobot AHP (total & CR) sebelum agregasi.
- Operasi tulis atribut dibungkus transaksi `startEditing/commitChanges`.
- Logika inti punya cakupan unit test (contoh kriteria di SRS §6).

---

## 8. Rencana Pengembangan Bertahap
1. **v0.1** — Kerangka + logika inti (dokumen ini) & visualisasi dasar.
2. **v0.2** — Overlay kawasan & cek topologi via Processing; report generator.
3. **v0.3** — Integrasi backend AI (OCR + Segmentation) untuk KW4–KW6.
4. **v0.4** — Georeferencing & LLM; peta before/after otomatis.
5. **v1.0** — Uji lapangan, optimasi kinerja, paket QGIS Plugin Repository.
