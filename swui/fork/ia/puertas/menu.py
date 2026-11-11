# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
FreeWorks > IA:
- "Puente IA" (se tilda): prende o apaga el servidor. Apagado al arrancar FreeCAD (privacidad).
- "Conectar la IA...": cómo conectar Claude Code (una sola vez por PC), con la clave para copiar
  y un botón para cambiarla.
"""

import FreeCAD
import FreeCADGui

from swui.compat import QtWidgets, exec_dialog

BRIDGE = "SWUI_IABridge"
CONNECT = "SWUI_IAConnect"


def _registry():
    from swui.fork.ia.herramientas import register_all
    from swui.fork.ia.terceros.registry import ToolRegistry

    return register_all(ToolRegistry())


def _set_checked(value):
    try:
        action = FreeCADGui.Command.get(BRIDGE).getAction()[0]
        action.setChecked(bool(value))
    except Exception:
        pass


def turn_on():
    """Prender el puente; si no se puede, avisa en castellano y deja el tilde apagado."""
    from swui.fork.ia.nucleo import config, puente

    try:
        url = puente.start(_registry())
    except OSError as exc:
        _set_checked(False)
        QtWidgets.QMessageBox.warning(
            FreeCADGui.getMainWindow(), "Puente IA",
            "No se pudo prender el puente IA en el puerto %d: %s\n\n¿Hay otro FreeCAD abierto con "
            "el puente prendido?" % (config.port(), exc))
        return False
    _set_checked(True)
    FreeCADGui.getMainWindow().statusBar().showMessage("Puente IA prendido (%s)" % url, 8000)
    return True


def turn_off():
    from swui.fork.ia.nucleo import puente

    puente.stop()
    _set_checked(False)
    FreeCADGui.getMainWindow().statusBar().showMessage("Puente IA apagado", 5000)


class _Bridge:
    def GetResources(self):
        return {"MenuText": "Puente IA",
                "ToolTip": ("Prende o apaga el puente para que la IA de su suscripción (Claude Code...) "
                            "maneje FreeWorks. Solo escucha en esta PC y pide clave."),
                "Checkable": False}

    def IsActive(self):
        return True

    def Activated(self, checked=None):
        from swui.fork.ia.nucleo import puente

        on = (not puente.running()) if checked is None else bool(checked)
        if on:
            turn_on()
        else:
            turn_off()


class _ConnectDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__(FreeCADGui.getMainWindow())
        from swui.fork.ia.nucleo import puente

        self.setWindowTitle("Conectar la IA")
        lay = QtWidgets.QVBoxLayout(self)
        state = "prendido" if puente.running() else "apagado"
        intro = QtWidgets.QLabel(
            "La IA de su suscripción maneja FreeWorks a través del puente IA (ahora: <b>%s</b>).<br><br>"
            "<b>1.</b> Active el puente: FreeWorks &gt; IA &gt; Puente IA.<br>"
            "<b>2.</b> Una sola vez por PC, copie esta línea y péguela en una terminal "
            "(PowerShell o la de Claude Code):" % state)
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.line = QtWidgets.QLineEdit()
        self.line.setReadOnly(True)
        self.line.setMinimumWidth(560)
        lay.addWidget(self.line)
        row = QtWidgets.QHBoxLayout()
        copy = QtWidgets.QPushButton("Copiar")
        copy.clicked.connect(self._copy)
        renew = QtWidgets.QPushButton("Cambiar la clave...")
        renew.clicked.connect(self._renew)
        row.addWidget(copy)
        row.addWidget(renew)
        row.addStretch(1)
        lay.addLayout(row)
        outro = QtWidgets.QLabel(
            "<b>3.</b> Abra Claude Code y pídale lo que quiera: va a ver FreeWorks como "
            "\"freeworks\".<br><br>La línea tiene la clave del puente: no la comparta. Si cambia la "
            "clave, hay que volver a pegar la línea (antes, <i>claude mcp remove freeworks</i>).")
        outro.setWordWrap(True)
        lay.addWidget(outro)
        ok = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        ok.rejected.connect(self.reject)
        lay.addWidget(ok)
        self._fill()

    def _fill(self):
        from swui.fork.ia.nucleo import config

        self.line.setText(config.claude_command())

    def _copy(self):
        QtWidgets.QApplication.clipboard().setText(self.line.text())
        FreeCADGui.getMainWindow().statusBar().showMessage("Línea copiada", 4000)

    def _renew(self):
        from swui.fork.ia.nucleo import config, puente

        answer = QtWidgets.QMessageBox.question(
            self, "Cambiar la clave",
            "La clave vieja deja de servir y hay que volver a conectar la IA. ¿Cambiarla?")
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        config.new_token()
        if puente.running():  # el servidor usa la clave con la que arrancó
            turn_off()
            turn_on()
        self._fill()


class _Connect:
    def GetResources(self):
        return {"MenuText": "Conectar la IA...",
                "ToolTip": "Cómo conectar Claude Code (u otra IA de suscripción) con FreeWorks"}

    def IsActive(self):
        return True

    def Activated(self):
        exec_dialog(_ConnectDialog())


def install():
    for name, cmd in ((BRIDGE, _Bridge()), (CONNECT, _Connect())):
        try:
            FreeCADGui.addCommand(name, cmd)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] IA: %s ya registrado\n" % name)
