# IA.md — Contexto operacional do Fetch All

Linha do tempo técnica do projeto. Adicione registros datados; não apague
nem reescreva entradas antigas.

## Objetivo

Programa que varre o computador inteiro em busca de repositórios git,
faz fetch em todos e sincroniza (pull/push) apenas os que estão em estado
seguro, reportando qualquer problema antes de agir — para garantir que
todos os projetos subiram ao remoto antes de uma troca de máquina.

## Stack e convenções

- Python (stdlib para toda a lógica; `rich` + `questionary` só para a TUI).
- Git via `subprocess` (`git -C <repo> …`), sem bibliotecas de binding.
- Estrutura: lógica no pacote `fetchall/`, entrada única em `start_app.py`
  (menu obrigatório do Felixo System Design).
- Configuração em `config.json` na raiz, ignorado pelo git (caminhos locais).

## Registros

### 2026-07-03 — Criação do projeto

- **Decisão: plano em duas fases.** `scan_and_analyze` (somente leitura:
  varredura + fetch paralelo + classificação) separado de `execute_plan`
  (pull/push). O menu mostra o plano completo e exige confirmação explícita
  antes de qualquer escrita. Motivo: requisito do usuário de "avisar antes
  de qualquer coisa" em caso de problema ou conflito.
- **Decisão: ações conservadoras.** Pull sempre `--ff-only`; push simples só
  quando o branch está estritamente à frente. Estados DIRTY, DIVERGED,
  CONFLICT (MERGE_HEAD/REBASE_HEAD/CHERRY_PICK_HEAD), NO_REMOTE,
  NO_UPSTREAM, DETACHED e FETCH_ERROR são apenas reportados.
- **Decisão: varredura automática de todos os discos.** Com `scan_roots`
  vazio no config, `scanner.list_local_drives()` enumera as unidades fixas
  e removíveis via `os.listdrives()` + `GetDriveTypeW` (rede e CD/DVD são
  ignoradas). Configurar caminhos passa a ser opcional, só para restringir.
- **Decisão: git não interativo.** `GIT_TERMINAL_PROMPT=0` em todo comando,
  para um repositório sem credenciais falhar como FETCH_ERROR em vez de
  travar a varredura pedindo senha.
- **Validação:** varredura executada na pasta real de projetos do usuário,
  encontrando e classificando os repositórios corretamente (atualizados,
  para push e com pendências), sem executar nenhuma escrita.
- **Teste em massa (mesmo dia):** varredura completa dos 14 discos locais
  encontrou 205 repositórios (74 atualizados, 44 para pull, 87 com problema
  apenas reportados). 42 pulls concluídos; 2 falharam de forma segura e
  ficaram intactos: um por nome de arquivo com `:` no histórico (inválido em
  NTFS, exige renomear no remoto) e um por erro de escrita no disco destino.
- **Correção pós-teste:** caminhos e mensagens do git agora passam por
  `rich.markup.escape` antes de irem para o terminal — um caminho terminado
  em `\` (ex.: `P:\`) escapava o fechamento `[/bold]` e vazava a marcação.
- **Limites conhecidos / convites a contribuição:** não cria upstream
  automaticamente (`push -u`); sincroniza apenas o branch atual de cada
  repositório; relatório só em tela (sem exportação).
