#!/usr/bin/env python3
"""Dibuja la Figura 1 del manuscrito y el graphical abstract.

Son dos piezas con la misma estructura (catálogo, método, resultado), dibujadas
cada una a su tamaño de impresión para que el texto sea legible:

- Figura 1: 13,6 × 14,2 cm, el ancho de la caja de texto del preprint (y la
  columna y media de Elsevier), con las tres partes apiladas en filas para que
  quepa en una página vertical: variantes reales de OEB040$, la consulta
  q_003907 con sus parameter tokens y el top-3 de BM25, Acc@1 a nivel de ítem y
  de padre, y dos errores reales de un solo valor. Letra de 7 pt como mínimo,
  el tamaño que piden las instrucciones de figuras de Elsevier.
- Graphical abstract: 13 × 5,2 cm (5:2), que es el ancho al que Elsevier exige
  que se lea, con letra de 7 pt como mínimo y sólo el mensaje principal.

La versión anterior era una imagen hecha con un generador de imágenes, con
códigos y scores inventados; la política de Elsevier no lo admite para un
graphical abstract. Aquí todo sale de los artefactos del estudio:
- catálogo y ejes: `data/processed/OEB_texto.json`, `OEB_concept_schema.json`;
- consulta, candidatos y errores: `runs/*/results_top100.jsonl.gz`;
- Acc@1: `eval/families/acc1_by_family.json` (la fuente de `plot_acc1_by_family.py`);
- errores numéricos: `eval/error_analysis/error_distribution.md`;
- configuraciones por familia: Tabla `tab:method_families`, comprobada contra
  `metrics/all_runs.json` del depósito (142 más dos controles).

Uso:  python scripts/plot_graphical_abstract.py
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.text  # noqa: E402
from matplotlib.patches import Ellipse, FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

FAMILIAS = Path("eval/families/acc1_by_family.json")
ERRORES = Path("eval/error_analysis/error_distribution.md")
CATALOGO = Path("data/processed/OEB_texto.json")
ESQUEMA = Path("data/processed/OEB_concept_schema.json")
RUNS = Path("runs")
OUT_FIG1 = Path("paper/figures/overview")
OUT_GA = Path("paper/figures/graphical_abstract")

PLANTILLA = "OEB040$"
CONSULTA = "q_003907"
BM25 = "bm25_unigram_params__k1-0.60__b-0.35"
HIBRIDO = "hyb_bm25_uni__bge_colbert__tfidf_char_3_5"
COLBERT = "bge_m3_colbert"
# Variantes de la tabla: trabajo nocturno, banda i < 3 horas, volumen escaso; varían tubos y terreno.
FILAS = ["OEB040aabcb", "OEB040abbcb", "OEB040babcb", "OEB040bbbcb", "OEB040cabcb", "OEB040cbbcb"]
# Dos errores reales de un solo eje: (run, consulta, eje, sistema, etiqueta del eje)
EJEMPLOS = [
    (COLBERT, "q_003907", "BANDA DE MANTENIMIENTO", "BGE-M3 ColBERT", "Maintenance window"),
    ("bm25_unigram__k1-0.80__b-0.35", "q_004304", "Nº TUBOS", "BM25 unigram", "Number of tubes"),
]
# Tabla tab:method_families; suma 142, igual que all_runs.json del depósito sin sus dos controles.
CONFIGS = [("Lexical", 67), ("PRF", 32), ("Neural", 7), ("Fusion", 4),
           ("Reranking", 18), ("HyDE", 6), ("Structured", 8)]
EJES = {"Nº TUBOS": "Nº tubos", "TIPO DE TERRENO": "Terreno", "TRABAJO": "Trabajo",
        "BANDA DE MANTENIMIENTO": "Banda", "CONDICIONES DE EJECUCIÓN": "Condiciones"}

NARANJA, AZUL, VERDE, ROJO = "#e8710a", "#1f4e9e", "#2e8540", "#d62728"
MORADO, TEAL, GRIS, BORDE = "#6a3d9a", "#1b7f8c", "#555555", "#f5a623"
FONDO_NARANJA, FONDO_VERDE, FONDO_ROJO = "#fff1e0", "#e6f4e8", "#fde8e8"
COLORES_BARRAS = [NARANJA, AZUL, VERDE]
CM = 1 / 2.54


# ---------------------------------------------------------------- datos

def leer_run(run: str, query_id: str) -> dict:
    with gzip.open(RUNS / run / "results_top100.jsonl.gz", "rt", encoding="utf-8") as f:
        for linea in f:
            r = json.loads(linea)
            if r["query_id"] == query_id:
                return r
    raise KeyError(f"{query_id} no está en {run}")


def parametros(item: dict) -> dict[str, str]:
    return {v["label"].strip(): v["values"][0]["value"].strip() for v in item["parameters"].values()}


def proporcion_numericos() -> dict[str, float]:
    """Porcentaje de errores «Numeric Mismatch» por sistema, del informe de error_analysis."""
    out, sistema = {}, None
    for linea in ERRORES.read_text(encoding="utf-8").splitlines():
        if linea.startswith("## "):
            sistema = linea[3:].strip()
        m = re.match(r"- Numeric Mismatch: ([\d.]+)%", linea)
        if m and sistema:
            out[sistema] = float(m.group(1))
    return out


def cargar() -> dict:
    catalogo = {r["item_key"]: r for r in json.loads(CATALOGO.read_text(encoding="utf-8"))}
    esquema = json.loads(ESQUEMA.read_text(encoding="utf-8"))
    assert all(catalogo[k]["parent_key"] == PLANTILLA for k in FILAS)

    r_bm25 = leer_run(BM25, CONSULTA)
    top3 = [(c["index_item_key"], c["score"]) for c in r_bm25["candidates"][:3]]
    assert top3[0][0] == r_bm25["query_item_key"], "BM25 ya no acierta la consulta del ejemplo"

    errores = []
    for run, qid, eje, sistema, etiqueta in EJEMPLOS:
        r = leer_run(run, qid)
        oro, rec = r["query_item_key"], r["candidates"][0]["index_item_key"]
        po, pr = parametros(catalogo[oro]), parametros(catalogo[rec])
        assert [k for k in po if po[k] != pr[k]] == [eje], f"{qid}: el error ya no es de un solo eje"
        fmt = (lambda v: f"{v} tubes") if eje == "Nº TUBOS" else (lambda v: v)
        errores.append((sistema, etiqueta, fmt(pr[eje]), fmt(po[eje])))

    familias = {f["run"]: f for f in json.loads(FAMILIAS.read_text(encoding="utf-8"))["families"]}
    barras = [(familias[run]["item"]["Acc@1"], familias[run]["parent"]["Acc@1"]) for run in (BM25, HIBRIDO, COLBERT)]
    for run, (item, padre) in zip((BM25, HIBRIDO, COLBERT), barras):
        print(f"  {run:44s} variante={item:.4f}  familia={padre:.4f}")

    return {
        "catalogo": catalogo, "esquema": esquema, "top3": top3, "errores": errores, "barras": barras,
        "consulta": leer_run(COLBERT, CONSULTA)["query_text"],  # sin normalizar: el texto del catálogo
        "tokens": [tk.removeprefix("param_") for tk in r_bm25["query_text"].split() if tk.startswith("param_")],
        "numericos": proporcion_numericos(),
        "n_items": sum(1 for k in catalogo if k.startswith("OEB") and not k.endswith(("$", "#"))),
    }


# ---------------------------------------------------------------- primitivas (unidades: cm)

def lienzo(ancho: float, alto: float):
    fig = plt.figure(figsize=(ancho * CM, alto * CM))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, ancho)
    ax.set_ylim(0, alto)
    ax.set_axis_off()
    return fig, ax


def rbox(ax, x, y, w, h, ec, fc="white", lw=0.8, r=0.12):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                linewidth=lw, edgecolor=ec, facecolor=fc, zorder=2))


def t(ax, x, y, s, size=7, **kw):
    kw.setdefault("va", "center")
    kw.setdefault("ha", "left")
    ax.text(x, y, s, fontsize=size, zorder=5, **kw)


def flecha(ax, x0, y0, x1, y1, color="black", lw=0.8):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=7,
                                 linewidth=lw, color=color, zorder=4, shrinkA=0, shrinkB=0))


def chip(ax, x, y, s, color, w, size=6.5, h=0.42):
    rbox(ax, x, y - h / 2, w, h, color, lw=0.7, r=0.08)
    t(ax, x + w / 2, y, s, size, ha="center", color=color)
    return x + w


def envolver(texto: str, ancho: int) -> str:
    lineas, actual = [], ""
    for w in texto.split():
        if actual and len(actual) + 1 + len(w) > ancho:
            lineas.append(actual)
            actual = w
        else:
            actual = f"{actual} {w}".strip()
    return "\n".join(lineas + [actual])


def token_corto(tk: str) -> str:
    # Se acorta el prefijo del eje; el valor, que es lo que distingue a las variantes, queda entero.
    for largo, corto in (("condiciones_de_ejecución_", "condic_"), ("banda_de_mantenimiento_", "banda_"),
                         ("tipo_de_terreno_", "terreno_")):
        tk = tk.replace(largo, corto)
    return tk


def icono_bd(ax, x, y, w=0.55, h=0.6):
    e = 0.18
    ax.add_patch(Rectangle((x, y), w, h, facecolor="#dfe6ee", edgecolor=GRIS, lw=0.6, zorder=3))
    for yy in (y, y + h / 2):
        ax.add_patch(Ellipse((x + w / 2, yy), w, e, facecolor="#dfe6ee", edgecolor=GRIS, lw=0.6, zorder=3))
    ax.add_patch(Ellipse((x + w / 2, y + h), w, e, facecolor="#eef2f6", edgecolor=GRIS, lw=0.6, zorder=3))


def icono_doc(ax, x, y, w=1.7, h=0.95):
    rbox(ax, x, y, w, h, GRIS, lw=0.6, r=0.05)
    t(ax, x + 0.1, y + h - 0.27, "BC3", 9, color=NARANJA, fontweight="bold")
    t(ax, x + 0.85, y + h - 0.27, "FIEBDC", 5.5, color=GRIS)
    for i in range(3):
        ax.add_patch(Rectangle((x + 0.1, y + 0.1 + i * 0.13), w - 0.2, 0.06, facecolor="#d9d9d9", lw=0, zorder=3))


def barras_acc(fig, rect, barras, etiquetas, size, ancho_barra, con_pct):
    """Acc@1 a nivel de ítem (barras) y de padre (línea discontinua sobre cada barra)."""
    axb = fig.add_axes(rect)
    for i, (item, padre) in enumerate(barras):
        axb.bar(i, 100 * item, ancho_barra, color=COLORES_BARRAS[i], zorder=2)
        axb.text(i, 100 * item - 4, f"{100 * item:.1f}" + ("%" if con_pct else ""), ha="center", va="top",
                 fontsize=size, fontweight="bold", color="white", zorder=4)
        axb.plot([i - ancho_barra / 2 - 0.05, i + ancho_barra / 2 + 0.05], [100 * padre] * 2, color="black",
                 lw=1.0, ls=(0, (3, 1.5)), zorder=3)
    axb.text(len(barras) - 1 + ancho_barra / 2 + 0.08, 100 * barras[-1][1], f"{100 * barras[-1][1]:.1f}",
             fontsize=size - 0.5, va="center", ha="left")
    axb.set_xticks(range(len(barras)))
    axb.set_xticklabels(etiquetas, fontsize=size, fontweight="bold", linespacing=1.0)
    for lbl, c in zip(axb.get_xticklabels(), COLORES_BARRAS):
        lbl.set_color(c)
    axb.set_ylim(0, 108)
    axb.set_xlim(-0.5, len(barras) - 0.5 + 0.6)
    axb.tick_params(axis="both", labelsize=size, length=2, width=0.6, pad=1.5)
    axb.grid(axis="y", ls="--", lw=0.4, color="#cccccc", zorder=0)
    axb.spines[["top", "right"]].set_visible(False)
    for s in ("left", "bottom"):
        axb.spines[s].set_linewidth(0.6)
    return axb


def guardar(fig, out: Path, tiff: bool) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    formatos = [(".pdf", {})]
    if tiff:
        formatos.append((".tiff", {"dpi": 300, "pil_kwargs": {"compression": "tiff_lzw"}}))
    for ext, extra in formatos:
        fig.savefig(out.with_suffix(ext), **extra)
        print(f"-> {out.with_suffix(ext)}")
    plt.close(fig)


# ---------------------------------------------------------------- Figura 1

def revisar(fig) -> list[str]:
    """Textos que se solapan entre sí o se salen del lienzo (bounding boxes en píxeles)."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    marco = fig.bbox
    cajas = []
    for txt in fig.findobj(matplotlib.text.Text):
        if not txt.get_visible() or not txt.get_text().strip():
            continue
        b = txt.get_window_extent(r)
        cajas.append((txt.get_text().replace("\n", " ")[:40], b))
    problemas = [f"fuera del lienzo: {s!r}" for s, b in cajas
                 if b.x0 < marco.x0 - 1 or b.x1 > marco.x1 + 1 or b.y0 < marco.y0 - 1 or b.y1 > marco.y1 + 1]
    for i, (s1, b1) in enumerate(cajas):
        for s2, b2 in cajas[i + 1:]:
            if b1.overlaps(b2) and min(b1.x1, b2.x1) - max(b1.x0, b2.x0) > 1 and min(b1.y1, b2.y1) - max(b1.y0, b2.y0) > 1:
                problemas.append(f"solapan: {s1!r} / {s2!r}")
    return problemas


def figura1(d: dict, out: Path) -> None:
    # Ancho de la caja de texto del preprint (390 pt = 13,76 cm), que es también la
    # columna y media de Elsevier (140 mm): la letra queda a su tamaño impreso, 7 pt
    # como mínimo, y con el pie a doble espacio cabe en una página vertical.
    W, H = 13.6, 14.2
    fig, ax = lienzo(W, H)
    filas = [(9.55, 4.6), (4.8, 4.6), (0.05, 4.6)]  # (y, alto) de catálogo, método y resultado
    titulos = ["Parametric catalogs: thousands of near-identical work items",
               f"{sum(n for _, n in CONFIGS)} retrieval configurations, from lexical to structured, "
               "each scored at two levels",
               "Dense models find the family, not the exact variant"]
    for (y, h), s in zip(filas, titulos):
        rbox(ax, 0.05, y, W - 0.1, h, BORDE, lw=1.0, r=0.18)
        t(ax, 0.3, y + h - 0.33, s, 8.5, fontweight="bold")

    # --- fila 1: el catálogo
    y0 = filas[0][0]
    cat, esq = d["catalogo"], d["esquema"][PLANTILLA]
    icono_doc(ax, 0.3, y0 + 2.65)
    icono_bd(ax, 2.2, y0 + 2.8)
    t(ax, 0.3, y0 + 2.2, f"{d['n_items']:,} items\n{len(d['esquema'])} parametric templates\n"
      "ADIF railway catalog,\nsubcategory OEB", 7, va="top", linespacing=1.3)

    xt, yt, alto = 3.25, y0 + 3.55, 0.45
    t(ax, xt, yt + 0.02, f"Template {PLANTILLA}: " + esq["concept"].capitalize(), 7, fontweight="bold")
    yt -= 0.5
    ax.add_patch(Rectangle((xt - 0.05, yt - alto / 2), 5.45, alto, facecolor="#eeeeee", lw=0, zorder=2.5))
    for nombre, dx in [("ID", 0.05), ("Nº tubos", 1.75), ("Terreno", 2.9), ("Trabajo", 4.25)]:
        t(ax, xt + dx, yt, nombre, 7, fontweight="bold")
    for i, k in enumerate(FILAS[:4]):
        p = parametros(cat[k])
        yy = yt - alto * (i + 1)
        ax.plot([xt - 0.05, xt + 5.4], [yy + alto / 2] * 2, color="#dddddd", lw=0.5, zorder=3)
        t(ax, xt + 0.05, yy, k, 7, family="monospace")
        t(ax, xt + 2.2, yy, p["Nº TUBOS"], 7.5, color=NARANJA, fontweight="bold", ha="center")
        t(ax, xt + 2.9, yy, p["TIPO DE TERRENO"], 7.5, color=NARANJA, fontweight="bold")
        t(ax, xt + 4.25, yy, p["TRABAJO"], 7)
    t(ax, xt + 2.7, yt - alto * 5 + 0.05, "⋮", 8, ha="center", color=GRIS)

    xb = 8.95
    rbox(ax, xb, y0 + 0.25, 4.4, 3.15, BORDE, FONDO_NARANJA, lw=0.7, r=0.12)
    producto = " × ".join(str(len(v)) for v in esq["axes"].values())
    t(ax, xb + 2.2, y0 + 3.2, f"{producto} = {esq['num_items']:,}\nvariants of one template,\n"
      "differing only in parameter values", 7, ha="center", fontweight="bold", va="top", linespacing=1.3)
    disposicion = [(0.25, 1.55), (2.25, 1.55), (0.25, 0.95), (2.25, 0.95), (1.25, 0.4)]
    for (eje, valores), (dx, dy) in zip(esq["axes"].items(), disposicion):
        chip(ax, xb + dx, y0 + dy, f"{EJES[eje]} ({len(valores)})", NARANJA, size=7, w=1.9, h=0.42)

    # --- fila 2: el método
    y0 = filas[1][0]
    pasos = [("Parse BC3", 1.9), ("Add parameter tokens", 3.1), ("Retrieve top 100", 2.6),
             ("Score at item and parent level", 4.15)]
    hueco = (W - 0.6 - sum(w for _, w in pasos)) / (len(pasos) - 1)
    x = 0.3
    for i, (nombre, w) in enumerate(pasos):
        rbox(ax, x, y0 + 3.4, w, 0.5, "black", lw=0.7, r=0.08)
        t(ax, x + w / 2, y0 + 3.65, nombre, 7, ha="center")
        if i < len(pasos) - 1:
            flecha(ax, x + w + 0.04, y0 + 3.65, x + w + hueco - 0.04, y0 + 3.65)
        x += w + hueco

    yb, hb = y0 + 0.25, 2.95
    rbox(ax, 0.3, yb, 4.55, hb, GRIS, "#f6f6f6", lw=0.6, r=0.08)
    t(ax, 0.42, yb + hb - 0.25, f"Test query {CONSULTA}", 7, fontweight="bold")
    t(ax, 0.42, yb + hb - 0.5, envolver(d["consulta"], 34), 7, va="top", linespacing=1.25)

    flecha(ax, 4.9, yb + hb / 2, 5.1, yb + hb / 2)
    xk = 5.15
    rbox(ax, xk, yb, 3.55, hb, GRIS, lw=0.6, r=0.08)
    t(ax, xk + 0.12, yb + hb - 0.25, "Parameter tokens", 7, fontweight="bold")
    for i, tk in enumerate(d["tokens"]):
        rbox(ax, xk + 0.1, yb + hb - 0.83 - 0.42 * i, 3.35, 0.36, NARANJA, lw=0.6, r=0.06)
        t(ax, xk + 0.18, yb + hb - 0.65 - 0.42 * i, token_corto(tk), 7, family="monospace")

    flecha(ax, 8.75, yb + hb / 2, 8.95, yb + hb / 2)
    xc = 9.0
    rbox(ax, xc, yb, 4.35, hb, GRIS, lw=0.6, r=0.08)
    t(ax, xc + 0.12, yb + hb - 0.25, "BM25 top 3 (score)", 7, fontweight="bold")
    oro = d["top3"][0][0]
    for i, (k, s) in enumerate(d["top3"]):
        yy = yb + hb - 0.8 - 0.72 * i
        color = NARANJA if k == oro else "#999999"
        ax.add_patch(Ellipse((xc + 0.3, yy), 0.32, 0.32, color=color, zorder=4))
        t(ax, xc + 0.3, yy, str(i + 1), 7, ha="center", color="white", fontweight="bold")
        t(ax, xc + 0.6, yy + 0.13, k, 7, family="monospace")
        p = parametros(d["catalogo"][k])
        t(ax, xc + 0.6, yy - 0.18, f"{p['Nº TUBOS']} t · {p['BANDA DE MANTENIMIENTO']}", 7, color=GRIS)
        t(ax, xc + 4.2, yy + 0.13, f"{s:.1f}", 7, ha="right", color=NARANJA if k == oro else GRIS)
    t(ax, xc + 0.12, yb + 0.2, "✓ item level  ✓ parent level", 7, color=VERDE, fontweight="bold")

    # --- fila 3: el resultado
    y0 = filas[2][0]
    axb = barras_acc(fig, [1.05 / W, (y0 + 0.75) / H, 5.0 / W, 2.9 / H], d["barras"],
                     ["BM25 +\nparam. tokens", "Best\nhybrid", "Best neural\n(ColBERT)"],
                     size=7, ancho_barra=0.62, con_pct=True)
    axb.set_yticks([0, 50, 100])
    axb.set_ylabel("Acc@1 (%)", fontsize=7, labelpad=2)
    t(ax, 0.3, y0 + 3.9, "Bars: exact variant · dashed: right family", 7, color=GRIS)

    xe, ye = 6.85, y0 + 0.25
    rbox(ax, xe, ye, 6.5, 3.75, ROJO, lw=0.8, r=0.12)
    lo, hi = min(d["numericos"].values()), max(d["numericos"].values())
    t(ax, xe + 3.25, ye + 3.45, f"Numeric mismatches: {lo:.1f}–{hi:.1f}% of errors", 7.5, ha="center",
      color=ROJO, fontweight="bold")
    t(ax, xe + 3.25, ye + 3.1, "in BM25, BGE-M3 ColBERT and the hybrid alike", 7, ha="center", color=GRIS)
    for i, (sistema, eje, recuperado, correcto) in enumerate(d["errores"]):
        yy = ye + 2.6 - 1.05 * i
        t(ax, xe + 0.2, yy, f"{eje} ({sistema})", 7, fontweight="bold")
        for xx, color, fondo, texto in [(xe + 0.2, ROJO, FONDO_ROJO, recuperado),
                                        (xe + 3.5, VERDE, FONDO_VERDE, correcto)]:
            rbox(ax, xx, yy - 0.72, 2.8, 0.44, color, fondo, lw=0.6, r=0.06)
            t(ax, xx + 1.4, yy - 0.5, texto, 7, ha="center", color=color)
        t(ax, xe + 3.25, yy - 0.5, "vs", 7, ha="center")
    t(ax, xe + 1.6, ye + 0.22, "retrieved", 7, ha="center", color=GRIS)
    t(ax, xe + 4.9, ye + 0.22, "correct", 7, ha="center", color=GRIS)

    problemas = revisar(fig)
    for p in problemas:
        print("  AVISO figura 1:", p)
    guardar(fig, out, tiff=False)


# ---------------------------------------------------------------- graphical abstract

def graphical_abstract(d: dict, out: Path) -> None:
    W, H = 13.0, 5.2  # 5:2, y legible a los 13 cm de ancho que exige Elsevier
    fig, ax = lienzo(W, H)
    cols = [(0.05, 4.22), (4.39, 4.22), (8.73, 4.22)]
    for x, w in cols:
        rbox(ax, x, 0.05, w, H - 0.1, BORDE, lw=1.0, r=0.15)
    titulos = [f"{d['n_items']:,} catalog items,\nmany nearly identical",
               f"{sum(n for _, n in CONFIGS)} retrieval configurations,\neach scored twice",
               "Dense models find the family,\nnot the exact variant"]
    for (x, w), s in zip(cols, titulos):
        t(ax, x + w / 2, H - 0.5, s, 8, ha="center", fontweight="bold", linespacing=1.1)

    # columna 1: variantes que sólo difieren en los tubos o en el terreno
    x0, cat = cols[0][0] + 0.2, d["catalogo"]
    t(ax, x0, 3.95, f"{PLANTILLA}: {d['esquema'][PLANTILLA]['num_items']:,} variants", 7, fontweight="bold")
    yt, alto = 3.45, 0.5
    t(ax, x0 + 2.05, yt, "Tubos", 7, fontweight="bold", color=GRIS, ha="center")
    t(ax, x0 + 2.55, yt, "Terreno", 7, fontweight="bold", color=GRIS)
    for i, k in enumerate(FILAS[:4]):
        p = parametros(cat[k])
        yy = yt - alto * (i + 1)
        ax.plot([x0, x0 + 3.85], [yy + alto / 2] * 2, color="#dddddd", lw=0.5, zorder=3)
        t(ax, x0, yy, k, 7, family="monospace")
        t(ax, x0 + 2.05, yy, p["Nº TUBOS"], 7.5, color=NARANJA, fontweight="bold", ha="center")
        t(ax, x0 + 2.55, yy, p["TIPO DE TERRENO"], 7.5, color=NARANJA, fontweight="bold")
    t(ax, x0 + 1.9, 0.75, "⋮", 8, ha="center", color=GRIS)

    # columna 2: una consulta, dos niveles de acierto
    x0 = cols[1][0] + 0.2
    rbox(ax, x0, 3.05, 3.82, 0.8, GRIS, "#f6f6f6", lw=0.6, r=0.08)
    t(ax, x0 + 1.91, 3.45, "Query: a short catalog\ndescription", 7, ha="center", linespacing=1.1)
    for xx, nivel, detalle in [(x0, "Right family", "its template"), (x0 + 2.0, "Exact variant", "its unit price")]:
        flecha(ax, xx + 0.91, 3.0, xx + 0.91, 2.55)
        rbox(ax, xx, 1.55, 1.82, 0.95, VERDE, FONDO_VERDE, lw=0.7, r=0.08)
        t(ax, xx + 0.91, 2.2, nivel, 7.5, ha="center", color=VERDE, fontweight="bold")
        t(ax, xx + 0.91, 1.85, detalle, 7, ha="center")
    t(ax, x0 + 1.91, 0.85, "lexical · neural · hybrid · structured", 7, ha="center", color=GRIS)

    # columna 3: barras
    x0 = cols[2][0]
    axb = barras_acc(fig, [(x0 + 0.6) / W, 0.95 / H, 3.35 / W, 2.45 / H], d["barras"],
                     ["BM25 +\nparams", "Best\nhybrid", "Best\nneural"], size=7, ancho_barra=0.72, con_pct=False)
    axb.set_yticks([0, 50, 100])
    t(ax, x0 + 0.25, 3.9, "Acc@1 (%)   bars: exact variant", 7, color=GRIS)
    t(ax, x0 + 1.33, 3.6, "dashed: right family", 7, color=GRIS)

    guardar(fig, out, tiff=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fig1", type=Path, default=OUT_FIG1, help="ruta sin extensión")
    parser.add_argument("--ga", type=Path, default=OUT_GA, help="ruta sin extensión")
    args = parser.parse_args()

    plt.rcParams["font.family"] = ["Arial", "Segoe UI Symbol"]  # la segunda sólo para ✓ y ⋮
    datos = cargar()
    figura1(datos, args.fig1)
    graphical_abstract(datos, args.ga)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
