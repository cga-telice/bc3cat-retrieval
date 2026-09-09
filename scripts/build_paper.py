#!/usr/bin/env python3
"""Compila el manuscrito en un contenedor, sin depender del TeX de la maquina.

No hay toolchain LaTeX instalado en el equipo y el proyecto ya se ejecuta sobre
Docker, asi que la compilacion va por el mismo camino: cualquiera que clone el
repositorio obtiene el mismo PDF sin instalar nada.

Se ejecutan tres pasadas de pdflatex con bibtex en medio, que es lo que exige
elsarticle con `elsarticle-num` para resolver referencias cruzadas y citas.

Uso:
    python scripts/build_paper.py             # compila paper/paper_28.tex
    python scripts/build_paper.py --clean     # borra subproductos y compila
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

IMAGE = "texlive/texlive:latest"
PAPER_DIR = Path("paper")
AUX_SUFFIXES = (".aux", ".bbl", ".blg", ".log", ".out", ".toc", ".fls", ".fdb_latexmk")

# Avisos de LaTeX que suelen indicar un problema real de contenido, frente al
# ruido habitual de cajas mal ajustadas.
SIGNIFICANT = (
    "Citation",
    "Reference",
    "There were undefined references",
    "Emergency stop",
    "File not found",
    "LaTeX Error",
)


def docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True, check=True, timeout=30,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def run_in_container(workdir: Path, command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "docker", "run", "--rm",
            "-v", f"{workdir.resolve()}:/paper",
            "-w", "/paper",
            IMAGE, *command,
        ],
        capture_output=True,
        text=True,
        errors="replace",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stem", default="paper_28", help="nombre del .tex sin extension")
    parser.add_argument("--clean", action="store_true", help="borra subproductos antes")
    args = parser.parse_args()

    tex = PAPER_DIR / f"{args.stem}.tex"
    if not tex.exists():
        print(f"No existe {tex}", file=sys.stderr)
        return 1

    if not docker_available():
        print(
            "Docker no responde. Arranca Docker Desktop y vuelve a intentarlo.",
            file=sys.stderr,
        )
        return 1

    if args.clean:
        for suffix in AUX_SUFFIXES:
            target = PAPER_DIR / f"{args.stem}{suffix}"
            if target.exists():
                target.unlink()
                print(f"borrado {target}")

    steps = [
        ("pdflatex (1/3)", ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", args.stem]),
        ("bibtex", ["bibtex", args.stem]),
        ("pdflatex (2/3)", ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", args.stem]),
        ("pdflatex (3/3)", ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", args.stem]),
    ]

    for name, command in steps:
        print(f"-> {name}")
        result = run_in_container(PAPER_DIR, command)
        # bibtex devuelve codigo 2 por avisos (campos ausentes), que no impiden
        # producir la bibliografia; solo pdflatex debe abortar la compilacion.
        fatal = result.returncode != 0 and not command[0] == "bibtex"
        if fatal:
            print(result.stdout[-4000:] or result.stderr[-4000:], file=sys.stderr)
            print(f"\n{name} fallo con codigo {result.returncode}", file=sys.stderr)
            return 1

    pdf = PAPER_DIR / f"{args.stem}.pdf"
    if not pdf.exists():
        print("La compilacion no produjo PDF", file=sys.stderr)
        return 1

    log = (PAPER_DIR / f"{args.stem}.log").read_text(encoding="utf-8", errors="replace")
    issues = [
        line
        for line in log.splitlines()
        if any(marker in line for marker in SIGNIFICANT)
    ]

    print()
    print(f"PDF: {pdf}  ({pdf.stat().st_size / 1024:.0f} KB)")
    pages = re.findall(r"Output written on .*?\((\d+) pages", log)
    if pages:
        print(f"paginas: {pages[-1]}")

    if issues:
        print(f"\n{len(issues)} avisos relevantes:")
        for line in issues[:25]:
            print(f"    {line.strip()}")
        if len(issues) > 25:
            print(f"    ... y {len(issues) - 25} mas")
        return 1

    print("\nOK: sin citas ni referencias sin resolver.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
