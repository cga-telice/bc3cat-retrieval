#!/usr/bin/env python3
"""Prepara la carpeta de ficheros para el envío a Advanced Engineering Informatics.

El sistema de envío de Elsevier aplana las carpetas y la guía pide el fuente
LaTeX editable (no vale un PDF), cada figura en su propio fichero con nombres
tipo Figure_1, los highlights en un fichero editable con «highlights» en el
nombre y el graphical abstract aparte. A partir de `paper/paper_rev_AEI.tex`:

- `manuscript.tex`: las tablas de `paper/tables/` incrustadas, las figuras
  renombradas a Figure_N según su número en el .aux, sin `\\graphicspath` y sin
  los comentarios de línea (había notas internas en español);
- `references.bib` y `manuscript.bbl`;
- `Figure_N.pdf` para todas las figuras, también las dos que se dibujan en el
  propio LaTeX (2 y 3), exportadas a PDF sueltas;
- `highlights.docx`, `graphical_abstract.tiff` / `.pdf`;
- `manuscript.pdf`, compilado desde la propia carpeta para comprobar que el
  paquete se basta a sí mismo, y `README.md` con qué subir como qué.

Uso:  python scripts/build_submission.py
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).parent))
from build_paper import SIGNIFICANT, docker_available, run_in_container  # noqa: E402

PAPER = Path("paper")
STEM = "paper_rev_AEI"
OUT = Path("submission/aei")
HIGHLIGHTS = PAPER / "highlights.txt"
GA = PAPER / "figures" / "graphical_abstract"
TEXTWIDTH = "390pt"  # la caja de texto del preprint de 12 pt, para exportar las figuras 2 y 3


def numeros_de_figura(aux: Path) -> dict[str, int]:
    return {m.group(1): int(m.group(2))
            for m in re.finditer(r"\\newlabel\{(fig:[^}]+)\}\{\{(\d+)\}", aux.read_text(encoding="utf-8"))}


def incrustar_tablas(tex: str) -> str:
    def sustituir(m):
        contenido = (PAPER / m.group(1)).read_text(encoding="utf-8")
        return "\n".join(l for l in contenido.splitlines() if not l.lstrip().startswith("%"))
    return re.sub(r"\\input\{(tables/[^}]+)\}", sustituir, tex)


def quitar_comentarios(tex: str) -> str:
    lineas = []
    for l in tex.splitlines():
        if l.lstrip().startswith("%"):
            continue
        # comentario al final de la línea, salvo un % escapado o el % que corta el salto de línea
        l = re.sub(r"(?<!\\)\s+%(?!$).*$", "", l)
        lineas.append(l)
    return "\n".join(lineas) + "\n"


def entornos_figura(tex: str):
    for m in re.finditer(r"\\begin\{(figure|sidewaysfigure)\}(.*?)\\end\{\1\}", tex, re.S):
        etiqueta = re.search(r"\\label\{(fig:[^}]+)\}", m.group(2))
        yield m, etiqueta.group(1) if etiqueta else None


def preambulo(tex: str) -> str:
    """Los paquetes y bibliotecas del manuscrito, para compilar las figuras sueltas."""
    usados = re.findall(r"^\\(?:usepackage|usetikzlibrary)(?:\[[^]]*\])?\{[^}]*\}", tex, re.M)
    fuera = ("lineno", "hyperref", "rotating", "natbib")
    return "\n".join(u for u in usados if not any(f in u for f in fuera))


def docx_highlights(lineas: list[str], destino: Path) -> None:
    """Un .docx mínimo: título y una viñeta por highlight (sin depender de python-docx)."""
    def parrafo(texto, estilo=None):
        ppr = f'<w:pPr><w:pStyle w:val="{estilo}"/></w:pPr>' if estilo else ""
        return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{escape(texto)}</w:t></w:r></w:p>'
    W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    cuerpo = parrafo("Highlights", "Title") + "".join(parrafo("• " + l) for l in lineas)
    archivos = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            '</Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>',
        "word/_rels/document.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>',
        "word/styles.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {W}>'
            '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="22"/>'
            '</w:rPr></w:rPrDefault></w:docDefaults>'
            '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:sz w:val="28"/>'
            '</w:rPr></w:style></w:styles>',
        "word/document.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W}>'
            f'<w:body>{cuerpo}</w:body></w:document>',
    }
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, contenido in archivos.items():
            z.writestr(nombre, contenido)


def compilar(carpeta: Path, stem: str, bibtex: bool) -> str:
    pasos = [["pdflatex", "-interaction=nonstopmode", "-halt-on-error", stem]]
    if bibtex:
        pasos += [["bibtex", stem]] + [pasos[0]] * 2
    for paso in pasos:
        r = run_in_container(carpeta, paso)
        if r.returncode != 0 and paso[0] != "bibtex":
            print(r.stdout[-3000:], file=sys.stderr)
            raise SystemExit(f"{paso[0]} {stem} falló con código {r.returncode}")
    return (carpeta / f"{stem}.log").read_text(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    if not docker_available():
        print("Docker no responde. Arranca Docker Desktop y vuelve a intentarlo.", file=sys.stderr)
        return 1

    out = args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    tex = (PAPER / f"{STEM}.tex").read_text(encoding="utf-8")
    numeros = numeros_de_figura(PAPER / f"{STEM}.aux")
    pre = preambulo(tex)

    # Figuras: las de fichero se copian con su número; las dibujadas en LaTeX se exportan sueltas.
    figuras = []
    for m, etiqueta in entornos_figura(tex):
        n = numeros[etiqueta]
        grafico = re.search(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", m.group(2))
        if grafico:
            origen = PAPER / "figures" / grafico.group(1)
            destino = f"Figure_{n}{origen.suffix}"
            shutil.copy2(origen, out / destino)
            figuras.append((n, etiqueta, destino, grafico.group(1)))
        else:
            cuerpo = m.group(2)
            cuerpo = cuerpo[cuerpo.index(r"\centering") + len(r"\centering"):cuerpo.index(r"\caption")]
            suelta = out / f"_fig{n}"
            suelta.mkdir()
            (suelta / f"Figure_{n}.tex").write_text(
                "\\documentclass[12pt,border=4pt]{standalone}\n" + pre + "\n"
                f"\\setlength{{\\textwidth}}{{{TEXTWIDTH}}}\n\\begin{{document}}\n"
                f"\\begin{{minipage}}{{\\textwidth}}\\centering\n{cuerpo.strip()}\n\\end{{minipage}}\n\\end{{document}}\n",
                encoding="utf-8")
            compilar(suelta, f"Figure_{n}", bibtex=False)
            shutil.copy2(suelta / f"Figure_{n}.pdf", out / f"Figure_{n}.pdf")
            shutil.rmtree(suelta)
            figuras.append((n, etiqueta, f"Figure_{n}.pdf", None))
    figuras.sort()

    # Manuscrito plano.
    plano = incrustar_tablas(tex)
    for _, _, destino, original in figuras:
        if original:
            plano = re.sub(r"(\\includegraphics(?:\[[^]]*\])?\{)" + re.escape(original) + r"\}",
                           lambda m: m.group(1) + destino + "}", plano)
    plano = re.sub(r"^\\graphicspath\{.*\}\s*$", "", plano, flags=re.M)
    plano = quitar_comentarios(plano)
    (out / "manuscript.tex").write_text(plano, encoding="utf-8")
    shutil.copy2(PAPER / "references.bib", out / "references.bib")

    log = compilar(out, "manuscript", bibtex=True)
    problemas = [l for l in log.splitlines() if any(s in l for s in SIGNIFICANT)]
    paginas = re.findall(r"Output written on .*?\((\d+) pages", log)
    for f in out.iterdir():
        if f.stem == "manuscript" and f.suffix not in (".tex", ".bbl", ".pdf"):
            f.unlink()

    lineas = [l.lstrip("•").strip() for l in HIGHLIGHTS.read_text(encoding="utf-8").splitlines()
              if l.strip().startswith("•")]
    assert 3 <= len(lineas) <= 5 and all(len(l) <= 85 for l in lineas), "los highlights no cumplen 3-5 × 85"
    docx_highlights(lineas, out / "highlights.docx")
    for ext in (".tiff", ".pdf"):
        shutil.copy2(GA.with_suffix(ext), out / f"graphical_abstract{ext}")

    filas = "\n".join(f"| `{d}` | Figure | Figura {n} (`{etiqueta}`)"
                      + (", dibujada en LaTeX; también está en el fuente" if not o else "") + " |"
                      for n, etiqueta, d, o in figuras)
    (out / "README.md").write_text(f"""# Envío a Advanced Engineering Informatics

Generado por `scripts/build_submission.py` desde `paper/{STEM}.tex`. No editar a mano:
se regenera entero.

| Fichero | Tipo en el sistema de envío | Notas |
|---|---|---|
| `manuscript.tex` | Manuscript (LaTeX source) | tablas incrustadas, figuras como Figure_N |
| `references.bib`, `manuscript.bbl` | LaTeX supplementary / source files | bibliografía (`elsarticle-num`) |
{filas}
| `highlights.docx` | Highlights | {len(lineas)} highlights, ≤ 85 caracteres |
| `graphical_abstract.tiff` | Graphical Abstract | 13 × 5,2 cm, 300 dpi (`.pdf` como alternativa) |
| `manuscript.pdf` | (no subir: lo genera el sistema) | compilado desde esta carpeta para comprobarla |

Pendiente antes de enviar: los DOI de Zenodo en `references.bib` (`bc3cat_dataset`,
`bc3cat_software`) y en la sección de disponibilidad de datos, cuando se publiquen
los depósitos; después, volver a generar esta carpeta.
""", encoding="utf-8")

    print(f"-> {out}  ({len(list(out.iterdir()))} ficheros, manuscript.pdf: {paginas[-1] if paginas else '?'} páginas)")
    for n, etiqueta, d, _ in figuras:
        print(f"   {d:22s} {etiqueta}")
    if problemas:
        print(f"\n{len(problemas)} avisos relevantes al compilar la carpeta:")
        for l in problemas[:20]:
            print(f"    {l.strip()}")
        return 1
    print("\nOK: la carpeta compila sola, sin citas ni referencias sin resolver.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
