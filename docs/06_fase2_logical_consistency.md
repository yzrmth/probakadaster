# Fase 2 — Konsistensi Konseptual (Logical Consistency)

Sub-elemen dari **Logical Consistency** (ISO 19157) yang menilai kesesuaian
jenis hak atas tanah terhadap fungsi kawasan/peruntukan ruang (kawasan hutan,
sempadan sungai, kawasan lindung, RTRW, fasum/fasos). Sub-elemen kedua,
**Konsistensi Topologi** (bebas overlap/gap/self-intersection antar
persil), belum diimplementasikan — di luar cakupan dokumen ini.

---

## 1. Alur Penilaian

```
1. PERSIAPAN DATA
   - Data bidang tanah dari KKP ATR/BPN (fisik & yuridis) - layer yang sama
     dipakai di seluruh elemen kualitas.
   - Data referensi kawasan (RTRW, kawasan hutan, sempadan sungai, kawasan
     lindung, fasum/fasos, atau kategori lain) - ditambahkan lewat tab
     "Pengaturan" -> "+ Tambah Referensi": upload file, pilih atribut acuan,
     pilih jenis hak yang dilarang. Jumlah & jenis referensi sepenuhnya
     ditentukan user (tidak ada kategori baku bawaan aplikasi).
        v
2. IDENTIFIKASI KAWASAN / OBJEK
   - Overlay spasial bidang tanah terhadap tiap file referensi yang sudah
     ditambahkan, untuk menentukan referensi mana saja yang "menaungi"
     tiap bidang.
        v
3. PEMERIKSAAN KESESUAIAN REGULASI
   - Bandingkan jenis hak atas tanah bidang dengan daftar "Jenis Hak Tidak
     Sesuai" yang didefinisikan user untuk tiap entry referensi (tab
     Pengaturan).
        v
4. PENILAIAN (SKOR BINER)
   - S_ij = 1 (sesuai / tidak termasuk larangan)
   - S_ij = 0 (tidak sesuai / termasuk larangan)
        v
5. PERHITUNGAN IKB_CC
   - IKB_cc = (1 / (Sigma n)) * Sigma_i Sigma_j S_ij   (lihat §4)
        v
6. HASIL & INTERPRETASI
   - Nilai IKB_cc pada rentang 0-1 (semakin mendekati 1 semakin baik).
   - Dipakai sebagai bahan evaluasi kualitas data & rekomendasi perbaikan.
```

### Pemetaan ke kode

| Langkah | Modul / fungsi |
|---|---|
| 1. Persiapan data (referensi kawasan) | `resources/config/conceptual_rules.json` (aturan, dikelola lewat GUI) + `resources/reference_layers/*.{gpkg,shp,geojson,json}` (file per entry, nama file dicatat eksplisit di JSON) |
| 2. Identifikasi kawasan (overlay spasial) | `core/reference_layers.py::build_kawasan_overlay()` — spatial index + reprojeksi CRS bila layer referensi beda CRS dari layer bidang tanah |
| 3-4. Kesesuaian regulasi + skor biner | `core/quality/logical_consistency.py::LogicalConsistencyAssessor._conceptual()`, aturan diambil dari `core/reference_layers.py::load_rules()` |
| 5. Perhitungan IKB_cc | `LogicalConsistencyAssessor.assess()` — digabung dengan skor topologi (`IKB_LC = (konseptual + topologi) / 2`) |
| 6. Hasil & interpretasi | `core/adqr_calculator.py::ADQRCalculator.compute()` — IKB_LC dikalikan bobot AHP `logical`, masuk ke `ADQRResult.ikb_breakdown["logical"]` dan nilai `ADQR` agregat |

Orkestrasi penuh: `core/engine.py::QualityEngine.run()` memanggil
`DataLoader.build_context()` (yang membaca referensi kawasan & membangun
overlay) sekali di awal, lalu menjalankan tiap `Assessor` (termasuk
`LogicalConsistencyAssessor`) per bidang.

---

## 2. Skor Biner (S_ij)

| Simbol | Keterangan |
|---|---|
| ✅ 1 | Valid / Sesuai |
| ❌ 0 | Tidak valid / Tidak sesuai |

Rentang nilai IKB: **0 (tidak lengkap/berlebih)** → **1 (sangat lengkap/sangat
baik)**, direpresentasikan merah → hijau pada heatmap (`classification.json`,
band `adqr_confidence_heatmap`).

---

## 3. Aturan Konseptual (dinamis, dikelola lewat GUI)

Berbeda dari versi sebelumnya, aplikasi **tidak lagi membawa daftar kawasan
baku** (kawasan hutan, sempadan sungai, dst. beserta dasar hukumnya). Tab
**Pengaturan** murni menampilkan apa pun yang sudah ada di
`resources/config/conceptual_rules.json` — kosong sampai user menambahkan
entry pertama lewat **"+ Tambah Referensi"**.

Tiap entry (satu baris di tab Pengaturan) disimpan dengan skema:

```json
"kawasan_hutan": {
  "label": "Kawasan Hutan",
  "file": "kawasan_hutan.gpkg",
  "atribut": "FUNGSI",
  "jenis_hak_dilarang": ["HM", "HGU", "HGB", "HP"],
  "catatan": "UU No. 41 Tahun 1999 tentang Kehutanan - kawasan hutan dikuasai negara..."
}
```

- `label` — nama bebas yang diketik user (mis. "Kawasan Hutan Produksi").
- `file` — nama file referensi hasil upload (di `resources/reference_layers/`).
- `atribut` — nama kolom pada file referensi yang dipilih user setelah
  upload (dibaca otomatis dari file, lihat §5). **Belum dipakai** oleh
  logika overlay saat ini — overlay murni cek irisan geometri, bukan
  filter nilai atribut; kolom ini baru tersimpan sebagai metadata untuk
  pengembangan lanjutan.
- `jenis_hak_dilarang` — daftar kode jenis hak yang dianggap tidak sesuai
  untuk entry ini (`*` = seluruh jenis hak, dipakai mis. untuk aturan RTRW
  yang melarang semua jenis hak tanpa terkecuali).
- `catatan` — teks bebas opsional, tempat mencatat dasar hukum/analisis
  seperti pada tabel regulasi versi sebelumnya (UU 41/1999 tentang
  Kehutanan, PP 38/2011 tentang Sungai, Keppres 32/1990 tentang Pengelolaan
  Kawasan Lindung, UU 26/2007 tentang Penataan Ruang, UU 1/2011 tentang
  Perumahan dan Kawasan Permukiman, dst.) — tidak lagi baku/wajib, murni
  referensi manual.

Kode jenis hak yang tersedia di dialog Tambah/Edit Referensi:

| Kode | Jenis Hak |
|---|---|
| `*` | Semua Jenis Hak (mis. aturan RTRW yang melarang seluruh jenis hak) |
| `HM` | Hak Milik |
| `HGU` | Hak Guna Usaha |
| `HGB` | Hak Guna Bangunan |
| `HP` | Hak Pakai |
| `HPL` | Hak Pengelolaan |
| `HMSRS` | Hak Milik atas Satuan Rumah Susun |
| `HT` | Hak Tanggungan |
| `TN_WAKAF` | Tanah Negara / Wakaf |

---

## 4. Formula IKB_cc

```
           1
IKB_cc = ----- * Sigma(i=1..m) Sigma(j=1..n) S_ij
         Sigma n
```

- `S_ij` = skor elemen ke-j pada unsur ke-i (0 atau 1)
- `m` = jumlah unsur
- `n` = jumlah elemen kualitas data

Pada implementasi saat ini, `S_ij` untuk konsistensi konseptual adalah satu
skor biner per bidang (1 = tidak melanggar kawasan manapun yang
ditumpangtindihkan, 0 = melanggar setidaknya satu kawasan) — lihat
`_conceptual()` di `logical_consistency.py`.

---

## 5. Cara Mendapatkan Output (langkah praktis di plugin)

1. **Tambah referensi** — buka tab **Pengaturan**, klik **"+ Tambah
   Referensi"**. Dialog yang muncul:
   a. **Nama** — nama bebas untuk entry ini (mis. "Kawasan Hutan").
   b. **Pilih File...** — pilih file vektor (GeoPackage `.gpkg`, Shapefile
      `.shp` — sidecar `.shx/.dbf/.prj` ikut tersalin otomatis saat
      disimpan — atau GeoJSON). Field-field yang ada pada file langsung
      terbaca begitu file dipilih.
   c. **Atribut Acuan** — pilih salah satu field yang baru terbaca.
   d. **Jenis Hak Tidak Sesuai** — buka menu, centang kode jenis hak yang
      dilarang untuk kawasan/objek ini (lihat tabel kode di §3).
   e. **Catatan** (opsional) — dasar hukum/analisis, bebas.
   f. Klik **Simpan** — file disalin ke `resources/reference_layers/`
      (nama file mengikuti nama entry) dan aturan tersimpan ke
      `conceptual_rules.json`, langsung berlaku untuk run berikutnya
      tanpa restart QGIS.
2. **Edit / Hapus** — tiap baris di tabel Pengaturan punya tombol **Edit**
   (membuka dialog yang sama, terisi otomatis dengan data entry tsb — pilih
   file baru untuk mengganti data, atau biarkan kosong untuk memakai file
   yang sudah ada) dan **Hapus** (menghapus entry dari
   `conceptual_rules.json` setelah konfirmasi; file fisik di
   `resources/reference_layers/` tidak ikut terhapus).
3. **Jalankan penilaian** — tab **Penilaian**, pilih layer bidang tanah, atur
   bobot AHP, klik **Jalankan Penilaian + Buat Peta Probabilistik**. Tab
   **Log** menampilkan referensi kawasan yang ditemukan/tidak ditemukan di
   awal proses, lalu progres penilaian per bidang.
4. **Lihat hasil** — nilai IKB Logical Consistency ikut teragregasi ke kolom
   `adqr` dan `kualitas` pada layer bidang tanah (`_write_adqr_fields()`),
   serta ke Heatmap ADQR dan statistik agregat pada tab Penilaian.

   **Keterbatasan saat ini:** tidak seperti Completeness (yang punya tombol
   & tab hasil tersendiri di Fase 1), IKB Logical Consistency per bidang
   belum ditampilkan di tabel terpisah — nilainya hanya tersedia sebagai
   `ADQRResult.ikb_breakdown["logical"]` di dalam objek `Parcel`, tergabung
   ke nilai ADQR akhir. Untuk audit detail per bidang, perlu ditambahkan tab
   "Hasil Logical Consistency" yang meniru pola `_build_completeness_tab()`
   — belum dibuat karena belum diminta.
