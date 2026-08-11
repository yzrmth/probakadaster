# -*- coding: utf-8 -*-
"""OCR - ekstraksi teks/atribut dari peta kadaster analog (NIB, luas, skala, dll).

Backend yang direkomendasikan: Tesseract, PaddleOCR, EasyOCR, atau TrOCR
(CRNN/Transformer). Kelas ini adalah adapter; implementasi nyata mengisi
metode `_engine_extract`.
"""


class OCRModule:
    def __init__(self, engine="paddleocr", lang="ind"):
        self.engine = engine
        self.lang = lang

    def extract(self, image_path):
        """Kembalikan dict atribut terstruktur hasil OCR.

        Contoh keluaran:
            {"no_bidang": "01234", "luas": 1250, "wilayah": "Sungai Raya",
             "skala": "1:1000", "tahun": 1985}
        """
        raw = self._engine_extract(image_path)
        return self._structure(raw)

    # -- titik integrasi backend nyata ----------------------------------- #
    def _engine_extract(self, image_path):
        raise NotImplementedError("Hubungkan backend OCR di sini.")

    @staticmethod
    def _structure(raw_text):
        """Parsing teks mentah -> field terstruktur (regex/rule/LLM)."""
        return {}
