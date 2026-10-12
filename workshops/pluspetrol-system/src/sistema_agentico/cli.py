from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import build_plan, consolidate, project_status, approve, stable_id, validate_project
from .project import locate_project


def _print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(
        prog="taller-agentes",
        description="Administra el estado local del sistema agéntico gerencial.",
    )
    command_parser.add_argument(
        "--root", type=Path, help="Raíz del proyecto; por defecto se detecta automáticamente."
    )
    subcommands = command_parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("status", help="Muestra el estado actual del proyecto.")
    plan = subcommands.add_parser('plan', help='Crea un borrador sin buscar; conserva el existente.')
    plan.add_argument('--new', action='store_true')
    plan.add_argument('--mode', choices=['secuencial', 'delegacion_real'], default='secuencial')
    approval = subcommands.add_parser('approve-plan', help='Registra aprobación explícita.')
    approval.add_argument('--message', required=True)
    selection = subcommands.add_parser('select', help='Registra selección humana por IDs.')
    selection.add_argument('--ids', nargs='+', required=True)
    selection.add_argument('--message', required=True)
    identity = subcommands.add_parser('id', help='Genera ID estable por URL normalizada.')
    identity.add_argument('--kind', choices=['noticia', 'documento'], required=True)
    identity.add_argument('--url', required=True)
    subcommands.add_parser("consolidate", help="Valida resultados y actualiza el dashboard.")
    subcommands.add_parser("validate", help="Valida configuración y estructura.")
    return command_parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        project = locate_project(args.root)
        if args.command == "status":
            _print(project_status(project))
        elif args.command == "plan":
            _print(build_plan(project, args.new, args.mode))
        elif args.command == 'approve-plan':
            _print(approve(project, args.message))
        elif args.command == 'select':
            _print(approve(project, args.message, args.ids))
        elif args.command == 'id':
            _print({'id': stable_id(args.kind, args.url)})
        elif args.command == "consolidate":
            _print(consolidate(project)["resumen"])
        elif args.command == "validate":
            report = validate_project(project)
            _print(report)
            return 1 if report['errores'] else 0
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
