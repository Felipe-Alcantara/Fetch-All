"""Fetch All — sincronizador de repositórios git locais.

Varre os caminhos configurados em busca de repositórios git, faz fetch em
todos e sincroniza (pull fast-forward / push) apenas os que estão em estado
seguro. Qualquer repositório com problema (mudanças não commitadas,
divergência, conflito, sem remoto) é reportado e nunca alterado.
"""

__version__ = "1.0.0"
