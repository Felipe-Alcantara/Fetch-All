"""Registro em Markdown de cada passada de sincronização.

A cada execução da sincronização, um arquivo ``passadas/AAAA-MM-DD_HH-MM-SS.md``
é criado com o que foi feito, o que não foi feito, o que foi salvo no remoto
e o que ficou pendente. A pasta fica na raiz do projeto e é ignorada pelo git
por conter caminhos locais da máquina.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .config import PROJECT_ROOT
from .gitrepo import RepoStatus
from .security import redact_sensitive_text
from .syncer import ActionResult, SyncPlan

RUNS_DIR = PROJECT_ROOT / "passadas"


def _repo_line(status: RepoStatus, extra: str = "") -> str:
    path = _inline_code(str(status.path))
    branch = f" ({_inline_code(status.branch)})" if status.branch else ""
    suffix = f" — {_single_line(extra)}" if extra else ""
    return f"- {path}{branch}{suffix}"


def _single_line(value: str) -> str:
    """Impede que texto externo injete novas linhas no Markdown."""
    return " ".join(redact_sensitive_text(value).splitlines())


def _inline_code(value: str) -> str:
    """Formata texto local como código mesmo quando ele contém crases."""
    clean = _single_line(value)
    runs = [len(match.group()) for match in re.finditer(r"`+", clean)]
    fence = "`" * (max(runs, default=0) + 1)
    return f"{fence} {clean} {fence}"


def build_run_report(
    plan: SyncPlan,
    results: list[ActionResult],
    executed: bool,
    scan_mode: str,
    when: datetime,
) -> str:
    """Monta o conteúdo Markdown do relatório de uma passada."""
    ok = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    lines = [
        f"# Passada de {when.strftime('%d/%m/%Y %H:%M:%S')}",
        "",
        f"- **Varredura:** {scan_mode}",
        f"- **Repositórios encontrados:** {plan.total}",
        f"- **Atualizados:** {len(plan.up_to_date)} · "
        f"**para pull:** {len(plan.to_pull)} · "
        f"**para push:** {len(plan.to_push)} · "
        f"**com problema:** {len(plan.problems)}",
        "",
        "## O que foi feito",
        "",
    ]
    if ok:
        lines += [_repo_line(r.status, f"{r.action} concluído") for r in ok]
    elif executed:
        lines.append("- Nenhuma ação foi concluída com sucesso.")
    else:
        lines.append("- Nada foi executado (sem ações seguras ou execução não confirmada).")

    lines += ["", "## O que não foi feito", ""]
    skipped = False
    if not executed and plan.has_actions:
        skipped = True
        lines += [
            _repo_line(s, f"{action} planejado, não executado")
            for action, bucket in (("pull", plan.to_pull), ("push", plan.to_push))
            for s in bucket
        ]
    if failed:
        skipped = True
        lines += [
            _repo_line(r.status, f"{r.action} FALHOU: {r.message.strip() or 'sem mensagem'}")
            for r in failed
        ]
    # Problemas resolvidos nesta passada (commit automático bem-sucedido)
    # não contam como "não feito".
    resolved = {r.status.path for r in ok if r.action == "commit"}
    unresolved = [s for s in plan.problems if s.path not in resolved]
    if unresolved:
        skipped = True
        lines += [
            _repo_line(s, f"{s.state.value}" + (f" — {s.detail}" if s.detail else ""))
            for s in unresolved
        ]
    if not skipped:
        lines.append("- Nada ficou de fora: todas as ações planejadas foram executadas.")

    saved = [r for r in ok if r.action == "push"]
    lines += ["", "## O que foi salvo no remoto", ""]
    if saved:
        lines += [_repo_line(r.status, "push enviado ao remoto") for r in saved]
    else:
        lines.append("- Nenhum push nesta passada.")

    pending = (
        len(unresolved)
        + len(failed)
        + (len(plan.to_pull) + len(plan.to_push) if not executed else 0)
    )
    lines += ["", "## Pendências", ""]
    if pending:
        lines.append(
            f"- {pending} item(ns) exigem atenção manual (listados em "
            '"O que não foi feito"). Resolva e rode a sincronização de novo.'
        )
    else:
        lines.append("- Nenhuma pendência: tudo sincronizado.")
    lines.append("")
    return "\n".join(lines)


def write_run_report(
    plan: SyncPlan,
    results: list[ActionResult],
    executed: bool,
    scan_mode: str,
    when: datetime | None = None,
    runs_dir: Path | None = None,
) -> Path:
    """Grava o relatório da passada em ``passadas/`` e devolve o caminho."""
    when = when or datetime.now()
    target_dir = runs_dir or RUNS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{when.strftime('%Y-%m-%d_%H-%M-%S')}.md"
    path.write_text(
        build_run_report(plan, results, executed, scan_mode, when),
        encoding="utf-8",
    )
    return path
