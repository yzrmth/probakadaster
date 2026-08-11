# ProbaKadaster

Plugin QGIS untuk penilaian kualitas data bidang tanah (ISO 19157 + AHP/ADQR) dan pembuatan Peta Kadaster Probabilistik (Heatmap ADQR & Positional Confidence Buffer), dilengkapi modul AI untuk digitalisasi kadaster.

## Persyaratan

- QGIS versi 3.28 atau lebih baru

## Instalasi Plugin di QGIS

### Opsi 1: Install dari folder plugin QGIS (manual)

1. Salin (atau clone) seluruh folder repo ini ke direktori plugin QGIS:
   - Windows: `C:\Users\<username>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - Pastikan nama foldernya `probakadaster` (harus sama dengan nama folder repo/berisi `metadata.txt`).
2. Buka QGIS, lalu masuk ke menu **Plugins > Manage and Install Plugins...**
3. Pilih tab **Installed**, cari **ProbaKadaster**, lalu centang untuk mengaktifkannya.
4. Plugin akan muncul di menu **ProbaKadaster** dan toolbar QGIS.

### Opsi 2: Install dari file ZIP

1. Buat file ZIP dari folder plugin ini (pastikan `metadata.txt` ada di root ZIP, bisa di dalam satu folder `probakadaster/`).
2. Di QGIS, buka **Plugins > Manage and Install Plugins... > Install from ZIP**.
3. Pilih file ZIP tersebut, lalu klik **Install Plugin**.
4. Aktifkan plugin di tab **Installed** jika belum otomatis aktif.

## Menjalankan Plugin

Setelah aktif, buka plugin melalui menu **ProbaKadaster** atau ikon toolbar **Penilaian Kualitas & Peta Probabilistik**.
