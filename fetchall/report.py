"""Apresentação dos resultados no terminal usando rich.

Separa a camada visual da lógica de sincronização: aqui só se formata,
nada de decisão sobre repositórios.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .gitrepo import RepoStatus
from .syncer import ActionResult, SyncPlan

console = Console()


def show_plan(plan: SyncPlan) -> None:
    """Mostra o plano completo: ações seguras primeiro, depois problemas."""
    console.print(
        Panel(
            f"[bold]{plan.total}[/bold] repositórios encontrados — "
            f"[green]{len(plan.up_to_date)} atualizados[/green], "
            f"[cyan]{len(plan.to_pull)} para pull[/cyan], "
            f"[yellow]{len(plan.to_push)} para push[/yellow], "
            f"[red]{len(plan.problems)} com problema[/red]",
            title="Resultado da varredura",
            border_style="blue",
        )
    )

    if plan.to_pull or plan.to_push:
        table = Table(title="Ações seguras planejadas (nada foi executado ainda)")
        table.add_column("Repositório", style="bold")
        table.add_column("Branch")
        table.add_column("Ação", style="cyan")
        table.add_column("Commits")
        for status in plan.to_pull:
            table.add_row(str(status.path), status.branch, "pull (fast-forward)", f"{status.behind} atrás")
        for status in plan.to_push:
            table.add_row(str(status.path), status.branch, "push", f"{status.ahead} à frente")
        console.print(table)

    if plan.problems:
        table = Table(
            title="⚠ Problemas — exigem sua atenção, NADA será feito nestes",
            border_style="red",
        )
        table.add_column("Repositório", style="bold")
        table.add_column("Branch")
        table.add_column("Problema", style="red")
        table.add_column("Detalhe")
        for status in plan.problems:
            table.add_row(str(status.path), status.branch or "—", status.state.value, status.detail)
        console.print(table)

    if not plan.has_actions and not plan.problems:
        console.print("[green]Tudo sincronizado — nenhum repositório precisa de ação.[/green]")


def show_problem_details(problems: list[RepoStatus]) -> None:
    """Lista os arquivos modificados dos repositórios sujos, para diagnóstico."""
    for status in problems:
        if status.dirty_files:
            console.print(f"\n[bold]{status.path}[/bold] ({status.state.value}):")
            for line in status.dirty_files[:20]:
                console.print(f"  [yellow]{line}[/yellow]")
            if len(status.dirty_files) > 20:
                console.print(f"  … e mais {len(status.dirty_files) - 20} arquivo(s)")


def show_results(results: list[ActionResult]) -> None:
    """Mostra o resultado de cada pull/push executado."""
    if not results:
        return
    table = Table(title="Execução")
    table.add_column("Repositório", style="bold")
    table.add_column("Ação")
    table.add_column("Resultado")
    table.add_column("Mensagem")
    for result in results:
        outcome = "[green]ok[/green]" if result.ok else "[red]FALHOU[/red]"
        message = result.message.splitlines()[-1] if result.message else ""
        table.add_row(str(result.status.path), result.action, outcome, message)
    console.print(table)

    failures = [r for r in results if not r.ok]
    if failures:
        console.print(
            f"[red]{len(failures)} ação(ões) falharam — nenhum dado foi perdido; "
            "verifique os repositórios listados acima.[/red]"
        )
    else:
        console.print("[green]Todas as ações concluídas com sucesso.[/green]")
