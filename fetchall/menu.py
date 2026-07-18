"""Interface TUI: apresenta ações e delega regras aos módulos de domínio."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import questionary
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from . import environment
from .cache import load_cache
from .config import CONFIG_PATH, DEFAULT_EXCLUDES, Config, load_config, save_config
from .report import show_plan, show_problem_details, show_results
from .runlog import write_run_report
from .scanner import resolve_scan_roots
from .security import redact_sensitive_text
from .syncer import (
    ActionResult,
    build_auto_commit_message,
    execute_auto_commits,
    execute_plan,
    scan_and_analyze,
)


def run_sync() -> None:
    """Varre, mostra o plano e só sincroniza após confirmação."""
    console = Console()
    if shutil.which("git") is None:
        console.print(
            f"[red]Git não encontrado no PATH[/red] — {environment.git_install_hint()} "
            "e rode a sincronização de novo. Nada foi alterado."
        )
        return
    config = load_config()
    roots = resolve_scan_roots(config.scan_roots)

    cached_repos = None
    cache = load_cache()
    if cache and cache.matches_roots(roots):
        repos = cache.valid_repos()
        when = cache.scanned_at.strftime("%d/%m/%Y %H:%M")
        mode = questionary.select(
            "Como varrer?",
            choices=[
                questionary.Choice(
                    f"⚡ Rápida — cache de {when} ({len(repos)} repositórios conhecidos)",
                    "fast",
                ),
                questionary.Choice(
                    "🔍 Completa — varre os discos novamente e encontra repositórios novos",
                    "full",
                ),
            ],
        ).ask()
        if mode is None:
            return
        if mode == "fast":
            cached_repos = repos

    scope = "todos os discos locais" if not config.scan_roots else "caminhos configurados"
    numbered = ", ".join(f"{i}. {root}" for i, root in enumerate(roots, start=1))
    if cached_repos is not None:
        console.print(f"Varredura rápida: [bold]{len(cached_repos)}[/bold] repositórios do cache.")
    else:
        console.print(f"Varrendo {scope} ({len(roots)}): [bold]{escape(numbered)}[/bold]")
    with console.status("[cyan]Procurando repositórios e fazendo fetch…[/cyan]"):
        plan = scan_and_analyze(config, cached_repos=cached_repos)

    show_plan(plan)
    show_problem_details(plan.problems)
    if plan.problems:
        console.print(
            "\n[red bold]Atenção:[/red bold] os repositórios com problema acima "
            "não serão tocados. Resolva-os manualmente e rode novamente."
        )

    scan_mode = "rápida (cache)" if cached_repos is not None else "completa"
    results: list[ActionResult] = []
    executed = False
    if plan.has_actions:
        confirmed = questionary.confirm(
            f"Executar {len(plan.to_pull)} pull(s) fast-forward e "
            f"{len(plan.to_push)} push(es) listados acima?",
            default=False,
        ).ask()
        if confirmed:
            executed = True
            with console.status("[cyan]Sincronizando…[/cyan]"):
                results = execute_plan(plan)
            show_results(results)
        else:
            console.print("[yellow]Cancelado — nenhum repositório foi alterado.[/yellow]")

    candidates = plan.auto_commit_candidates
    if candidates:
        message = build_auto_commit_message()
        console.print(
            f"\n[bold]{len(candidates)}[/bold] repositório(s) podem receber "
            "commit automático de tudo + pull fast-forward + push:"
        )
        for status in candidates:
            console.print(f"  • {escape(str(status.path))} ({escape(status.detail)})")
        console.print(f"Mensagem do commit: [bold]{escape(message)}[/bold]")
        console.print(
            "[dim]Repositórios também atrasados ficam de fora. Qualquer falha "
            "interrompe apenas aquele repositório.[/dim]"
        )
        confirmed = questionary.confirm(
            f"Commitar tudo e sincronizar esses {len(candidates)} repositório(s)?",
            default=False,
        ).ask()
        if confirmed:
            executed = True
            with console.status("[cyan]Commitando e sincronizando…[/cyan]"):
                auto_results = execute_auto_commits(candidates, message)
            results += auto_results
            show_results(auto_results)
        else:
            console.print("[yellow]Commit automático recusado — nada foi commitado.[/yellow]")

    report_path = write_run_report(plan, results, executed, scan_mode)
    console.print(f"Registro da passada salvo em [bold]{escape(str(report_path))}[/bold]")


def _configure_excludes(config: Config, console: Console) -> None:
    """Adiciona ou remove exclusões personalizadas sem alterar os padrões seguros."""
    custom = [name for name in config.exclude_dirs if name not in DEFAULT_EXCLUDES]
    console.print(f"Exclusões padrão: {escape(str(DEFAULT_EXCLUDES))}")
    console.print(f"Exclusões personalizadas: {escape(str(custom or '(nenhuma)'))}")
    action = questionary.select(
        "O que fazer com as exclusões personalizadas?",
        choices=[
            questionary.Choice("➕ Adicionar pasta", "add"),
            questionary.Choice("➖ Remover pasta", "remove"),
            questionary.Choice("↩ Voltar", "back"),
        ],
    ).ask()
    if action == "add":
        name = questionary.text("Nome exato da pasta a excluir:").ask()
        if name and name.strip() and name.strip() not in config.exclude_dirs:
            config.exclude_dirs.append(name.strip())
    elif action == "remove" and custom:
        selected = questionary.checkbox(
            "Marque as exclusões personalizadas a remover:", choices=custom
        ).ask()
        for item in selected or []:
            config.exclude_dirs.remove(item)


def configure() -> None:
    """Edita caminhos, exclusões e paralelismo pelo menu."""
    console = Console()
    config = load_config()
    while True:
        roots = config.scan_roots or ["(vazio — varre todos os discos automaticamente)"]
        console.print(f"\nCaminhos de varredura: [bold]{escape(str(roots))}[/bold]")
        console.print(f"Paralelismo de análise: [bold]{config.max_workers}[/bold]")
        choice = questionary.select(
            "Configurar o quê?",
            choices=[
                questionary.Choice("➕ Adicionar caminho de varredura", "add"),
                questionary.Choice("➖ Remover caminho de varredura", "remove"),
                questionary.Choice("🚫 Editar pastas excluídas", "excludes"),
                questionary.Choice("🧵 Ajustar paralelismo", "workers"),
                questionary.Choice("💾 Salvar e voltar", "back"),
            ],
        ).ask()
        if choice == "add":
            example = "C:\\Projetos" if sys.platform == "win32" else str(Path.home() / "Projetos")
            path = questionary.path(f"Caminho da pasta (ex.: {example}):").ask()
            if path:
                resolved = str(Path(path).expanduser())
                if not Path(resolved).is_dir():
                    console.print(f"[red]Pasta não encontrada: {escape(resolved)}[/red]")
                elif resolved not in config.scan_roots:
                    config.scan_roots.append(resolved)
        elif choice == "remove" and config.scan_roots:
            selected = questionary.checkbox(
                "Marque os caminhos a remover:", choices=config.scan_roots
            ).ask()
            for item in selected or []:
                config.scan_roots.remove(item)
        elif choice == "excludes":
            _configure_excludes(config, console)
        elif choice == "workers":
            workers = questionary.text(
                "Quantidade de repositórios analisados em paralelo (1–256):",
                default=str(config.max_workers),
                validate=lambda value: (
                    True
                    if value.isdigit() and 1 <= int(value) <= 256
                    else "Informe um número inteiro entre 1 e 256."
                ),
            ).ask()
            if workers:
                config.max_workers = int(workers)
        else:
            save_config(config)
            console.print("[green]Configuração salva em config.json.[/green]")
            return


def show_status() -> None:
    """Mostra estado real do Git, ambiente, dependências, config e cache."""
    console = Console()
    try:
        git_result = subprocess.run(
            ["git", "--version"], capture_output=True, text=True, timeout=10
        )
        git_version = git_result.stdout.strip() if git_result.returncode == 0 else "erro"
    except (FileNotFoundError, subprocess.SubprocessError):
        git_version = f"[red]git não encontrado[/red] — {environment.git_install_hint()}"

    config = load_config()
    cache = load_cache()
    table = Table(title="Status do Fetch All")
    table.add_column("Item", style="bold")
    table.add_column("Valor")
    venv_python = environment.project_venv_python()
    table.add_row("Python", sys.version.split()[0])
    table.add_row("Python do menu", escape(sys.executable))
    table.add_row(
        "Ambiente local",
        escape(str(venv_python)) if venv_python.exists() else ".venv ainda não criado",
    )
    missing = environment.missing_packages()
    table.add_row("Dependências", "ok" if not missing else "ajustar: " + ", ".join(missing))
    table.add_row("Git", git_version)
    table.add_row(
        "Config",
        escape(str(CONFIG_PATH)) + ("" if CONFIG_PATH.exists() else " (ainda não criado)"),
    )
    mode = "manual (config.json)" if config.scan_roots else "automática (discos locais)"
    table.add_row("Modo de varredura", mode)
    table.add_row("Paralelismo", str(config.max_workers))
    cache_info = (
        f"{len(cache.repos)} repositórios em {cache.scanned_at.strftime('%d/%m/%Y %H:%M')}"
        if cache
        else "(nenhuma varredura completa ainda)"
    )
    table.add_row("Cache da varredura", cache_info)
    for number, root in enumerate(resolve_scan_roots(config.scan_roots), start=1):
        marker = "" if Path(root).exists() else "  ⚠ não existe"
        table.add_row(f"Varredura {number}", f"{escape(root)}{marker}")
    console.print(table)


def run_menu() -> None:
    """Abre a porta de entrada interativa, colorida e descritiva."""
    console = Console()
    console.print(
        Panel(
            "[bold cyan]Fetch All[/bold cyan] — sincroniza repositórios Git locais.\n"
            "Pull, push e commit só após confirmação; estados ambíguos são "
            "[bold]avisados e preservados[/bold].",
            border_style="cyan",
        )
    )
    actions = {"sync": run_sync, "config": configure, "status": show_status}
    while True:
        choice = questionary.select(
            "O que você quer fazer?",
            choices=[
                questionary.Choice("🚀 Iniciar — varrer e sincronizar com segurança", "sync"),
                questionary.Choice("📦 Instalar/Setup — preparar dependências locais", "install"),
                questionary.Choice("⚙️  Configurar — caminhos, exclusões e paralelismo", "config"),
                questionary.Choice("📊 Status — verificar ambiente e configuração", "status"),
                questionary.Choice("👋 Sair — fechar sem executar outras ações", "quit"),
            ],
        ).ask()
        if choice in (None, "quit"):
            console.print("Até logo! Nada além do que você confirmou foi alterado.")
            return
        if choice == "install":
            if environment.install_menu_dependencies():
                console.print("[green]Dependências do menu prontas.[/green]")
                if not environment.uses_project_venv():
                    console.print(
                        "Ambiente preparado. Para usá-lo, rode: "
                        f"[bold]{escape(str(environment.project_venv_python()))} "
                        "start_app.py[/bold]"
                    )
            else:
                console.print("[red]Setup falhou; nada foi marcado como concluído.[/red]")
            continue
        try:
            actions[choice]()
        except KeyboardInterrupt:
            console.print("\n[yellow]Ação interrompida — voltando ao menu.[/yellow]")
        except Exception as exc:
            message = escape(redact_sensitive_text(str(exc)))
            console.print(f"[red]Erro: {message}[/red]")
