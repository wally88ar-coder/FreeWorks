# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""Genera swui/fork/weld_cirsoc.py desde las "Tablas de perfiles laminados y tubos estructurales"
CIRSOC 301/302 (Troglia, Troglia y Godoy, PDF que pasó el usuario el 07/11; no está en el repositorio).

    pdftotext -table tablas.pdf tt.txt
    python tools/fork/cirsoc_tablas.py tt.txt swui/fork/weld_cirsoc.py

Solo las familias que usa el usuario (sin las series americanas W, HP, M, C, MC). A los tubos la
medida (D, B, BxH) les aparece en una sola fila de cada grupo: se asigna a las demás con el área
(Ag = f(medida, t), con radio exterior 2t e interior t) y la ancla más cercana.
"""

import io, json, math, re, sys

L = io.open(sys.argv[1], encoding="latin-1").read().split("\n")
NUM = re.compile(r"^-?\d+(?:[.,]\d+)?$")


def num(s):
    return float(s.replace(",", "."))


def toks(line):
    return line.split()


def find(pat, start=0):
    for i in range(start, len(L)):
        if re.search(pat, L[i]):
            return i
    raise KeyError(pat)


def numeric_rows(a, b):
    """(índice, [tokens]) de las filas entre a y b que son todas numéricas (o '-')."""
    out = []
    for i in range(a, b):
        t = toks(L[i])
        if t and all(NUM.match(x) or x == "-" for x in t):
            out.append((i, t))
    return out


def f(x):
    return None if x == "-" else num(x)


out = {}

# ---------- perfiles doble T --------------------------------------------------------------------
# columnas comunes tras las dimensiones: Ag Peso Ix Sx rx Qx Zx Iy Sy ry Qy 1.5Sy Zy ... J Cw X1 X2 Lp Lr Lp Lr
PROPS_I = ["Ag", "Peso", "Ix", "Sx", "rx", "Qx", "Zx", "Iy", "Sy", "ry", "Qy", "1,5Sy", "Zy"]


def ibeams(name, start_pat, end_pat, ndim):
    a = find(start_pat)
    b = find(end_pat, a + 1)
    rows = []
    for i, t in numeric_rows(a, b):
        if len(t) < 30:
            continue
        desig = t[0]
        dims = [f(x) for x in t[1:1 + ndim]]
        rest = t[1 + ndim:]
        rest = rest[2:]  # relaciones bf/2tf, hw/tw
        props = dict(zip(PROPS_I, [f(x) for x in rest[:13]]))
        tail = [f(x) for x in t[-8:]]
        props["J"], props["Cw"] = tail[0], tail[1]
        rows.append({"desig": desig, "dims": dims, "props": props})
    return rows


# IPN: d bf tf hw tw=r1 r2
out["IPN"] = ibeams("IPN", r"IPN seg", r"IPB seg", 6)
# raro: líneas como "320/305" no son numéricas: se tratan aparte
out["IPB"] = ibeams("IPB", r"IPB seg", r"IPBI seg", 5)       # d bf tf hw tw (r de hw)
out["IPBI"] = ibeams("IPBI", r"IPBI seg", r"IPBv seg", 6)    # d bf tf hw tw r
out["IPE"] = ibeams("IPE", r"IPE seg", r"Serie W", 6)        # d bf tf hw tw r


def ipbv():
    a = find(r"IPBv seg")
    b = find(r"IPE seg", a + 1)
    rows = []
    for i in range(a, b):
        t = toks(L[i])
        if len(t) >= 30 and re.match(r"^\d+(/\d+)?$", t[0]) and all(NUM.match(x) or x == "-" for x in t[1:]):
            dims = [f(x) for x in t[1:7]]
            rest = t[9:]
            props = dict(zip(PROPS_I, [f(x) for x in rest[:13]]))
            tail = [f(x) for x in t[-8:]]
            props["J"], props["Cw"] = tail[0], tail[1]
            rows.append({"desig": t[0], "dims": dims, "props": props})
    return rows


out["IPBv"] = ipbv()

# ---------- UPN: h bf tf=r1 hw tw r2 | bf/tf hw/tw | Ag Peso Ix Sx rx Qx Zx Iy Sy ry Qy 1,5Sy Zy eY eC
#                 | w1 d w4 t1 t2 | J Cw X1 X2 Lp Lr Lp Lr  (los chicos no tienen las últimas 7)


def upn():
    a = find(r"UPN seg")
    b = find(r"Serie C seg", a + 1)
    rows = []
    names = ["Ag", "Peso", "Ix", "Sx", "rx", "Qx", "Zx", "Iy", "Sy", "ry", "Qy", "1,5Sy", "Zy", "eY", "eC"]
    for i in range(a, b):
        t = toks(L[i])
        if len(t) < 25 or not re.match(r"^\d+(x\d+)?$", t[0]):
            continue
        if not all(NUM.match(x) or x == "-" for x in t[1:]):
            continue
        dims = [f(x) for x in t[1:7]]
        rest = t[9:]
        props = dict(zip(names, [f(x) for x in rest[:15]]))
        after = rest[15:]
        # w1 d w4 t1 t2 J Cw X1 X2 Lp Lr Lp Lr
        props["J"] = f(after[5]) if len(after) > 5 else None
        props["Cw"] = f(after[6]) if len(after) > 6 else None
        rows.append({"desig": t[0], "dims": dims, "props": props})
    return rows


out["UPN"] = upn()

# ---------- Ángulos: ... b t [r r1] b/t Ag Peso ex w v1 Ix Sx rx Iv Sv iv Iz iz J Cw


def angles():
    a = find(r"Perfiles Angulo")
    b = find(r"Perfiles T", a + 1)
    rows = []
    names = ["b/t", "Ag", "Peso", "ex", "w", "v1", "Ix", "Sx", "rx", "Iv", "Sv", "iv", "Iz", "iz", "J", "Cw"]
    pending_r = None
    for i in range(a, b):
        line = L[i]
        t = toks(line)
        if len(t) == 2 and all(NUM.match(x) for x in t):
            pending_r = (num(t[0]), num(t[1]))  # "10 5" suelto entre filas
            rows.append({"radii_line": pending_r, "line": i})
            continue
        m = re.match(r"^\s*(L\s*[\d,]+\s*x\s*[\d,]+\s*x\s*[\d,]+|x\s*[\d,]+)", line)
        if not m:
            continue
        # números al final de la línea
        nums = []
        for x in reversed(t):
            if NUM.match(x):
                nums.append(num(x))
            else:
                break
        nums.reverse()
        if len(nums) == 20:
            b_, t_, r, r1 = nums[:4]
            vals = nums[4:]
        elif len(nums) == 18:
            b_, t_ = nums[:2]
            r = r1 = None
            vals = nums[2:]
        else:
            raise ValueError("ángulo raro: %r" % line)
        rows.append({"b": b_, "t": t_, "r": r, "r1": r1, "props": dict(zip(names, vals)), "line": i})
    # radios: uno por cada tamaño b (aparece en una fila del grupo o suelto)
    groups = {}
    for r in rows:
        if "b" in r:
            groups.setdefault(r["b"], []).append(r)
    loose = [r for r in rows if "radii_line" in r]
    final = []
    for b_, g in groups.items():
        rr = [(x["r"], x["r1"]) for x in g if x["r"] is not None]
        if not rr:
            lines = [x["line"] for x in g]
            near = [lr for lr in loose if min(lines) <= lr["line"] <= max(lines)]
            if len(near) != 1:
                raise ValueError("sin radio para L%s" % b_)
            rr = [near[0]["radii_line"]]
        assert len(set(rr)) == 1, (b_, rr)
        for x in g:
            final.append({"b": x["b"], "t": x["t"], "r": rr[0][0], "r1": rr[0][1], "props": x["props"]})
    return final


out["Ángulo"] = angles()

# ---------- T: d bf tf=tw r r1 r2 bf/2tf d/tw Ag Peso dx Ix Sx rx Qx Zx Iy Sy ry Qy 1,5Sy Zy J Cw


def tees():
    a = find(r"Perfiles T")
    b = find(r"Tubos de acero", a + 1)
    names = ["Ag", "Peso", "dx", "Ix", "Sx", "rx", "Qx", "Zx", "Iy", "Sy", "ry", "Qy", "1,5Sy", "Zy", "J", "Cw"]
    rows = []
    for i in range(a, b):
        line = L[i]
        if not re.match(r"^\s*T\s*\d", line):
            continue
        t = toks(line)
        nums = []
        for x in reversed(t):
            if NUM.match(x):
                nums.append(num(x))
            else:
                break
        nums.reverse()
        assert len(nums) == 24, line
        d, bf, tf, r, r1, r2 = nums[:6]
        rows.append({"d": d, "bf": bf, "t": tf, "r": r, "r1": r1, "r2": r2,
                     "props": dict(zip(names, nums[8:]))})
    return rows


out["Perfil T"] = tees()

# ---------- Tubos -------------------------------------------------------------------------------


def tube_rows(a, b, n_after):
    """Filas de tubo: anclas (con medida) y sueltas; devuelve [(linea, medidas|None, valores)]."""
    rows = []
    for i, t in numeric_rows(a, b):
        if len(t) == n_after:
            rows.append((i, None, [num(x) for x in t]))
        elif n_after < len(t) <= n_after + 2:
            k = len(t) - n_after
            rows.append((i, [num(x) for x in t[:k]], [num(x) for x in t[k:]]))
    return rows


def assign(rows, estimate, key_of, tol):
    anchors = [(i, m) for i, m, _v in rows if m is not None]
    out_ = []
    for i, m, v in rows:
        if m is None:
            est = estimate(v)
            cands = [(abs(j - i), mm) for j, mm in anchors if abs(key_of(mm) - est) < tol(mm)]
            if not cands:
                raise ValueError("sin medida para la fila %d %r (estimado %.2f)" % (i, v, est))
            m = min(cands, key=lambda c: c[0])[1]
        else:
            est = estimate(v)
            if abs(key_of(m) - est) >= tol(m):
                print("AVISO ancla %d %r estimado %.2f" % (i, m, est))
        out_.append((m, v))
    return out_


K = 3 * (4 - math.pi)


def round_tubes():
    a = find(r"Secci.n Circular", 100)
    b = find(r"Cuadrada", a + 1)
    names = ["t", "p", "Ag", "Peso", "Ix", "Sx", "rx", "Zx", "J", "C"]
    rows = tube_rows(a, b, 10)
    est = lambda v: v[2] * 100 / (math.pi * v[0]) + v[0]
    got = assign(rows, est, lambda m: m[0], lambda m: max(1.5, 0.02 * m[0]))
    return [{"D": m[0], "t": v[0], "props": dict(zip(names[1:], v[1:]))} for m, v in got]


def square_tubes():
    a = find(r"Cuadrada", find(r"Secci.n Circular", 100))
    b = find(r"Rectangular", a + 1)
    names = ["t", "p", "Ag", "Peso", "Ix", "Sx", "rx", "Zx", "J", "C"]
    rows = tube_rows(a, b, 10)
    est = lambda v: (v[2] * 100 + 4 * v[0] ** 2 + K * v[0] ** 2) / (4 * v[0])
    got = assign(rows, est, lambda m: m[0], lambda m: max(1.5, 0.03 * m[0]))
    return [{"B": m[0], "t": v[0], "props": dict(zip(names[1:], v[1:]))} for m, v in got]


def rect_tubes():
    a = find(r"Rectangular", find(r"Cuadrada", find(r"Secci.n Circular", 100)) + 1)
    b = len(L)
    names = ["t", "p", "Ag", "Peso", "Ix", "Sx", "rx", "Zx", "Iy", "Sy", "ry", "Zy", "J", "C"]
    rows = tube_rows(a, b, 14)
    est = lambda v: (v[2] * 100 + 4 * v[0] ** 2 + K * v[0] ** 2) / (2 * v[0])
    got = assign(rows, est, lambda m: m[0] + m[1], lambda m: max(2.0, 0.03 * (m[0] + m[1])))
    return [{"B": m[0], "H": m[1], "t": v[0], "props": dict(zip(names[1:], v[1:]))} for m, v in got]


out["Caño redondo"] = round_tubes()
out["Caño cuadrado"] = square_tubes()
out["Caño rectangular"] = rect_tubes()

for k, v in out.items():
    print(k, len(v))
HEAD = """# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
# GENERADO por tools/fork/cirsoc_tablas.py desde las tablas CIRSOC 301/302 (IRAM-IAS): no editar a mano.
# Medidas en mm; propiedades con las unidades de la tabla (ver weld_profiles.UNITS).
\"\"\"Tablas de perfiles CIRSOC 301/302 (datos).\"\"\"

DATA = """
with io.open(sys.argv[2], "w", encoding="utf-8", newline="\n") as fh:
    fh.write(HEAD)
    import pprint
    fh.write(pprint.pformat(json.loads(json.dumps(out)), width=110, sort_dicts=False))
    fh.write("\n")
