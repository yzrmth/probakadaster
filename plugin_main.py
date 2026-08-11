# -*- coding: utf-8 -*-
"""Titik masuk plugin: registrasi menu/toolbar QGIS dan pemanggilan dialog utama."""

import os

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction


class ProbaKadasterPlugin:
    """Kelas utama plugin. Menghubungkan QGIS iface dengan GUI ProbaKadaster."""

    MENU_TITLE = "&ProbaKadaster"

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = self.MENU_TITLE
        self.toolbar = self.iface.addToolBar("ProbaKadaster")
        self.toolbar.setObjectName("ProbaKadaster")
        self._dialog = None

    # ------------------------------------------------------------------ #
    # Lifecycle QGIS
    # ------------------------------------------------------------------ #
    def initGui(self):
        """Dipanggil QGIS saat plugin diaktifkan."""
        icon_path = os.path.join(self.plugin_dir, "resources", "icon.png")
        action = QAction(QIcon(icon_path),
                         self.tr("Penilaian Kualitas & Peta Probabilistik"),
                         self.iface.mainWindow())
        action.triggered.connect(self.run)
        action.setEnabled(True)

        self.toolbar.addAction(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)

    def unload(self):
        """Dipanggil QGIS saat plugin dinonaktifkan / QGIS ditutup."""
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    # ------------------------------------------------------------------ #
    # Aksi utama
    # ------------------------------------------------------------------ #
    def run(self):
        """Membuka dialog utama plugin (lazy import agar QGIS start cepat)."""
        from .gui.main_dialog import MainDialog
        if self._dialog is None:
            self._dialog = MainDialog(self.iface)
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    @staticmethod
    def tr(message):
        return QCoreApplication.translate("ProbaKadaster", message)
