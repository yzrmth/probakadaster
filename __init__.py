# -*- coding: utf-8 -*-
"""ProbaKadaster - Plugin QGIS Penilaian Kualitas Data Kadaster Probabilistik.

Entry-point yang dipanggil QGIS untuk memuat plugin.
"""


def classFactory(iface):  # pragma: no cover - dipanggil oleh QGIS
    """Load ProbaKadasterPlugin.

    :param iface: qgis.gui.QgisInterface instance milik QGIS.
    """
    from .plugin_main import ProbaKadasterPlugin
    return ProbaKadasterPlugin(iface)
