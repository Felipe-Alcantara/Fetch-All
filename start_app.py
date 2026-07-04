"""Porta de entrada do Fetch All — menu interativo (padrão Felixo System Design).

Rode ``python start_app.py`` (ou ``python3 start_app.py``) e escolha no
menu: sincronizar todos os repositórios git do PC, instalar dependências,
configurar caminhos de varredura ou ver o status. Nenhuma ação de escrita
acontece sem revisão e confirmação explícita do plano.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
REQUIRED_PACKAGES = ["rich", "questionary"]


def _missing_packages(packages: list[str] | None = None) -> list[str]:
    """Lista dependências Python que ainda não podem ser importadas."""
    missing = []
    for package in packages or REQUIRED_PACKAGES:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    return missing


def _project_venv_python() -> Path:
    """Caminho do Python do ambiente virtual local do projeto."""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _uses_project_venv() -> bool:
    """Indica se o menu está rodando pelo .venv local deste projeto."""
    return Path(sys.prefix).resolve() == VENV_DIR.resolve()


def _create_project_venv() -> bool:
    """Cria o .venv local se ele ainda não existir."""
    venv_python = _project_venv_python()
    if venv_python.exists():
        return True

    print(f"Criando ambiente virtual local em {VENV_DIR}...")
    result = subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)])
    if result.returncode == 0 and venv_python.exists():
        return True

    print(
        "Não foi possível criar o .venv. Em Debian/Ubuntu, instale "
        "python3-venv e tente novamente."
    )
    return False


def _install_packages(python_executable: Path, packages: list[str]) -> bool:
    """Instala pacotes no interpretador informado e valida o retorno."""
    result = subprocess.run(
        [str(python_executable), "-m", "pip", "install", *packages]
    )
    if result.returncode == 0:
        return True

    print(
        "A instalação falhou. O menu não vai marcar o setup como concluído; "
        "veja a mensagem do pip acima."
    )
    return False


def _install_menu_dependencies() -> bool:
    """Prepara dependências do menu em um ambiente local e isolado."""
    if _uses_project_venv():
        target_python = Path(sys.executable)
    else:
        if not _create_project_venv():
            return False
        target_python = _project_venv_python()

    print(f"Instalando dependências do menu com {target_python}...")
    return _install_packages(target_python, REQUIRED_PACKAGES)


def _bootstrap() -> bool:
    """Garante rich/questionary antes de desenhar o menu; oferece instalar."""
    missing = _missing_packages()
    if not missing:
        return True
    print(f"Dependências do menu ausentes: {', '.join(missing)}")
    answer = input(
        "Criar/atualizar .venv local e reabrir o menu? [S/n] "
    ).strip().lower()
    if answer in ("", "s", "sim", "y", "yes"):
        if not _install_menu_dependencies():
            return False
        if not _uses_project_venv():
            venv_python = _project_venv_python()
            print(f"Reabrindo menu com {venv_python}...")
            os.execv(
                str(venv_python),
                [str(venv_python), str(Path(__file__).resolve())],
            )
        return not _missing_packages()
    print("Sem as dependências o menu não pode abrir. Nada foi alterado.")
    return False


def _run_sync() -> None:
    """Ação principal: varre, mostra o plano e só executa após confirmação."""
    import questionary
    from rich.console import Console
    from rich.markup import escape

    from fetchall.cache import load_cache
    from fetchall.config import load_config
    from fetchall.report import show_plan, show_problem_details, show_results
    from fetchall.scanner import resolve_scan_roots
    from fetchall.syncer import execute_plan, scan_and_analyze

    console = Console()
    config = load_config()
    roots = resolve_scan_roots(config.scan_roots)

    # Cache da última varredura: permite pular a busca completa no disco.
    cached_repos = None
    cache = load_cache()
    if cache and cache.matches_roots(roots):
        repos = cache.valid_repos()
        when = cache.scanned_at.strftime("%d/%m/%Y %H:%M")
        mode = questionary.select(
            "Como varrer?",
            choices=[
                questionary.Choice(
                    f"⚡ Rápida — usa o cache de {when} ({len(repos)} repositórios já conhecidos)",
                    "fast",
                ),
                questionary.Choice(
                    "🔍 Completa — varre os discos de novo (encontra repositórios novos)",
                    "full",
                ),
            ],
        ).ask()
        if mode is None:
            return
        if mode == "fast":
            cached_repos = repos

    scope = "todos os discos locais" if not config.scan_roots else "caminhos configurados"
    # escape() impede que caminhos terminados em "\" quebrem a marcação do rich.
    numbered = ", ".join(f"{i}. {root}" for i, root in enumerate(roots, start=1))
    if cached_repos is not None:
        console.print(
            f"Varredura rápida: [bold]{len(cached_repos)}[/bold] repositórios do cache."
        )
    else:
        console.print(f"Varrendo {scope} ({len(roots)}): [bold]{escape(numbered)}[/bold]")
    with console.status("[cyan]Procurando repositórios e fazendo fetch…[/cyan]"):
        plan = scan_and_analyze(config, cached_repos=cached_repos)

    show_plan(plan)
    show_problem_details(plan.problems)

    if plan.problems:
        console.print(
            "\n[red bold]Atenção:[/red bold] os repositórios com problema acima "
            "NÃO serão tocados. Resolva-os manualmente (commit, merge ou "
            "configuração de remoto) e rode a sincronização de novo."
        )
    if not plan.has_actions:
        return

    if questionary.confirm(
        f"Executar {len(plan.to_pull)} pull(s) fast-forward e "
        f"{len(plan.to_push)} push(es) listados acima?",
        default=False,
    ).ask():
        with console.status("[cyan]Sincronizando…[/cyan]"):
            results = execute_plan(plan)
        show_results(results)
    else:
        console.print("[yellow]Cancelado — nenhum repositório foi alterado.[/yellow]")


def _configure() -> None:
    """Edita caminhos de varredura e exclusões pelo menu, sem editar arquivo."""
    import questionary
    from rich.console import Console

    from fetchall.config import load_config, save_config

    console = Console()
    config = load_config()
    while True:
        console.print(
            f"\nCaminhos de varredura: [bold]{config.scan_roots or '(vazio — varre todos os discos automaticamente)'}[/bold]"
        )
        choice = questionary.select(
            "Configurar o quê?",
            choices=[
                questionary.Choice("➕ Adicionar caminho de varredura", "add"),
                questionary.Choice("➖ Remover caminho de varredura", "remove"),
                questionary.Choice("🚫 Ver/editar pastas excluídas", "excludes"),
                questionary.Choice("💾 Salvar e voltar", "back"),
            ],
        ).ask()
        if choice == "add":
            path = questionary.path("Caminho da pasta (ex.: C:\\Projetos):").ask()
            if path:
                resolved = str(Path(path).expanduser())
                if not Path(resolved).exists():
                    console.print(f"[red]Pasta não encontrada: {resolved}[/red]")
                elif resolved not in config.scan_roots:
                    config.scan_roots.append(resolved)
        elif choice == "remove" and config.scan_roots:
            selected = questionary.checkbox(
                "Marque os caminhos a remover:", choices=config.scan_roots
            ).ask()
            for item in selected or []:
                config.scan_roots.remove(item)
        elif choice == "excludes":
            console.print(f"Excluídas da varredura: {config.exclude_dirs}")
            extra = questionary.text(
                "Adicionar pasta à exclusão (vazio para pular):"
            ).ask()
            if extra:
                config.exclude_dirs.append(extra)
        else:
            save_config(config)
            console.print("[green]Configuração salva em config.json.[/green]")
            return


def _status() -> None:
    """Mostra estado real: git disponível, config e caminhos existentes."""
    from rich.console import Console
    from rich.table import Table

    from fetchall.config import CONFIG_PATH, load_config

    console = Console()
    try:
        git_version = subprocess.run(
            ["git", "--version"], capture_output=True, text=True
        ).stdout.strip()
    except FileNotFoundError:
        git_version = "[red]git não encontrado no PATH — instale o Git[/red]"

    from fetchall.cache import load_cache
    from fetchall.scanner import resolve_scan_roots

    config = load_config()
    cache = load_cache()
    table = Table(title="Status do Fetch All")
    table.add_column("Item", style="bold")
    table.add_column("Valor")
    venv_python = _project_venv_python()
    table.add_row("Python", sys.version.split()[0])
    table.add_row("Python do menu", sys.executable)
    table.add_row(
        "Ambiente local",
        str(venv_python) if venv_python.exists() else ".venv ainda não criado",
    )
    missing = _missing_packages()
    table.add_row(
        "Dependências do menu",
        "ok" if not missing else "faltando: " + ", ".join(missing),
    )
    table.add_row("Git", git_version)
    table.add_row(
        "Config",
        str(CONFIG_PATH) + ("" if CONFIG_PATH.exists() else " (ainda não criado)"),
    )
    mode = "manual (config.json)" if config.scan_roots else "automática (todos os discos locais)"
    table.add_row("Modo de varredura", mode)
    cache_info = (
        f"{len(cache.repos)} repositórios em {cache.scanned_at.strftime('%d/%m/%Y %H:%M')}"
        if cache else "(nenhuma varredura completa ainda)"
    )
    table.add_row("Cache da varredura", cache_info)
    for number, root in enumerate(resolve_scan_roots(config.scan_roots), start=1):
        marker = "" if Path(root).exists() else "  ⚠ não existe"
        table.add_row(f"Varredura {number}", f"{root}{marker}")
    console.print(table)


def main() -> None:
    if not _bootstrap():
        sys.exit(1)

    import questionary
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    console.print(
        Panel(
            "[bold cyan]Fetch All[/bold cyan] — sincroniza todos os seus "
            "repositórios git antes de trocar de PC.\n"
            "Pull/push só em repositórios limpos; conflitos e pendências são "
            "[bold]avisados, nunca tocados[/bold].",
            border_style="cyan",
        )
    )

    actions = {
        "sync": _run_sync,
        "config": _configure,
        "status": _status,
    }
    while True:
        choice = questionary.select(
            "O que você quer fazer?",
            choices=[
                questionary.Choice("🚀 Iniciar — varrer o PC e sincronizar tudo", "sync"),
                questionary.Choice("📦 Instalar/Setup — dependências do menu", "install"),
                questionary.Choice("⚙️  Configurar — caminhos de varredura e exclusões", "config"),
                questionary.Choice("📊 Status — ambiente e configuração atual", "status"),
                questionary.Choice("👋 Sair", "quit"),
            ],
        ).ask()
        if choice in (None, "quit"):
            console.print("Até logo! Nada além do que você confirmou foi alterado.")
            return
        if choice == "install":
            if _install_menu_dependencies():
                console.print("[green]Dependências do menu prontas.[/green]")
                if not _uses_project_venv():
                    console.print(
                        "Ambiente local preparado. Para usar isolado, rode: "
                        f"[bold]{_project_venv_python()} start_app.py[/bold]"
                    )
            else:
                console.print("[red]Setup falhou; nada foi marcado como concluído.[/red]")
            continue
        try:
            actions[choice]()
        except KeyboardInterrupt:
            console.print("\n[yellow]Ação interrompida — voltando ao menu.[/yellow]")
        except Exception as exc:  # menu nunca morre com stack trace cru
            console.print(f"[red]Erro: {exc}[/red]")


if __name__ == "__main__":
    main()
