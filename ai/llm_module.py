# -*- coding: utf-8 -*-
"""LLM - reasoning atas hasil OCR + atribut untuk ekstraksi informasi semantik
dan deteksi inkonsistensi (mis. jenis hak vs penggunaan, risiko overlap).

Teknik: Prompt Engineering + Retrieval-Augmented Generation (RAG).
"""


class LLMModule:
    def __init__(self, provider="local", model="llm"):
        self.provider = provider
        self.model = model

    def interpret(self, ocr_attrs, georef_context):
        """Kembalikan informasi terstruktur + rekomendasi tindak lanjut.

        Contoh:
            {"jenis_hak": "Hak Milik", "penggunaan": "Sawah",
             "konsistensi_luas": "Sesuai", "risiko_overlap": "Rendah",
             "rekomendasi": "Validasi Lapangan"}
        """
        return self._reason(ocr_attrs, georef_context)

    def _reason(self, ocr_attrs, georef_context):
        raise NotImplementedError("Hubungkan LLM/RAG di sini.")
