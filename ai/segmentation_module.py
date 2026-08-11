# -*- coding: utf-8 -*-
"""AI Segmentation - klasifikasi piksel citra peta menjadi objek spasial.

Kelas objek: batas bidang, simbol, teks, bangunan, lainnya.
Backend: U-Net, DeepLabV3+, Mask R-CNN, FCN, SegFormer.
Output: poligon bidang tanah (geometri) hasil vektorisasi mask.
"""


class SegmentationModule:
    CLASSES = ["batas_bidang", "simbol", "teks", "bangunan", "lainnya"]

    def __init__(self, model="mask_rcnn"):
        self.model = model

    def segment(self, image_path):
        """Kembalikan list geometri (WKT/koordinat) bidang tanah terdeteksi."""
        mask = self._infer(image_path)
        return self._vectorize(mask)

    def _infer(self, image_path):
        raise NotImplementedError("Hubungkan model deep learning di sini.")

    @staticmethod
    def _vectorize(mask):
        """Ubah mask raster batas bidang -> poligon (mis. gdal_polygonize)."""
        return []
