# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#2, decisión del usuario (11/11): las esquinas de un marco soldado siguen al esqueleto con
fórmulas NATIVAS de FreeCAD, también sin FreeWorks. Marco 600 x 400 de caño 40x40, a inglete y a
tope; se guarda y un FreeCAD SOLO (FreeCADCmd, que no carga FreeWorks: se comprueba) lo abre, pasa
el ancho a 800 y recalcula: el marco ocupa -20..820 x -20..420, cada caño válido, sin huecos en
las esquinas ni caños superpuestos."""

import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402

import FreeCAD  # noqa: E402

from _base import carpeta_temporal  # noqa: E402
from comun import marco  # noqa: E402

HIJO = r'''
import json, sys
import FreeCAD
doc = FreeCAD.openDocument(sys.argv[-3])
sk = doc.getObject(sys.argv[-2])
sk.setDatum(int(sys.argv[-1]), FreeCAD.Units.Quantity("800 mm"))
doc.recompute()
cuerpos = [o for o in doc.Objects if getattr(o, "SWUI_WeldMember", False)]
out = {"swui": any(m.startswith("swui") for m in sys.modules), "caños": []}
for b in cuerpos:
    bb = b.Shape.BoundBox
    out["caños"].append({"n": b.Label, "ok": b.Shape.isValid() and "Invalid" not in str(b.State),
                         "bb": [bb.XMin, bb.XMax, bb.YMin, bb.YMax]})
huecos, sup = [], []
for i in range(len(cuerpos)):
    for j in range(i + 1, len(cuerpos)):
        d = cuerpos[i].Shape.distToShape(cuerpos[j].Shape)[0]
        c = cuerpos[i].Shape.common(cuerpos[j].Shape).Volume
        if c > 0.01:
            sup.append([cuerpos[i].Label, cuerpos[j].Label, c])
        huecos.append(d)
out["sup"] = sup
out["huecos"] = sorted(huecos)[:4]
print("RESULTADO " + json.dumps(out))
'''


def prueba():
    hijo = os.path.join(carpeta_temporal(), "hijo.py")
    with open(hijo, "w", encoding="utf-8") as fh:
        fh.write(HIJO)
    cmd_bin = os.path.join(FreeCAD.getHomePath(), "bin", "FreeCADCmd.exe")
    for esquina in ("inglete", "tope"):
        doc = FreeCAD.newDocument("Marco_" + esquina)
        sk, cota, _cuerpos = marco(doc, esquina=esquina)
        ruta = os.path.join(carpeta_temporal(), "marco_%s.FCStd" % esquina)
        doc.saveAs(ruta)
        nombre = sk.Name
        FreeCAD.closeDocument(doc.Name)
        r = subprocess.run([cmd_bin, hijo, ruta, nombre, str(cota)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
        linea = [x for x in (r.stdout or "").splitlines() if x.startswith("RESULTADO ")]
        assert linea, "%s: FreeCAD solo no dio resultado:\n%s\n%s" % (esquina, r.stdout[-800:], r.stderr[-800:])
        res = json.loads(linea[-1][len("RESULTADO "):])
        assert not res["swui"], "el FreeCAD de control cargó FreeWorks: la prueba no vale"
        assert len(res["caños"]) == 4, res
        for c in res["caños"]:
            x0, x1, y0, y1 = c["bb"]
            assert c["ok"], "%s: %s con error sin FreeWorks" % (esquina, c["n"])
            assert x0 > -20.1 and x1 < 820.1 and y0 > -20.1 and y1 < 420.1, \
                "%s: %s sobresale sin FreeWorks (#2): %s" % (esquina, c["n"], c["bb"])
        assert max(c["bb"][1] for c in res["caños"]) > 819.9, "%s: el marco no llega a 820 (hueco)" % esquina
        assert not res["sup"], "%s: caños superpuestos sin FreeWorks: %s" % (esquina, res["sup"])
        assert all(h < 1e-3 for h in res["huecos"][:4]), "%s: hueco en una esquina: %s" % (esquina, res["huecos"])


from _base import ejecutar  # noqa: E402
ejecutar(globals())
