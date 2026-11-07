# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Perfiles normalizados para Piezas soldadas: tablas CIRSOC 301/302 (IRAM-IAS) y su dibujo real
(radios de esquina, radios de acuerdo, alas inclinadas). Decisión del usuario 07/11: todas las
familias de la tabla CIRSOC salvo las series americanas (W, HP, M, C, MC); la Planchuela sigue como
estaba. Los datos salen de `weld_cirsoc.py` (generado con tools/fork/cirsoc_tablas.py).

Sin FreeCAD.Gui; solo FreeCAD.Vector. La geometría sale como contornos:
    ("circle", radio)                       círculo centrado
    ("poly", [puntos])                      polígono (formato viejo, perfiles sin radios)
    ("wire", [tramos])                      contorno cerrado con tramos
        ("line", p, q)                      recta de p a q
        ("arc", centro, radio, p, q)        arco de p a q (el corto), en el sentido del contorno
Todos centrados en su rectángulo envolvente: X = ancho, Y = alto (eje fuerte X-X horizontal, como
la tabla: Ix es la inercia alrededor del eje horizontal).

Funciones públicas:
    kinds()                         familias (nombres que se guardan en SWUI_WeldKind)
    sizes(kind)                     [(nombre, dims)]
    find(kind, name)                fila de la tabla (dict) o None
    loops(kind, dims, outer_only)   contornos (ver arriba)
    extent(kind, dims)              (ancho X, alto Y)
    section(kind, name)             {"Designación": ..., "Ag (cm2)": "7,57", ...} propiedades de tabla
"""

import math

import FreeCAD

V = FreeCAD.Vector
INCH = 25.4

TUBES = ("Caño cuadrado", "Caño rectangular", "Caño redondo")
IBEAMS = ("IPN", "IPE", "IPB", "IPBI", "IPBv")
KINDS = ("Caño cuadrado", "Caño rectangular", "Caño redondo", "Ángulo", "Perfil T", "UPN",
         "IPN", "IPE", "IPB", "IPBI", "IPBv", "Planchuela")

# Unidad de cada propiedad (como la tabla CIRSOC)
UNITS = {"Ag": "cm2", "Peso": "kg/m", "p": "m2/m", "Ix": "cm4", "Iy": "cm4", "Sx": "cm3", "Sy": "cm3",
         "rx": "cm", "ry": "cm", "Zx": "cm3", "Zy": "cm3", "Qx": "cm3", "Qy": "cm3", "J": "cm4",
         "Cw": "cm6", "C": "cm3", "ex": "cm", "w": "cm", "v1": "cm", "Iv": "cm4", "Sv": "cm3",
         "iv": "cm", "Iz": "cm4", "iz": "cm", "dx": "cm", "eY": "cm", "eC": "cm"}
NAMES = {"Ag": "Área Ag", "Peso": "Peso", "p": "Superficie exterior p", "Ix": "Inercia Ix", "Iy": "Inercia Iy",
         "Sx": "Módulo resistente Sx", "Sy": "Módulo resistente Sy", "rx": "Radio de giro rx",
         "ry": "Radio de giro ry", "Zx": "Módulo plástico Zx", "Zy": "Módulo plástico Zy",
         "Qx": "Momento estático Qx", "Qy": "Momento estático Qy", "J": "Módulo de torsión J",
         "Cw": "Módulo de alabeo Cw", "C": "Constante torsional C", "ex": "Centro de gravedad ex=ey",
         "w": "Distancia w", "v1": "Distancia v1", "Iv": "Inercia mínima Iv", "Sv": "Módulo Sv",
         "iv": "Radio de giro mínimo iv", "Iz": "Inercia máxima Iz", "iz": "Radio de giro máximo iz",
         "dx": "Centro de gravedad dx", "eY": "Centro de gravedad x", "eC": "Centro de corte eC"}
NORMS = {"Caño cuadrado": "IRAM-IAS U 500-218 / U 500-2592", "Caño rectangular": "IRAM-IAS U 500-218 / U 500-2592",
         "Caño redondo": "IRAM-IAS U 500-218 / U 500-2592", "Ángulo": "IRAM-IAS U 500-558",
         "Perfil T": "IRAM-IAS U 500-561", "UPN": "IRAM-IAS U 500-509-2", "IPN": "IRAM-IAS U 500-511",
         "IPB": "IRAM-IAS U 500-215-2", "IPBI": "IRAM-IAS U 500-215-3", "IPBv": "IRAM-IAS U 500-215-4",
         "IPE": "IRAM-IAS U 500-215-5"}


def _fmt(x):
    s = ("%.2f" % x).rstrip("0").rstrip(".")
    return s.replace(".", ",")


def _inch(mm, den=16, tol=0.012):
    """'1 1/2' si mm es una fracción de pulgada (hasta 1/den), si no None."""
    n = _inch_n(mm, den, tol)
    if n is None:
        return None
    whole, frac = divmod(n, den)
    d = den
    while frac and frac % 2 == 0:
        frac //= 2
        d //= 2
    if not frac:
        return "%d" % whole
    return ("%d %d/%d" % (whole, frac, d)) if whole else "%d/%d" % (frac, d)


def _inch_n(mm, den, tol):
    x = mm / INCH
    n = int(round(x * den))
    if n <= 0 or abs(x - float(n) / den) > tol:
        return None
    return n


# --- Nombres y medidas ----------------------------------------------------------------------------


def _data():
    from swui.fork import weld_cirsoc

    return weld_cirsoc.DATA


def _rows(kind):
    """[(nombre, dims, fila)] de una familia de la tabla."""
    rows = _data().get(kind, [])
    out = []
    for r in rows:
        if kind == "Caño cuadrado":
            out.append(("%sx%sx%s" % (_fmt(r["B"]), _fmt(r["B"]), _fmt(r["t"])), [r["B"], r["B"], r["t"]], r))
        elif kind == "Caño rectangular":
            out.append(("%sx%sx%s" % (_fmt(r["B"]), _fmt(r["H"]), _fmt(r["t"])), [r["B"], r["H"], r["t"]], r))
        elif kind == "Caño redondo":
            inch = _inch(r["D"], den=8, tol=0.006)
            if inch:  # como antes: 1" (25,4 mm) x 1,6 (el mm, de la pulgada exacta)
                exact = _inch_n(r["D"], 8, 0.006) / 8.0 * INCH
                name = "%s\" (%s mm) x %s" % (inch, _fmt(exact), _fmt(r["t"]))
            else:
                name = "Ø %s mm x %s" % (_fmt(r["D"]), _fmt(r["t"]))
            out.append((name, [r["D"], r["t"]], r))
        elif kind in ("Ángulo", "Perfil T"):
            b = r["b"] if kind == "Ángulo" else r["bf"]
            ib, it = _inch(b, tol=0.025), _inch(r["t"], tol=0.025)
            name = "%s\" x %s\"" % (ib, it) if ib and it else "%s x %s" % (_fmt(b), _fmt(r["t"]))
            if kind == "Ángulo":
                dims = [r["b"], r["t"], r["r"], r["r1"]]
            else:
                dims = [r["d"], r["bf"], r["t"], r["r"], r["r1"], r["r2"]]
            out.append((name, dims, r))
        elif kind == "UPN" or kind in IBEAMS:
            out.append(("%s %s" % (kind, r["desig"]), list(r["dims"]), r))
    return out


def kinds():
    return KINDS


def sizes(kind):
    return [(n, d) for n, d, _r in _rows(kind)]


def find(kind, name):
    for n, _d, r in _rows(kind):
        if n == name:
            return r
    return None


def designation(kind, row):
    """Designación de la norma (como la tabla)."""
    if kind == "Caño cuadrado":
        return "Tubo □ %s x %s" % (_fmt(row["B"]), _fmt(row["t"]))
    if kind == "Caño rectangular":
        return "Tubo ▭ %s x %s x %s" % (_fmt(row["B"]), _fmt(row["H"]), _fmt(row["t"]))
    if kind == "Caño redondo":
        return "Tubo Ø %s x %s" % (_fmt(row["D"]), _fmt(row["t"]))
    if kind == "Ángulo":
        return "L %s x %s x %s" % (_fmt(row["b"]), _fmt(row["b"]), _fmt(row["t"]))
    if kind == "Perfil T":
        return "T %s x %s x %s" % (_fmt(row["d"]), _fmt(row["bf"]), _fmt(row["t"]))
    return "%s %s" % (kind, row["desig"])


def section(kind, name):
    """Propiedades de sección de la tabla CIRSOC, listas para guardar (textos con coma decimal):
    {"Designación", "Norma", "<propiedad> (<unidad>)": "valor"}. None si no es de la tabla."""
    row = find(kind, name)
    if row is None:
        return None
    out = {"Designación": designation(kind, row), "Norma": NORMS.get(kind, "") + " (tablas CIRSOC 301/302)"}
    props = dict(row["props"])
    if kind in ("Caño cuadrado", "Caño redondo"):  # simétricos: la tabla da un solo valor
        for a, b in (("Ix", "Iy"), ("Sx", "Sy"), ("rx", "ry"), ("Zx", "Zy")):
            if a in props:
                props[b] = props[a]
    if kind == "Ángulo":
        for a, b in (("Ix", "Iy"), ("Sx", "Sy"), ("rx", "ry")):
            props[b] = props[a]
    for key in UNITS:  # en el orden de UNITS: área, peso, inercias, módulos, radios de giro...
        val = props.get(key)
        if val is None:
            continue
        out["%s (%s)" % (NAMES[key], UNITS[key])] = _fmt_prop(val)
    return out


def _fmt_prop(x):
    s = repr(float(x))
    if s.endswith(".0"):
        s = s[:-2]
    return s.replace(".", ",")


# --- Dibujo ----------------------------------------------------------------------------------------


def contour(pts):
    """Contorno cerrado por vértices [(x, y, radio)] (radio 0 = esquina viva): redondea cada esquina
    con su radio (convexa o cóncava). Devuelve [tramos] (ver formato arriba)."""
    n = len(pts)
    corners = []  # por vértice: (entrada, salida, centro|None, radio)
    for i in range(n):
        x, y, r = pts[i]
        p = V(x, y, 0)
        if r <= 0:
            corners.append((p, p, None, 0))
            continue
        a = V(pts[i - 1][0], pts[i - 1][1], 0)
        b = V(pts[(i + 1) % n][0], pts[(i + 1) % n][1], 0)
        u = a - p
        w = b - p
        room = min(u.Length, w.Length) * 0.95  # un radio de tabla que no entra (p. ej. punta
        u.normalize()                          # de ala más fina que el radio) se achica
        w.normalize()
        half = math.acos(max(-1.0, min(1.0, u.dot(w)))) / 2
        d = r / math.tan(half)
        if d > room:
            d = room
            r = d * math.tan(half)
        bis = u + w
        bis.normalize()
        c = p + bis * (r / math.sin(half))
        corners.append((p + u * d, p + w * d, c, r))
    segs = []
    for i in range(n):
        _ein, eout, _c, _r = corners[i]
        nin, _nout, c2, r2 = corners[(i + 1) % n]
        if (nin - eout).Length > 1e-9:
            segs.append(("line", eout, nin))
        if c2 is not None:
            segs.append(("arc", c2, r2, nin, corners[(i + 1) % n][1]))
    return segs


def _rrect(w, h, r):
    return contour([(-w / 2, -h / 2, r), (w / 2, -h / 2, r), (w / 2, h / 2, r), (-w / 2, h / 2, r)])


def _box(w, h):
    return [("poly", [V(-w / 2, -h / 2, 0), V(w / 2, -h / 2, 0), V(w / 2, h / 2, 0), V(-w / 2, h / 2, 0)])]


def _ibeam(d, bf, tw, t_web, t_toe, r_root, r_toe):
    """Doble T (alas paralelas si t_web == t_toe)."""
    x, y, s = bf / 2, d / 2, tw / 2
    return contour([(-x, -y, 0), (x, -y, 0), (x, -y + t_toe, r_toe), (s, -y + t_web, r_root),
                    (s, y - t_web, r_root), (x, y - t_toe, r_toe), (x, y, 0), (-x, y, 0),
                    (-x, y - t_toe, r_toe), (-s, y - t_web, r_root), (-s, -y + t_web, r_root),
                    (-x, -y + t_toe, r_toe)])


def ibeam_params(kind, dims):
    """(d, bf, tw, t_alma, t_punta, r_acuerdo, r_punta) de un doble T de la tabla."""
    if kind == "IPN":  # d bf tf hw tw=r1 r2; alas al 14 %, tf medido a bf/4 del borde
        d, bf, tf, _hw, tw, r2 = dims
        k = 0.14
        t_toe = tf - k * bf / 4
        t_web = tf + k * (bf / 4 - tw / 2)
        return d, bf, tw, t_web, t_toe, tw, r2
    if kind == "IPB":  # d bf tf hw tw (r = (d - 2 tf - hw) / 2)
        d, bf, tf, hw, tw = dims
        r = (d - 2 * tf - hw) / 2
        return d, bf, tw, tf, tf, r, 0
    d, bf, tf, _hw, tw, r = dims  # IPBI, IPBv, IPE
    return d, bf, tw, tf, tf, r, 0


def upn_params(dims):
    """(h, bf, tw, t_alma, t_punta, r1, r2): alas al 8 % (5 % si h > 300), tf medido a bf/2."""
    h, bf, tf, _hw, tw, r2 = dims
    k = 0.05 if h > 300 else 0.08
    t_toe = tf - k * (bf / 2)
    t_web = tf + k * (bf / 2 - tw)
    return h, bf, tw, t_web, t_toe, tf, r2


def loops(kind, dims, outer_only=False):
    """Contornos de la sección (ver arriba). dims como en sizes(); acepta también las medidas viejas
    (sin radios) de archivos hechos antes de las tablas CIRSOC."""
    if kind in ("Caño cuadrado", "Caño rectangular"):
        b, h, t = dims[:3]
        out = [("wire", _rrect(b, h, 2 * t))]
        if not outer_only:
            out.append(("wire", _rrect(b - 2 * t, h - 2 * t, t)))
        return out
    if kind == "Caño redondo":
        d, t = dims[:2]
        out = [("circle", d / 2)]
        if not outer_only:
            out.append(("circle", d / 2 - t))
        return out
    if kind == "Ángulo":
        a, t = dims[0], dims[1]
        r, r1 = (dims[2], dims[3]) if len(dims) >= 4 else (0, 0)
        h = a / 2
        if outer_only:
            return _box(a, a)
        return [("wire", contour([(-h, -h, 0), (h, -h, 0), (h, -h + t, r1), (-h + t, -h + t, r),
                                  (-h + t, h, r1), (-h, h, 0)]))]
    if kind == "Perfil T":
        d, bf, t, r, r1, r2 = dims
        if outer_only:
            return _box(bf, d)
        x, y = bf / 2, d / 2
        k = 0.02  # caras del alma y del ala al 2 %; el espesor t, a mitad de cada tramo
        lw, lf = d - t, (bf - t) / 2
        s_tip, s_root = t / 2 - k * lw / 2, t / 2 + k * lw / 2
        f_toe, f_root = t - k * lf / 2, t + k * lf / 2
        return [("wire", contour([(-s_tip, -y, r2), (s_tip, -y, r2), (s_root, y - f_root, r), (x, y - f_toe, r1),
                                  (x, y, 0), (-x, y, 0), (-x, y - f_toe, r1), (-s_root, y - f_root, r)]))]
    if kind == "Planchuela":
        b, t = dims
        return _box(b, t)
    if kind == "UPN":
        if len(dims) == 4:  # archivos viejos: h, b, alma, ala (DIN 1026, sin radios)
            h, b, tw, tf = dims
            x0, x1, y0, y1 = -b / 2, b / 2, -h / 2, h / 2
            if outer_only:
                return _box(b, h)
            return [("poly", [V(x0, y0, 0), V(x1, y0, 0), V(x1, y0 + tf, 0), V(x0 + tw, y0 + tf, 0),
                              V(x0 + tw, y1 - tf, 0), V(x1, y1 - tf, 0), V(x1, y1, 0), V(x0, y1, 0)])]
        h, bf, tw, t_web, t_toe, r1, r2 = upn_params(dims)
        if outer_only:
            return _box(bf, h)
        x0, x1, y0, y1 = -bf / 2, bf / 2, -h / 2, h / 2
        return [("wire", contour([(x0, y0, 0), (x1, y0, 0), (x1, y0 + t_toe, r2), (x0 + tw, y0 + t_web, r1),
                                  (x0 + tw, y1 - t_web, r1), (x1, y1 - t_toe, r2), (x1, y1, 0), (x0, y1, 0)]))]
    if kind in IBEAMS:
        p = ibeam_params(kind, dims)
        if outer_only:
            return _box(p[1], p[0])
        return [("wire", _ibeam(*p))]
    raise ValueError(kind)


def extent(kind, dims):
    """(ancho en X, alto en Y) del perfil."""
    if kind in ("Caño cuadrado", "Caño rectangular"):
        return dims[0], dims[1]
    if kind in ("Caño redondo", "Ángulo"):
        return dims[0], dims[0]
    if kind == "Planchuela":
        return dims[0], dims[1]
    if kind == "Perfil T":
        return dims[1], dims[0]
    if kind == "UPN":
        return (dims[1], dims[0])
    if kind in IBEAMS:
        return dims[1], dims[0]
    return 0, 0


def face(kind, dims):
    """Cara (Part.Face) de la sección, para medir área e inercias."""
    import Part

    faces = []
    for typ, data in loops(kind, dims):
        if typ == "circle":
            faces.append(Part.Face(Part.Wire(Part.makeCircle(data))))
        elif typ == "poly":
            faces.append(Part.Face(Part.makePolygon(data + [data[0]])))
        else:
            faces.append(Part.Face(Part.Wire([edge(s) for s in data])))
    f = faces[0]
    for g in faces[1:]:
        f = f.cut(g)
    return f


def edge(seg):
    """Part.Edge de un tramo."""
    import Part

    if seg[0] == "line":
        return Part.LineSegment(seg[1], seg[2]).toShape()
    _t, c, r, p, q = seg
    mid = _arc_mid(c, r, p, q)
    return Part.Arc(p, mid, q).toShape()


def _arc_mid(c, r, p, q):
    m = (p + q) * 0.5 - c
    if m.Length < 1e-12:
        m = V(-(p - c).y, (p - c).x, 0)
    m.normalize()
    return c + m * r
