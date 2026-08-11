# Software Requirements Specification (SRS)
## Plugin ProbaKadaster — Penilaian Kualitas Data & Peta Kadaster Probabilistik

| | |
|---|---|
| **Produk** | ProbaKadaster (plugin QGIS) |
| **Versi** | 0.1.0 (draft) |
| **Penyusun** | Rizal Adhi Pratama |
| **Basis metodologi** | ISO 19157, AHP, ADQR; Permen ATR/BPN No. 3 Tahun 2023; PMNA/Kepala BPN No. 3 Tahun 1997 |
| **Standar dokumen** | Adaptasi IEEE Std 830 |

---

## 1. Pendahuluan

### 1.1 Tujuan
Dokumen ini mendefinisikan kebutuhan perangkat lunak ProbaKadaster, sebuah plugin QGIS untuk:
1. menilai kualitas data bidang tanah terdaftar berdasarkan lima elemen kualitas data ISO 19157;
2. mengagregasikan hasil penilaian menjadi **Aggregate Data Quality Rating (ADQR)** menggunakan bobot **AHP**;
3. memvisualisasikan hasil sebagai **Peta Kadaster Probabilistik** (Heatmap ADQR + Positional Confidence Buffer);
4. menyediakan pipeline **AI** (OCR, Segmentation, Georeferencing, LLM) untuk digitalisasi peta analog dan peningkatan kualitas bidang KW4–KW6.

### 1.2 Ruang Lingkup
Perangkat lunak berjalan sebagai plugin di QGIS 3.28+. Masukan utamanya adalah layer vektor bidang tanah dari sistem KKP ATR/BPN beserta data referensi (ortofoto, RTRW, kawasan hutan/sempadan/lindung). Keluaran utamanya adalah nilai kualitas per bidang, dua produk peta probabilistik, statistik agregat, dan laporan.

### 1.3 Definisi & Akronim
- **IKB** — Indeks Kelas Bidang (indeks kualitas per elemen, rentang 0–1).
- **ADQR** — Aggregate Data Quality Rating (kualitas total, 0–1).
- **AHP** — Analytic Hierarchy Process (penentuan bobot antar elemen).
- **KW** — Kelas Kualitas kelengkapan dokumen (KW1–KW6).
- **CR** — Consistency Ratio (AHP) / Circularity Ratio (positional accuracy), sesuai konteks.
- **GVF** — Goodness of Variance Fit (kualitas klasifikasi Jenks).
- **Confidence Buffer** — zona ketidakpastian posisi batas bidang.

---

## 2. Deskripsi Umum

### 2.1 Perspektif Produk
ProbaKadaster memanfaatkan QGIS sebagai host (rendering peta, manajemen layer, CRS, Processing). Logika penilaian dipisah dari GUI agar dapat diuji unit dan dipakai ulang (mis. via PyQGIS headless).

### 2.2 Kelas Pengguna
| Aktor | Deskripsi | Hak akses utama |
|---|---|---|
| Petugas Ukur | Menyiapkan & mengunggah data, menjalankan digitalisasi AI | Load data, jalankan AI, jalankan penilaian |
| Analis GIS | Mengatur bobot AHP, menjalankan penilaian, membuat peta | Semua fitur analitik & visualisasi |
| Kepala Kantor | Meninjau hasil untuk pengambilan keputusan | Lihat peta, lihat & ekspor laporan |
| AI Engine (sistem) | Menjalankan OCR/Segmentation/Georeferencing/LLM | Otomatis (dipicu Petugas Ukur) |

### 2.3 Batasan
- Bergantung pada QGIS Python API dan CRS berbasis meter untuk perhitungan buffer.
- Backend AI bersifat pluggable; model deep learning tidak dibundel.
- Perhitungan positional accuracy membutuhkan data referensi (ortofoto).

### 2.4 Asumsi & Ketergantungan
- Data KKP memiliki minimal atribut NIB, luas, jenis hak, tanggal terbit, dan KW.
- Ortofoto/RTRW/kawasan tersedia sebagai layer referensi ber-georeferensi.

---

## 3. Kebutuhan Fungsional

Notasi prioritas: **M** (Must), **S** (Should), **C** (Could).

### 3.1 Manajemen Data
| ID | Kebutuhan | Prioritas |
|---|---|---|
| FR-01 | Sistem memuat layer vektor bidang tanah (Polygon) dari QGIS. | M |
| FR-02 | Sistem memetakan kolom layer ke field standar (NIB, luas KKP, luas SU, KW, jenis hak, dll) yang dapat dikonfigurasi pengguna. | M |
| FR-03 | Sistem memvalidasi skema dan melaporkan field yang hilang. | S |
| FR-04 | Sistem mendeteksi data ganda pada atribut unik (Nomor Hak, Nomor SU, NIB). | M |

### 3.2 Penilaian Kualitas (ISO 19157)
| ID | Kebutuhan | Prioritas |
|---|---|---|
| FR-05 | **Completeness** — menghitung IKB omission & commission serta skor KW1–KW6. | M |
| FR-06 | **Logical Consistency** — menilai konsistensi konseptual (jenis hak vs kawasan) dan topologi (overlap/gap). | M |
| FR-07 | **Positional Accuracy** — menghitung Circularity Ratio, Near Distance, selisih luas poligon, dan uji-z (α=0.05) terhadap referensi. | M |
| FR-08 | **Thematic Accuracy** — uji toleransi luas ΔL ≤ ½√L (PMNA/BPN 3/1997). | M |
| FR-09 | **Temporal Accuracy** — menilai usia data dengan bobot AHP (<5, 5–10, 10–20, >20 tahun). | M |
| FR-10 | Setiap elemen menghasilkan IKB pada rentang 0–1. | M |

### 3.3 AHP & Agregasi ADQR
| ID | Kebutuhan | Prioritas |
|---|---|---|
| FR-11 | Sistem menerima matriks pairwise comparison per narasumber & menggabungkannya (geometric mean). | S |
| FR-12 | Sistem menghitung eigenvector (bobot), λmax, CI, dan CR; menolak bila CR > 0.10. | M |
| FR-13 | Sistem menghitung ADQR = Σ(IKBₑ × Egvₑ) untuk lima elemen. | M |
| FR-14 | Sistem mengklasifikasikan ADQR ke kategori Sangat Baik…Sangat Rendah. | M |

### 3.4 Peta Kadaster Probabilistik
| ID | Kebutuhan | Prioritas |
|---|---|---|
| FR-15 | Sistem mengklasifikasikan ADQR dengan Natural Breaks (Jenks) dan menghitung GVF. | M |
| FR-16 | Sistem membuat **Heatmap ADQR** (5 kelas, gradasi Merah–Kuning–Hijau). | M |
| FR-17 | Sistem menentukan lebar **Positional Confidence Buffer** (0.25/0.50/1.00/2.00/3.00 m) per kelas confidence. | M |
| FR-18 | Sistem membangun layer buffer (zone of uncertainty) dan menata simbol per kelas. | M |
| FR-19 | Sistem menuliskan hasil (adqr, kualitas, pos_conf, buffer_m) ke atribut layer. | M |

### 3.5 Pipeline AI (Peningkatan Kualitas)
| ID | Kebutuhan | Prioritas |
|---|---|---|
| FR-20 | Sistem mengekstrak teks/atribut peta analog via OCR. | C |
| FR-21 | Sistem mengekstrak batas bidang via AI Segmentation. | C |
| FR-22 | Sistem melakukan georeferensi otomatis poligon hasil segmentasi. | C |
| FR-23 | Sistem menggunakan LLM untuk interpretasi semantik & deteksi inkonsistensi. | C |
| FR-24 | Hasil AI dapat dialirkan sebagai input penilaian kualitas (bidang KW4–KW6). | S |

### 3.6 Statistik, Laporan & UI
| ID | Kebutuhan | Prioritas |
|---|---|---|
| FR-25 | Sistem menampilkan statistik agregat (rata-rata, min, maks, SDAM/SDCM, GVF, jumlah bidang). | M |
| FR-26 | Sistem menampilkan distribusi bidang per kelas confidence. | S |
| FR-27 | Sistem mengekspor laporan (CSV/PDF/HTML) beserta peta before/after. | S |
| FR-28 | Sistem menampilkan progress bar & pesan status selama pemrosesan. | S |

---

## 4. Kebutuhan Non-Fungsional
| ID | Kategori | Kebutuhan |
|---|---|---|
| NFR-01 | Kinerja | Menilai 10.000 bidang dalam waktu wajar (< 2 menit pada mesin standar) tanpa membekukan UI. |
| NFR-02 | Keandalan | Kegagalan pada satu bidang tidak menghentikan pemrosesan bidang lain; kesalahan ditampilkan jelas. |
| NFR-03 | Ketertelusuran | Semua nilai IKB & ADQR dapat ditelusuri ke skor S_ij penyusunnya (kolom detail). |
| NFR-04 | Portabilitas | Berjalan di QGIS 3.28+ pada Windows, Linux, macOS. |
| NFR-05 | Modularitas | Logika inti bebas dependensi GUI/QGIS untuk pengujian unit. |
| NFR-06 | Keteruji | Modul perhitungan memiliki unit test dengan data referensi. |
| NFR-07 | Konfigurabilitas | Bobot AHP, ambang klasifikasi, dan lebar buffer dapat diubah via file konfigurasi. |
| NFR-08 | Lokalisasi | Antarmuka berbahasa Indonesia; siap diperluas ke bahasa lain (Qt tr). |

---

## 5. Aturan Klasifikasi (Referensi Perhitungan)

**Kategori ADQR**

| Rentang | Kategori |
|---|---|
| 0.81–1.00 | Sangat Baik |
| 0.61–0.80 | Baik |
| 0.41–0.60 | Sedang |
| 0.21–0.40 | Rendah |
| 0.00–0.20 | Sangat Rendah |

**Kelas Confidence & Lebar Buffer**

| Interval | Confidence | Buffer |
|---|---|---|
| 0.81–1.00 | Very High | 0.25 m |
| 0.61–0.80 | High | 0.50 m |
| 0.41–0.60 | Moderate | 1.00 m |
| 0.21–0.40 | Low | 2.00 m |
| 0.00–0.20 | Very Low | 3.00 m |

**Kelengkapan Dokumen (KW):** KW1=1.00, KW2=0.83, KW3=0.67, KW4=0.50, KW5=0.33, KW6=0.17.

**Bobot Usia Temporal (AHP):** <5 th=0.313, 5–10 th=0.289, 10–20 th=0.224, >20 th=0.174.

---

## 6. Kriteria Penerimaan (Contoh)
- Diberikan bidang dengan seluruh IKB=1 dan bobot valid, ADQR bernilai 1.00 dan kategori "Sangat Baik".
- Diberikan bidang tanpa data referensi, positional accuracy bernilai 0 dan buffer 3.00 m (Very Low).
- Matriks AHP dengan CR>0.10 ditolak dan pengguna diminta merevisi.
- Selisih luas ΔL > ½√L memberi skor thematic 0.
