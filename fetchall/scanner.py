"""Varredura do disco em busca de repositórios git.

Percorre os caminhos configurados podando pastas excluídas (node_modules,
pastas de sistema etc.) e o interior de cada ``.git`` encontrado.
Repositórios aninhados (ex.: submódulos clonados) também são encontrados.
Com mais de um caminho, cada disco é varrido em paralelo (uma thread por
raiz — a varredura é limitada por I/O de disco, não por CPU).

Portabilidade: no Windows os discos locais são enumerados pela API do
sistema; no Linux/macOS a varredura parte de ``/`` e pula pontos de
montagem virtuais (``/proc``, ``/sys``, snaps…) e de rede (NFS, SMB…),
mantendo o escopo "discos locais" em qualquer SO.
"""

from __future__ import annotations

import os
import queue
import string
import subprocess
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Sistemas de arquivos que nunca contêm repositórios locais do usuário:
# pseudo-filesystems do kernel, caches em memória e montagens de rede.
_SKIP_FSTYPES = {
    "proc", "procfs", "sysfs", "devtmpfs", "devpts", "devfs", "tmpfs",
    "ramfs", "squashfs", "overlay", "autofs", "mqueue", "hugetlbfs",
    "debugfs", "tracefs", "securityfs", "pstore", "efivarfs", "bpf",
    "binfmt_misc", "configfs", "fusectl", "rpc_pipefs", "selinuxfs",
    "cifs", "smbfs", "smb3", "afs", "9p", "v9fs", "map",
}
# Famílias inteiras a pular; "fuse." cobre sshfs/gvfs, mas NÃO "fuseblk"
# (ntfs-3g), que é disco local de verdade.
_SKIP_FSTYPE_PREFIXES = ("nfs", "cgroup", "fuse.")
# Se a lista de montagens não puder ser lida, pula ao menos o essencial.
_FALLBACK_SKIP_PATHS = frozenset({"/proc", "/sys", "/dev", "/run"})


def _is_skipped_fstype(fstype: str) -> bool:
    """Indica se um tipo de filesystem é virtual ou de rede."""
    fstype = fstype.lower()
    return fstype in _SKIP_FSTYPES or fstype.startswith(_SKIP_FSTYPE_PREFIXES)


def parse_linux_mounts(lines: list[str]) -> list[tuple[str, str]]:
    """Extrai ``(ponto_de_montagem, fstype)`` de linhas do ``/proc/mounts``.

    Formato: ``origem ponto_de_montagem fstype opções …``. Espaços e tabs
    no caminho vêm como escapes octais (``\\040``/``\\011``).
    """
    mounts: list[tuple[str, str]] = []
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        mount_point = parts[1].replace("\\040", " ").replace("\\011", "\t")
        mounts.append((mount_point, parts[2]))
    return mounts


def parse_bsd_mounts(lines: list[str]) -> list[tuple[str, str]]:
    """Extrai ``(ponto_de_montagem, fstype)`` da saída do ``mount`` (macOS/BSD).

    Formato: ``origem on /ponto (fstype, opções…)``.
    """
    mounts: list[tuple[str, str]] = []
    for line in lines:
        if " on " not in line or "(" not in line:
            continue
        rest = line.split(" on ", 1)[1]
        mount_point, _, info = rest.rpartition(" (")
        fstype = info.split(",")[0].strip().rstrip(")")
        if mount_point:
            mounts.append((mount_point, fstype))
    return mounts


def parse_linux_mount_skips(lines: list[str]) -> set[str]:
    """Pontos de montagem virtuais/de rede em linhas do ``/proc/mounts``."""
    return {mp for mp, fstype in parse_linux_mounts(lines) if _is_skipped_fstype(fstype)}


def parse_bsd_mount_skips(lines: list[str]) -> set[str]:
    """Pontos de montagem virtuais/de rede na saída do ``mount`` (macOS/BSD)."""
    return {mp for mp, fstype in parse_bsd_mounts(lines) if _is_skipped_fstype(fstype)}


def _list_mounts() -> list[tuple[str, str]]:
    """Todas as montagens do sistema como ``(ponto, fstype)``; vazio se ilegível."""
    try:
        proc_mounts = Path("/proc/mounts")
        if proc_mounts.exists():
            lines = proc_mounts.read_text(encoding="utf-8", errors="replace").splitlines()
            return parse_linux_mounts(lines)
        result = subprocess.run(
            ["mount"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return parse_bsd_mounts(result.stdout.splitlines())
    except (OSError, subprocess.SubprocessError):
        pass
    return []


def mount_skip_paths() -> set[str]:
    """Pontos de montagem virtuais/de rede que a varredura deve pular.

    No Windows devolve vazio (a seleção de discos já filtra por tipo).
    No Linux lê ``/proc/mounts``; no macOS/BSD usa o comando ``mount``;
    se nada disso funcionar, cai num mínimo seguro (``/proc``, ``/sys``…).
    """
    if sys.platform == "win32":
        return set()
    mounts = _list_mounts()
    if mounts:
        return {mp for mp, fstype in mounts if _is_skipped_fstype(fstype)}
    return set(_FALLBACK_SKIP_PATHS)


def local_mount_points(mounts: list[tuple[str, str]] | None = None) -> list[str]:
    """Raízes de varredura no POSIX: ``/`` mais cada disco/partição local.

    Cada montagem local vira uma raiz própria para ser varrida em paralelo
    (um disco por thread). Ficam de fora as montagens virtuais/de rede,
    ``/boot`` (nunca tem repositório do usuário) e, no macOS, tudo sob
    ``/System`` — o volume de dados já é alcançado a partir de ``/`` pelos
    firmlinks, e listá-lo de novo duplicaria a varredura.
    """
    if mounts is None:
        mounts = _list_mounts()
    points = {
        mp for mp, fstype in mounts
        if not _is_skipped_fstype(fstype)
        and mp != "/"
        and mp != "/boot" and not mp.startswith("/boot/")
        and not (sys.platform == "darwin" and mp.startswith("/System/"))
    }
    return ["/"] + sorted(points)


def _windows_drive_letters() -> list[str]:
    """Raízes de unidade no Windows, com fallback para Python < 3.12."""
    if hasattr(os, "listdrives"):
        return list(os.listdrives())
    import ctypes

    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    return [
        f"{letter}:\\"
        for index, letter in enumerate(string.ascii_uppercase)
        if bitmask & (1 << index)
    ]


def list_local_drives() -> list[str]:
    """Devolve as raízes de todos os discos locais (fixos e removíveis).

    No Windows usa a API do sistema para ignorar unidades de rede e de
    CD/DVD. No Linux/macOS devolve ``/`` mais cada disco/partição local
    montado (``/mnt/…``, ``/media/…``, ``/Volumes/…``), para a varredura
    acontecer em todos os discos ao mesmo tempo; montagens virtuais e de
    rede são puladas.
    """
    if sys.platform != "win32":
        return local_mount_points()
    import ctypes

    DRIVE_REMOVABLE, DRIVE_FIXED = 2, 3
    drives = []
    for drive in _windows_drive_letters():
        drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive)
        if drive_type in (DRIVE_REMOVABLE, DRIVE_FIXED):
            drives.append(drive)
    return drives


def resolve_scan_roots(configured_roots: list[str]) -> list[str]:
    """Caminhos a varrer: os configurados ou, se vazio, todos os discos."""
    return configured_roots or list_local_drives()


def _walk_root(root_path: Path, excludes: set[str], skips: set[str]) -> Iterator[Path]:
    """Percorre uma única raiz gerando cada diretório de trabalho git."""
    for dirpath, dirnames, _filenames in os.walk(root_path, onerror=lambda _e: None):
        if ".git" in dirnames or ".git" in _filenames:
            yield Path(dirpath).resolve()
        # Poda: não desce em .git, em pastas excluídas nem em montagens
        # virtuais/de rede.
        dirnames[:] = [
            d for d in dirnames
            if d != ".git"
            and d.lower() not in excludes
            and (not skips or os.path.join(dirpath, d) not in skips)
        ]


def find_git_repos(
    scan_roots: list[str],
    exclude_dirs: list[str],
    skip_paths: set[str] | None = None,
) -> Iterator[Path]:
    """Gera o caminho de cada diretório de trabalho git sob os roots dados.

    Um repositório é qualquer pasta contendo ``.git`` (diretório ou arquivo,
    para cobrir worktrees/submódulos). A varredura não entra em ``.git``,
    nas pastas listadas em ``exclude_dirs`` (comparação sem diferenciar
    maiúsculas, pensada para Windows) nem em ``skip_paths`` — por padrão,
    os pontos de montagem virtuais/de rede detectados no sistema.

    Com várias raízes (ex.: vários discos no Windows), cada uma é varrida
    em uma thread própria e os resultados são gerados conforme aparecem;
    repositórios repetidos entre raízes são deduplicados.
    """
    excludes = {name.lower() for name in exclude_dirs}
    skips = mount_skip_paths() if skip_paths is None else skip_paths
    roots = list(dict.fromkeys(
        Path(root) for root in scan_roots if Path(root).exists()
    ))
    seen: set[Path] = set()

    # Uma raiz só: caminho simples, sem threads.
    if len(roots) <= 1:
        for root_path in roots:
            for repo in _walk_root(root_path, excludes, skips):
                if repo not in seen:
                    seen.add(repo)
                    yield repo
        return

    # Várias raízes: uma thread por disco, resultados via fila conforme
    # cada varredura avança. ``None`` é a sentinela de "este disco acabou".
    # Cada raiz pula as outras raízes aninhadas nela (ex.: "/" não desce em
    # "/mnt/dados", que já tem thread própria) para não varrer nada duas vezes.
    results: queue.Queue[Path | None] = queue.Queue()

    def scan_one(root_path: Path) -> None:
        nested_roots = {
            str(other) for other in roots
            if other != root_path and other.is_relative_to(root_path)
        }
        try:
            for repo in _walk_root(root_path, excludes, skips | nested_roots):
                results.put(repo)
        finally:
            results.put(None)

    with ThreadPoolExecutor(
        max_workers=len(roots), thread_name_prefix="fetchall-scan"
    ) as pool:
        for root_path in roots:
            pool.submit(scan_one, root_path)
        finished = 0
        while finished < len(roots):
            item = results.get()
            if item is None:
                finished += 1
            elif item not in seen:
                seen.add(item)
                yield item
