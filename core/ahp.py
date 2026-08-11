# -*- coding: utf-8 -*-
"""Analytic Hierarchy Process (AHP).

Menghitung bobot prioritas (eigenvector) antar elemen kualitas dari matriks
pairwise comparison, sekaligus menguji konsistensi (Consistency Ratio).

Rumus (mengikuti slide penelitian):
    CI = (lambda_max - n) / (n - 1)
    CR = CI / RI          -> konsisten jika CR <= 0.10
"""

from typing import Dict, List, Sequence

# Random Index (Saaty) untuk n kriteria.
RANDOM_INDEX = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12,
                6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}


class AHPResult:
    def __init__(self, weights, lambda_max, ci, cr, consistent):
        self.weights = weights            # List[float], jumlah = 1
        self.lambda_max = lambda_max
        self.ci = ci
        self.cr = cr
        self.consistent = consistent

    def as_dict(self, labels: Sequence[str]) -> Dict[str, float]:
        return {label: w for label, w in zip(labels, self.weights)}


class AHPCalculator:
    """Menghitung eigenvector prioritas dari matriks perbandingan berpasangan."""

    def __init__(self, cr_threshold: float = 0.10):
        self.cr_threshold = cr_threshold

    def compute(self, matrix: List[List[float]]) -> AHPResult:
        """Hitung bobot prioritas + konsistensi.

        :param matrix: matriks pairwise n x n (matrix[i][j] = kepentingan i thd j).
        :returns: AHPResult
        """
        n = len(matrix)
        self._validate(matrix, n)

        # 1. Normalisasi kolom -> rata-rata baris = eigenvector (bobot prioritas).
        col_sums = [sum(matrix[i][j] for i in range(n)) for j in range(n)]
        weights = []
        for i in range(n):
            row_norm = sum(matrix[i][j] / col_sums[j] for j in range(n))
            weights.append(row_norm / n)

        # 2. lambda_max = rata-rata dari (Aw)_i / w_i
        aw = [sum(matrix[i][j] * weights[j] for j in range(n)) for i in range(n)]
        lambda_max = sum(aw[i] / weights[i] for i in range(n)) / n

        # 3. Consistency Index & Ratio
        ci = (lambda_max - n) / (n - 1) if n > 1 else 0.0
        ri = RANDOM_INDEX.get(n, 1.49)
        cr = ci / ri if ri > 0 else 0.0
        consistent = cr <= self.cr_threshold

        return AHPResult(weights, lambda_max, ci, cr, consistent)

    def aggregate_experts(self, matrices: List[List[List[float]]]) -> List[List[float]]:
        """Gabungkan matriks banyak narasumber via geometric mean (aturan AHP grup)."""
        if not matrices:
            raise ValueError("Minimal satu matriks narasumber diperlukan.")
        n = len(matrices[0])
        agg = [[1.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                prod = 1.0
                for m in matrices:
                    prod *= m[i][j]
                agg[i][j] = prod ** (1.0 / len(matrices))
        return agg

    @staticmethod
    def _validate(matrix, n):
        if n == 0 or any(len(row) != n for row in matrix):
            raise ValueError("Matriks AHP harus persegi (n x n).")
