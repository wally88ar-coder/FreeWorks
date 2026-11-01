# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Respaldo de la IA (decisión del usuario, 01/11): UNA copia por documento, la de antes del primer
cambio de la IA desde la última vez que el usuario guardó. Los scripts siguientes no la pisan.
Cuando el usuario guarda el documento, se borra: se entiende que aceptó lo que hizo la IA. Si
cierra sin guardar, queda (en <datos de usuario>/FreeWorks-IA/respaldos/). No es control de
versiones: para ir unos pasos atrás está Ctrl+Z.

FreeCAD 1.1.4 avisa slotFinishSaveDocument también con saveCopy (las copias de la IA): solo
cuenta como "el usuario guardó" si el archivo guardado es el del documento.
"""

import hashlib
import os
import re

import FreeCAD

from swui.fork.ia.nucleo import config

_backups = {}  # nombre interno del documento -> ruta del respaldo de esta sesión
_observer = []


def _folder():
    path = os.path.join(config.data_dir(), "respaldos")
    os.makedirs(path, exist_ok=True)
    return path


def path_for(doc):
    stem = re.sub(r"[^\w.-]+", "_", doc.Label or doc.Name).strip("_")[:40] or "documento"
    tag = hashlib.sha1((doc.FileName or doc.Name).encode("utf-8")).hexdigest()[:8]
    return os.path.join(_folder(), "%s.%s.FCStd" % (stem, tag))


def current(doc_name):
    path = _backups.get(doc_name)
    return path if path and os.path.exists(path) else ""


def ensure(doc):
    """Hacer el respaldo si este documento todavía no tiene uno desde que se guardó.
    Devuelve (ruta, recién_hecho)."""
    path = current(doc.Name)
    if path:
        return path, False
    path = path_for(doc)
    save_copy(doc, path)
    _backups[doc.Name] = path
    return path, True


def save_copy(doc, path):
    """saveCopy sin dejar un .FCBak al lado: si el archivo ya existe, FreeCAD guarda una copia de
    seguridad (preferencia "Crear archivos de respaldo"); se borra antes para que no haya qué
    resguardar. No cambia el nombre ni el archivo del documento."""
    if os.path.exists(path):
        os.remove(path)
    doc.saveCopy(path)


def discard(doc_name, quiet=False):
    path = _backups.pop(doc_name, "")
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            FreeCAD.Console.PrintLog("FreeWorks IA: no se pudo borrar el respaldo %s\n" % path)
            return
        if not quiet:
            FreeCAD.Console.PrintMessage("FreeWorks IA: guardaste el documento; se borró el respaldo de la IA.\n")


def discard_quiet(doc_name):
    """Respaldo hecho para un script que al final no cambió nada."""
    discard(doc_name, quiet=True)


def _same_file(a, b):
    return bool(a and b) and os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


class _SaveObserver:
    def slotFinishSaveDocument(self, doc, filename):
        try:
            if doc.Name in _backups and _same_file(filename, doc.FileName):
                discard(doc.Name)
        except Exception:
            pass

    def slotDeletedDocument(self, doc):
        # cerrado sin guardar: el respaldo queda en disco, pero esta sesión lo olvida
        try:
            _backups.pop(doc.Name, None)
        except Exception:
            pass


def install():
    if _observer:
        return
    obs = _SaveObserver()
    FreeCAD.addDocumentObserver(obs)
    _observer.append(obs)
