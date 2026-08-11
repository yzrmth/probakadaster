# -*- coding: utf-8 -*-
"""Pipeline AI untuk digitalisasi & peningkatan kualitas data kadaster.

Urutan: Input (peta analog) -> OCR + AI Segmentation -> Georeferencing -> LLM
        -> output data vektor + atribut siap dinilai kualitasnya.

Modul di sini berupa *interface* yang dapat di-plug ke backend nyata
(Tesseract/PaddleOCR, U-Net/Mask R-CNN, SuperPoint/SuperGlue, LLM) tanpa
mengubah kode pemanggil.
"""

from .ocr_module import OCRModule
from .segmentation_module import SegmentationModule
from .georeferencing_module import GeoreferencingModule
from .llm_module import LLMModule


class AIPipeline:
    """Rangkaian tahap AI untuk mengubah peta kadaster analog jadi data digital."""

    def __init__(self, ocr=None, seg=None, georef=None, llm=None):
        self.ocr = ocr or OCRModule()
        self.seg = seg or SegmentationModule()
        self.georef = georef or GeoreferencingModule()
        self.llm = llm or LLMModule()

    def run(self, scanned_map_path, reference_layer=None):
        """Jalankan seluruh tahap. Kembalikan dict hasil per tahap."""
        text = self.ocr.extract(scanned_map_path)
        polygons = self.seg.segment(scanned_map_path)
        georef = self.georef.align(polygons, reference_layer)
        semantic = self.llm.interpret(text, georef)
        return {"ocr": text, "polygons": polygons,
                "georeferenced": georef, "semantic": semantic}


__all__ = ["AIPipeline", "OCRModule", "SegmentationModule",
           "GeoreferencingModule", "LLMModule"]
