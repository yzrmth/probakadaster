# ProbaKadaster

Plugin QGIS untuk **penilaian kualitas data bidang tanah** (ISO 19157 + AHP/ADQR)
dan pembuatan **Peta Kadaster Probabilistik**: *Heatmap ADQR* dan
*Positional Confidence Buffer*. Dilengkapi kerangka pipeline **AI**
(OCR, Segmentation, Georeferencing, LLM) untuk digitalisasi peta analog
dan peningkatan kualitas bidang KW4–KW6.

## Instalasi (pengembangan)
1. Salin folder `probakadaster/` ke direktori plugin QGIS:
   - Windows: `%APPDATA%/QGIS/QGIS3/profiles/default/python/plugins/`
   - Linux/macOS: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
2. Buka QGIS → menu **Plugins → Manage and Install Plugins** → aktifkan *ProbaKadaster*.
3. Ikon plugin muncul di toolbar → buka dialog utama.

## Penggunaan singkat
1. Pilih layer bidang tanah (Polygon, CRS meter, mis. UTM).
2. Atur bobot AHP tiap elemen (total dinormalisasi ke 1).
3. Klik **Jalankan Penilaian** → plugin menghitung IKB, ADQR, lalu membuat
   Heatmap ADQR dan Confidence Buffer, serta menampilkan statistik.
4. Ekspor laporan bila diperlukan.

## Struktur & dokumentasi
- Kode: `gui/` (UI), `core/` (logika & GIS), `ai/` (pipeline AI), `models/` (domain).
- Dokumen: `docs/SRS.md`, `docs/SAD_TDD.md`, dan diagram `docs/*.mermaid`
  (flowchart sistem, use case, activity, class, ERD).

## Uji logika inti (tanpa QGIS)
```bash
python -m pytest tests/
```

## Basis metodologi
ISO 19157; Permen ATR/BPN No. 3 Tahun 2023; PMNA/Kepala BPN No. 3 Tahun 1997;
AHP (Saaty); ADQR; Natural Breaks (Jenks).
