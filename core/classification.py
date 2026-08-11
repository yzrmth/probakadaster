# -*- coding: utf-8 -*-
"""Klasifikasi nilai ADQR dengan Natural Breaks (Jenks) dan Goodness of Variance Fit.

    GVF = (SDAM - SDCM) / SDAM
      SDAM = Sum of squared Deviations from Array Mean
      SDCM = Sum of squared Deviations from Class Means
    GVF -> 1 = klasifikasi makin baik.
"""

from typing import List, Tuple


def _sdam(values: List[float]) -> float:
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values)


def _sdcm(values: List[float], breaks: List[float]) -> float:
    sdcm = 0.0
    for lo, hi in zip(breaks[:-1], breaks[1:]):
        cls = [v for v in values if lo <= v <= hi]
        if cls:
            m = sum(cls) / len(cls)
            sdcm += sum((v - m) ** 2 for v in cls)
    return sdcm


def jenks_breaks(values: List[float], n_classes: int = 5) -> List[float]:
    """Hitung batas kelas Jenks. Implementasi dynamic programming standar."""
    data = sorted(values)
    n = len(data)
    if n == 0:
        return []
    if n <= n_classes:
        return [data[0]] + data

    mat1 = [[0] * (n_classes + 1) for _ in range(n + 1)]
    mat2 = [[0.0] * (n_classes + 1) for _ in range(n + 1)]
    for i in range(1, n_classes + 1):
        mat1[1][i] = 1
        for j in range(2, n + 1):
            mat2[j][i] = float("inf")

    for l in range(2, n + 1):
        s1 = s2 = w = 0.0
        for m in range(1, l + 1):
            i3 = l - m + 1
            val = data[i3 - 1]
            s2 += val * val
            s1 += val
            w += 1
            variance = s2 - (s1 * s1) / w
            i4 = i3 - 1
            if i4 != 0:
                for j in range(2, n_classes + 1):
                    if mat2[l][j] >= (variance + mat2[i4][j - 1]):
                        mat1[l][j] = i3
                        mat2[l][j] = variance + mat2[i4][j - 1]
        mat1[l][1] = 1
        mat2[l][1] = s2 - (s1 * s1) / w

    breaks = [0.0] * (n_classes + 1)
    breaks[n_classes] = data[-1]
    breaks[0] = data[0]
    k = n
    for j in range(n_classes, 1, -1):
        idx = int(mat1[k][j]) - 2
        breaks[j - 1] = data[idx]
        k = int(mat1[k][j]) - 1
    return breaks


def goodness_of_variance_fit(values: List[float], breaks: List[float]) -> float:
    sdam = _sdam(values)
    if sdam == 0:
        return 1.0
    sdcm = _sdcm(values, breaks)
    return (sdam - sdcm) / sdam


def classify(values: List[float], n_classes: int = 5) -> Tuple[List[float], float]:
    """Kembalikan (breaks, GVF)."""
    breaks = jenks_breaks(values, n_classes)
    gvf = goodness_of_variance_fit(values, breaks) if breaks else 0.0
    return breaks, round(gvf, 4)
