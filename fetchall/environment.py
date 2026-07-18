"""Validação do ambiente e bootstrap das dependências da interface."""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = PROJECT_ROOT / ".venv"
REQUIREMENTS_LOCK = PROJECT_ROOT / "requirements.lock"
REQUIRED_VERSIONS = {"rich": "15.0.0", "questionary": "2.1.1"}
REQUIRED_PACKAGES = tuple(REQUIRED_VERSIONS)
MIN_PYTHON = (3, 10)


def check_python_version() -> bool:
    """Confere a versão mínima do Python com mensagem clara, em qualquer SO."""
    if sys.version_info >= MIN_PYTHON:
        return True
    minimum = ".".join(str(part) for part in MIN_PYTHON)
    print(
        f"Este programa precisa de Python {minimum} ou mais novo; "
        f"você está usando {sys.version.split()[0]}.\n"
        "Instale uma versão mais nova em https://www.python.org/downloads/ "
        "(ou pelo gerenciador de pacotes do seu sistema) e rode de novo."
    )
    return False


def git_install_hint() -> str:
    """Dica de instalação do Git adequada ao sistema operacional atual."""
    if sys.platform == "win32":
        return "instale com 'winget install Git.Git' ou baixe em https://git-scm.com"
    if sys.platform == "darwin":
        return "instale com 'xcode-select --install' ou 'brew install git'"
    return "instale pelo gerenciador do sistema (ex.: 'sudo apt install git')"


def missing_packages(packages: tuple[str, ...] | None = None) -> list[str]:
    """Lista dependências ausentes ou diferentes das versões homologadas."""
    missing = []
    for package in packages or REQUIRED_PACKAGES:
        try:
            __import__(package)
            expected = REQUIRED_VERSIONS.get(package)
            if expected is not None and version(package) != expected:
                missing.append(package)
        except (ImportError, PackageNotFoundError):
            missing.append(package)
    return missing


def project_venv_python() -> Path:
    """Caminho do Python do ambiente virtual local do projeto."""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def uses_project_venv() -> bool:
    """Indica se o menu está rodando pelo ambiente virtual local."""
    return Path(sys.prefix).resolve() == VENV_DIR.resolve()


def create_project_venv() -> bool:
    """Cria o ambiente virtual local se ele ainda não existir."""
    venv_python = project_venv_python()
    if venv_python.exists():
        return True

    print(f"Criando ambiente virtual local em {VENV_DIR}...")
    result = subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)])
    if result.returncode == 0 and venv_python.exists():
        return True

    print(
        "Não foi possível criar o .venv. Em Debian/Ubuntu, instale python3-venv e tente novamente."
    )
    return False


def install_packages(python_executable: Path) -> bool:
    """Instala o lockfile no interpretador informado e valida o retorno."""
    result = subprocess.run(
        [
            str(python_executable),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--requirement",
            str(REQUIREMENTS_LOCK),
        ]
    )
    if result.returncode == 0:
        return True

    print(
        "A instalação falhou. O menu não vai marcar o setup como concluído; "
        "veja a mensagem do pip acima."
    )
    return False


def install_menu_dependencies() -> bool:
    """Prepara dependências da TUI em ambiente local e isolado."""
    if uses_project_venv():
        target_python = Path(sys.executable)
    else:
        if not create_project_venv():
            return False
        target_python = project_venv_python()

    print(f"Instalando dependências do menu com {target_python}...")
    return install_packages(target_python)


def bootstrap() -> bool:
    """Garante Rich/Questionary antes de desenhar o menu; oferece instalar."""
    missing = missing_packages()
    if not missing:
        return True
    print(f"Dependências do menu ausentes: {', '.join(missing)}")
    answer = input("Criar/atualizar .venv local e reabrir o menu? [S/n] ").strip().lower()
    if answer not in ("", "s", "sim", "y", "yes"):
        print("Sem as dependências o menu não pode abrir. Nada foi alterado.")
        return False
    if not install_menu_dependencies():
        return False
    if not uses_project_venv():
        venv_python = project_venv_python()
        print(f"Reabrindo menu com {venv_python}...")
        completed = subprocess.run([str(venv_python), str(PROJECT_ROOT / "start_app.py")])
        raise SystemExit(completed.returncode)
    return not missing_packages()
