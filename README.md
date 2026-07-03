# Fetch All

Sincronizador de repositórios git locais. Varre automaticamente **todos os
discos do computador** em busca de projetos git, faz `fetch` em todos e
sincroniza com segurança: `pull --ff-only` nos que estão atrás do remoto e
`push` nos que estão à frente. Ideal para garantir que tudo subiu para o
GitHub antes de trocar de máquina.

## Segurança em primeiro lugar

Nada é executado sem sua revisão: a varredura monta um **plano** (o que será
puxado, o que será enviado e o que tem problema) e só age depois da sua
confirmação. Repositórios em qualquer estado arriscado são **apenas
reportados, nunca tocados**:

- mudanças não commitadas ou arquivos não rastreados;
- histórico divergente entre local e remoto (exigiria merge/rebase);
- merge, rebase ou cherry-pick em andamento;
- sem remoto, branch sem upstream ou HEAD desanexado;
- erro de fetch (rede, credenciais, remoto removido).

O pull é sempre `--ff-only`: nunca cria commit de merge nem sobrescreve nada.

## Como rodar

Forma mais simples — abre o menu interativo onde você instala, configura e inicia:

```bash
python start_app.py
```

No menu você escolhe: **Iniciar/Rodar** (varre e sincroniza), **Instalar/Setup**
(dependências `rich` e `questionary`), **Configurar** (restringir a varredura a
pastas específicas e editar exclusões) e **Status/Sair**.

## Requisitos

- Python 3.10+ (3.12+ no Windows para detecção automática de discos)
- Git instalado e no `PATH`, com credenciais já configuradas (o programa
  nunca pede senha; repositórios sem credencial aparecem como erro de fetch)

## Configuração

Por padrão não é preciso configurar nada: com a lista de caminhos vazia, o
programa varre todos os discos locais (fixos e removíveis). Se quiser
restringir, use **Configurar** no menu — os caminhos ficam em `config.json`
(ignorado pelo git por conter caminhos locais). Pastas pesadas, de sistema ou
de ferramentas (`node_modules`, `Windows`, `Program Files`, caches de
assistentes de IA, bibliotecas Steam etc.) são puladas por padrão e a lista
de exclusões é editável.

Após a primeira varredura completa, os repositórios encontrados ficam em um
cache local (`scan_cache.json`, também ignorado pelo git). Nas execuções
seguintes você escolhe entre a varredura **rápida** (usa o cache — ideal
para rodar de novo após resolver pendências) e a **completa** (varre os
discos de novo para encontrar repositórios criados desde então).

## Estrutura

```
start_app.py          # porta de entrada — menu interativo
fetchall/
  config.py           # leitura/gravação do config.json
  cache.py            # cache da última varredura (execuções rápidas)
  scanner.py          # detecção de discos e varredura por repositórios
  gitrepo.py          # análise de estado e ações git (fetch/pull/push)
  syncer.py           # orquestração: plano em duas fases (analisar → executar)
  report.py           # tabelas e painéis no terminal (rich)
```

## Ideias para quem quiser contribuir

- Exportar o relatório final em arquivo (Markdown/JSON) para auditoria.
- Agendamento periódico da sincronização.
- Suporte a criar upstream automaticamente (`push -u`) mediante confirmação.

## Licença

MIT — veja [LICENSE](LICENSE).
