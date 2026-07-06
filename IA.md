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
- **Melhorias pós-teste (pedidas pelo usuário):** exclusões padrão passam a
  cobrir caches de assistentes de IA (`.gemini`, `.codex`, `.claude`) e
  bibliotecas Steam (`SteamLibrary`, `steamapps`), com mesclagem automática
  em configs salvos antes; discos numerados na varredura e no status; cache
  da última varredura (`scan_cache.json`, ignorado pelo git) com escolha
  entre varredura rápida (cache) e completa a cada execução — o cache
  descarta repositórios apagados e é invalidado se os caminhos mudarem.
- **Auditoria de conformidade com o padrão de qualidade:** adicionada suíte
  de testes (`tests/`, 25 testes com `unittest`, offline — remotos são
  repositórios bare temporários) cobrindo classificação de estados,
  segurança do pull `--ff-only` em divergência, scanner, mesclagem de
  exclusões no config e cache; README reescrito na estrutura obrigatória do
  `DESIGN_SYSTEM_README.md` (badges, índice, seções canônicas, autor);
  `.gitignore` organizado e comentado.
- **Correção de usabilidade (pedida pelo usuário):** tabelas do relatório
  não cortam mais texto com "…" — colunas de caminho, detalhe e mensagem
  usam `overflow="fold"`; falhas de execução mostram a mensagem completa
  do git.
- **Limites conhecidos / convites a contribuição:** não cria upstream
  automaticamente (`push -u`); sincroniza apenas o branch atual de cada
  repositório; relatório só em tela (sem exportação).

### 2026-07-04 — Correção do setup do menu e validação de qualidade

- **Bug corrigido:** a opção **Instalar/Setup** chamava `pip install` no
  Python em execução e sempre imprimia sucesso, mesmo quando o pip falhava
  em ambientes gerenciados pelo sistema (PEP 668). Agora o setup valida o
  retorno do pip, não marca falha como sucesso e prepara as dependências em
  `.venv` local quando o menu não está rodando dentro dele.
- **Decisão:** o bootstrap sem `rich`/`questionary` também usa o `.venv`
  local e reabre o menu com o Python isolado, evitando instalação global
  acidental e mantendo o `start_app.py` como porta de entrada única.
- **Documentação:** README passou a explicitar `python3 start_app.py` quando
  `python` não existir, além do comportamento do setup com `.venv`.
- **Validação planejada:** regressão coberta por testes unitários do
  `start_app.py`, além da suíte offline completa e compilação dos módulos.

### 2026-07-05 — Registro em Markdown de cada passada

- **Feature (pedida pelo usuário):** cada execução da sincronização gera um
  arquivo `passadas/AAAA-MM-DD_HH-MM-SS.md` com data/hora, modo de
  varredura, totais, o que foi feito, o que não foi feito (ações
  canceladas, falhas e problemas), o que foi salvo no remoto (pushes) e as
  pendências.
- **Decisão:** lógica isolada em `fetchall/runlog.py` (montagem do texto
  separada da gravação, para testabilidade); o menu apenas chama
  `write_run_report` ao final de `_run_sync`, em qualquer desfecho
  (executado, cancelado ou sem ações). A pasta `passadas/` é ignorada pelo
  git por conter caminhos locais da máquina.
- **Validação:** 5 testes novos em `tests/test_runlog.py` (executado,
  cancelado, sem pendências, falha de ação e nome do arquivo); suíte
  completa com 33 testes passando.

### 2026-07-05 — Commit automático opcional para repositórios sujos

- **Feature (pedida pelo usuário):** quando a única pendência de um
  repositório é commitar (DIRTY sem estar atrás do remoto), o menu oferece
  um commit automático de tudo com mensagem padronizada
  (`chore: commit automático do Fetch All — <dia da semana>, <data> <hora>`),
  seguido de pull `--ff-only` e push.
- **Decisão de segurança (reforçada pelo usuário):** repositórios sujos que
  também estão atrás do remoto ficam de fora — commitar neles criaria
  divergência. O fluxo exige confirmação explícita (default Não), o pull
  continua fast-forward-only e qualquer falha interrompe a sequência daquele
  repositório, apenas reportando; nada destrutivo é executado.
- **Implementação:** `commit_all` em `gitrepo.py` (`add -A` + `commit -m`);
  `auto_commit_candidates`, `build_auto_commit_message` e
  `execute_auto_commits` em `syncer.py`; oferta no `_run_sync` do menu; o
  registro de passadas passa a não listar como pendência os repositórios
  resolvidos pelo commit automático.
- **Validação:** 5 testes novos (mensagem, filtro de candidatos, fluxo
  commit+pull+push real em repositório temporário, falha de commit
  interrompendo o fluxo, e runlog sem pendência falsa); suíte completa com
  38 testes passando.

### 2026-07-06 — Portabilidade para qualquer SO e varredura paralela por disco

- **Auditoria (pedida pelo usuário):** o programa anunciava suporte amplo,
  mas tinha lacunas reais fora do Windows e em Python antigo. Corrigidas:
  - **Linux/macOS/BSD:** a varredura automática partia de `/` e descia em
    `/proc`, `/sys`, snaps e montagens de rede. Agora o scanner lê os pontos
    de montagem (`/proc/mounts` no Linux; comando `mount` no macOS/BSD;
    fallback estático `/proc`, `/sys`, `/dev`, `/run`) e poda os de
    filesystem virtual ou de rede — `fuseblk` (ntfs-3g) segue sendo tratado
    como disco local. Funções de parse puras (`parse_linux_mount_skips`,
    `parse_bsd_mount_skips`) para testabilidade; `find_git_repos` aceita
    `skip_paths` injetável.
  - **Windows com Python < 3.12:** `os.listdrives()` não existia; fallback
    via `GetLogicalDrives` (ctypes). Requisito geral do projeto passa a ser
    Python 3.10+, conferido no início do menu com mensagem clara.
  - **Bug de relançamento:** o bootstrap reabria o menu com `os.execv`, que
    no Windows não trata espaços no caminho (o próprio projeto pode viver em
    pasta com espaços). Trocado por `subprocess.run` + `sys.exit`.
  - **Git ausente:** a sincronização agora verifica `shutil.which("git")`
    antes de varrer e mostra dica de instalação específica do SO (winget,
    xcode-select/brew, apt); o Status usa a mesma dica.
  - **Exclusões padrão POSIX:** `lost+found`, `.cache` (ex.: pre-commit
    clona repositórios git internos ali), `snap`, `.Trash`, `.Trashes` —
    mescladas automaticamente em configs antigos.
- **Feature (pedida pelo usuário): varredura paralela.** Com mais de uma
  raiz (ex.: vários discos no Windows), cada disco é varrido em uma thread
  própria (`ThreadPoolExecutor` + fila, sentinela por disco), com
  deduplicação de repositórios repetidos entre raízes. Threads (e não
  asyncio) porque `os.walk` é bloqueante e o gargalo é I/O de disco — mesmo
  modelo do fetch paralelo já existente. Com uma raiz só (Linux/macOS), o
  caminho sequencial simples é mantido.
- **Validação:** 9 testes novos (parse de mounts Linux com escapes octais e
  fstypes de rede, parse do `mount` BSD/macOS, poda de `skip_paths`,
  varredura multi-raiz paralela, deduplicação, relançamento via subprocess
  e guarda de versão do Python); suíte completa com 47 testes passando;
  `mount_skip_paths()` validado na máquina real (21 montagens virtuais
  detectadas e puladas).
- **Limite conhecido:** a paralelização é por disco/raiz; no Linux/macOS a
  varredura automática usa uma raiz única (`/`), então não há ganho de
  paralelismo nesse modo — dividir uma raiz em sub-árvores paralelas fica
  como convite a contribuição.

### 2026-07-06 — Paralelismo por disco também no Linux/macOS

- **Melhoria (fechando o limite registrado acima):** no POSIX, cada
  disco/partição local montado agora vira uma raiz de varredura própria
  (`local_mount_points`): `/` mais `/mnt/…`, `/media/…`, `/Volumes/…` etc.,
  cada um em sua thread — a varredura acontece em todos os discos ao mesmo
  tempo também fora do Windows.
- **Decisões:**
  - Cada raiz poda as outras raízes aninhadas nela (ex.: `/` não desce em
    `/home` quando `/home` é partição própria com thread própria), para
    nada ser varrido duas vezes.
  - `/boot` fica de fora (nunca tem repositório do usuário); no macOS,
    montagens sob `/System/` ficam de fora porque o volume de dados já é
    alcançado por `/` via firmlinks — listá-lo duplicaria a varredura.
  - `parse_linux_mounts`/`parse_bsd_mounts` passam a devolver pares
    `(ponto, fstype)`; as funções de skip são derivadas delas, e
    `local_mount_points` aceita a lista injetada para testes.
  - Raízes repetidas são deduplicadas antes de criar threads.
- **Efeito colateral aceito:** a lista de raízes muda em relação à versão
  anterior (ex.: `["/"]` → `["/", "/mnt/dados"]`), invalidando o cache de
  varredura uma vez — comportamento correto do `matches_roots`.
- **Validação:** 4 testes novos (raiz por disco local com ntfs-3g dentro e
  rede/virtual/boot fora, filtro de `/System` no macOS, fallback para `/`,
  raízes aninhadas sem duplicar repositórios); suíte completa com 51 testes
  passando. Na máquina real (1 disco: `/` ext4 + `/boot/efi` filtrada) as
  raízes resolvem para `["/"]`, como esperado.
- **Limite conhecido (atualizado):** sub-árvores de um mesmo disco ainda são
  sequenciais; paralelizar dentro de um disco segue como convite a
  contribuição.
