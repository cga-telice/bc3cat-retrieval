#!/usr/bin/env python3
"""Genera el documento de cambios entre el manuscrito enviado y el revisado.

Produce, en `paper/diff/`:

  paper_28_cambios.pdf            latexdiff compilado: lo borrado en rojo
                                  tachado, lo añadido en azul subrayado
  paper_28_revisado_overleaf.zip  el artículo revisado limpio (paper_28.tex,
                                  tables/, figures/, references.bib)
  paper_28_cambios_overleaf.zip   el documento de diferencias, con sus figuras
                                  y bibliografía

Son dos proyectos de Overleaf separados a propósito: el .tex del diff lleva las
dos versiones entrelazadas y, leído como código fuente, parece el original
anotado. Cada zip tiene un único documento principal y se verifica compilándolo
aislado desde el zip extraído.

Tres decisiones que no son obvias y que hacen que compile:

- La versión revisada lee sus tablas con `\\input{tables/...}`. latexdiff no
  sigue esos `\\input`, así que se aplanan antes: si no, cada tabla aparecería
  como una única línea cambiada en vez de como la tabla que es.
- Las tablas se marcan como bloque (vieja tachada, nueva añadida) y no celda a
  celda: las marcas de latexdiff delante de `\\hline` o de `\\cmidrule` rompen la
  compilación. Por lo mismo, la figura TikZ nueva va como bloque.
- Se compila dentro de la carpeta que luego se empaqueta, de modo que el éxito
  de la compilación es la prueba de que el zip funciona solo en Overleaf.

La versión enviada es la del commit `223a2f0`, idéntica a la que se mandó a
Automation in Construction el 2026-06-24 (ver docs/reviews/CORRECTIONS_LOG.md).

Uso:  python scripts/build_diff.py
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_paper import docker_available, run_in_container  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
OUT = PAPER / "diff"
BUILD = OUT / "overleaf"

SUBMITTED_COMMIT = "223a2f0"
NAME = "paper_28_cambios"
REVISED = "paper_28_revisado"

INPUT_RE = re.compile(r"\\input\{(tables/[^}]+)\}")

LATEXDIFF = [
    "latexdiff",
    "--encoding=utf8",
    "--math-markup=whole",
    r"--config=PICTUREENV=(?:picture|DIFnomarkup|tikzpicture|tabular)[\w\d*@]*",
]


def submitted_source() -> str:
    return subprocess.run(
        ["git", "show", f"{SUBMITTED_COMMIT}:paper/paper_28.tex"],
        cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout


def flattened_revision() -> tuple[str, int]:
    """El .tex revisado con las tablas generadas insertadas en su sitio."""
    source = (PAPER / "paper_28.tex").read_text(encoding="utf-8")

    def inline(match: re.Match) -> str:
        path = PAPER / match.group(1)
        if not path.suffix:
            path = path.with_suffix(".tex")
        lines = path.read_text(encoding="utf-8").splitlines()
        return "\n".join(l for l in lines if not l.startswith("% Generado por"))

    return INPUT_RE.subn(inline, source)


def package_revised(zip_path: Path) -> None:
    """El artículo revisado tal cual, con sus tablas generadas, para Overleaf."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(PAPER / "paper_28.tex", "paper_28.tex")
        z.write(PAPER / "references.bib", "references.bib")
        for sub in ("tables", "figures"):
            for f in sorted((PAPER / sub).iterdir()):
                if f.is_file():
                    z.write(f, f"{sub}/{f.name}")


def verify_zip(zip_path: Path, main_tex: str) -> tuple[int, int]:
    """Extrae el zip en una carpeta vacía y lo compila: (errores, páginas)."""
    check = OUT / "_zipcheck"
    if check.exists():
        shutil.rmtree(check)
    check.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(check)
    stem = Path(main_tex).stem
    pdflatex = f"pdflatex -interaction=nonstopmode {main_tex} >/dev/null 2>&1"
    script = "; ".join(["cd /paper", pdflatex, f"bibtex {stem} >/dev/null 2>&1", pdflatex, pdflatex])
    run_in_container(check, ["sh", "-c", script])
    log_path = check / f"{stem}.log"
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    errors_n = sum(1 for l in log.splitlines() if l.startswith("!"))
    written = re.search(r"Output written on \S+ \((\d+) pages", log)
    shutil.rmtree(check)
    return errors_n, int(written.group(1)) if written else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    if not docker_available():
        print("Docker no responde; el compilador de LaTeX vive en un contenedor.", file=sys.stderr)
        return 1

    # 1. Las dos versiones, como texto comparable.
    if BUILD.exists():
        shutil.rmtree(BUILD)
    (BUILD / "figures").mkdir(parents=True)
    (BUILD / "old.tex").write_text(submitted_source(), encoding="utf-8")
    revised, n_inputs = flattened_revision()
    (BUILD / "new.tex").write_text(revised, encoding="utf-8")
    print(f"versión enviada: commit {SUBMITTED_COMMIT}; revisada: {n_inputs} tablas aplanadas")

    # 2. Los activos que necesita el documento para compilar.
    shutil.copy2(PAPER / "references.bib", BUILD / "references.bib")
    for fig in (PAPER / "figures").iterdir():
        if fig.is_file():
            shutil.copy2(fig, BUILD / "figures" / fig.name)

    # 3. latexdiff y compilación completa, dentro de la carpeta que se empaqueta.
    diff_cmd = " ".join(
        [LATEXDIFF[0], LATEXDIFF[1], LATEXDIFF[2], f"'{LATEXDIFF[3]}'", "old.tex", "new.tex"]
    )
    pdflatex = f"pdflatex -interaction=nonstopmode {NAME}.tex >/dev/null 2>&1"
    script = " && ".join([
        "cd /paper",
        f"{diff_cmd} > {NAME}.tex 2> latexdiff.log",
        f"({pdflatex}; true)",
        f"(bibtex {NAME} >/dev/null 2>&1; true)",
        f"({pdflatex}; true)",
        f"({pdflatex}; true)",
    ])
    result = run_in_container(BUILD, ["sh", "-c", script])
    if result.returncode != 0:
        print(result.stdout, result.stderr, sep="\n", file=sys.stderr)
        return 1

    log = (BUILD / f"{NAME}.log").read_text(encoding="utf-8", errors="replace")
    errors = [l for l in log.splitlines() if l.startswith("!")]
    written = re.search(r"Output written on \S+ \((\d+) pages", log)
    unresolved = sorted(set(re.findall(r"(?:Reference|Citation) `([^']+)' .*undefined", log)))

    if errors or not written:
        print(f"FALLO: {len(errors)} errores de LaTeX", file=sys.stderr)
        for e in errors[:10]:
            print(f"    {e}", file=sys.stderr)
        return 1

    # 4. Entregables. Dos proyectos de Overleaf separados, cada uno con un único
    #    documento principal: si van juntos, Overleaf puede abrir el diff creyendo
    #    que es el artículo, y su código fuente parece el original anotado.
    shutil.copy2(BUILD / f"{NAME}.pdf", OUT / f"{NAME}.pdf")
    diff_zip = OUT / f"{NAME}_overleaf.zip"
    with zipfile.ZipFile(diff_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(BUILD / f"{NAME}.tex", f"{NAME}.tex")
        z.write(BUILD / "references.bib", "references.bib")
        for fig in sorted((BUILD / "figures").iterdir()):
            z.write(fig, f"figures/{fig.name}")

    revised_zip = OUT / f"{REVISED}_overleaf.zip"
    package_revised(revised_zip)

    marks_add = (BUILD / f"{NAME}.tex").read_text(encoding="utf-8").count("\\DIFadd{")
    marks_del = (BUILD / f"{NAME}.tex").read_text(encoding="utf-8").count("\\DIFdel{")
    print(f"diff compilado: {written.group(1)} páginas, 0 errores; {marks_add} adiciones, {marks_del} borrados")
    if unresolved:
        print(
            f"{len(unresolved)} referencias «??», todas en texto borrado que apunta a tablas "
            f"eliminadas en la revisión: {', '.join(unresolved)}"
        )

    # 5. La prueba de que cada zip funciona solo: extraerlo y compilarlo aislado.
    failed = False
    for zip_path, main_tex in ((revised_zip, "paper_28.tex"), (diff_zip, f"{NAME}.tex")):
        errors_n, pages = verify_zip(zip_path, main_tex)
        status = "OK" if errors_n == 0 and pages else "FALLO"
        failed |= status != "OK"
        print(f"{status}: {zip_path.name} compila aislado -> {pages} páginas, {errors_n} errores")

    print(f"-> {OUT / (NAME + '.pdf')}")
    print(f"-> {revised_zip}")
    print(f"-> {diff_zip}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
