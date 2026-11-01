# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 Dominik Ladewig
"""Einzige Stelle, an der die Versionsnummer steht."""

# Bei JEDER Freigabe hochzaehlen - zusammen mit <version> und <date> in
# package.xml (der Test prueft, dass beide gleich sind). Daran erkennt der
# Addon-Manager "Update verfuegbar".
#   0.9.0  erste Veroeffentlichung (18.10.2026)
#   0.10.0 erste Freigabe ueber den Zweig "release" (18.10.2026)
#   0.11.0 FreeWorks: primera versión del fork (01/11/2026)
#   1.0.0  Aufnahme in den offiziellen Index
# Aenderungen je Version: CHANGELOG.md. Freigeben: tools/freigabe.sh
__version__ = "0.11.0"

# Kleinste FreeCAD-Version, gegen die wir entwickeln.
MIN_FREECAD = (1, 1)  # fork: desarrollado y probado en 1.1.4 (menús, barra de menú de 1.1)
