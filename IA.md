# IA.md — Contexto operacional do Fetch All

Linha do tempo técnica do projeto. Adicione registros datados; não apague
nem reescreva entradas antigas.

## Estado atual (resumo vivo)

Última atualização: [2026-07-18]

- **Fase:** aplicação CLI funcional e conforme aos guias de qualidade aplicáveis.
- **Arquitetura:** entrada mínima em `start_app.py`; ambiente, TUI, domínio Git,
  orquestração, persistência e apresentação vivem em módulos separados.
- **Qualidade:** 76 testes, 87% de cobertura de branches da lógica não visual,
  CI multi-versão, locks com hashes, Ruff e auditoria dos dois locks
  automatizados por `scripts/check_quality.py`.
- **Em andamento:** nenhuma mudança estrutural pendente nesta entrega.
- **Riscos abertos:** comportamento específico de Windows/macOS é coberto por
  testes simulados; a CI hospedada executará após o próximo push.

## Objetivo

Programa que varre o computador inteiro em busca de repositórios git,
faz fetch em todos e sincroniza (pull/push) apenas os que estão em estado
seguro, reportando qualquer problema antes de agir — para garantir que
todos os projetos subiram ao remoto antes de uma troca de máquina.

## Metas e milestones

- [2026-07-03] ✅ Sincronização conservadora com revisão prévia.
- [2026-07-06] ✅ Varredura portátil e paralela por disco.
- [2026-07-18] ✅ Automação local de qualidade e CI multi-versão.
- [2026-07-18] ✅ Conformidade integral com os guias aplicáveis do padrão.

## Stack e convenções

- Python 3.10+ (stdlib para a lógica; Rich 15.0.0 + Questionary 2.1.1 na TUI).
- Git via `subprocess` (`git -C <repo> …`), sem bibliotecas de binding.
- Estrutura: lógica no pacote `fetchall/`, entrada única em `start_app.py`
  (menu obrigatório do Felixo System Design).
- Configuração em `config.json` na raiz, ignorado pelo git (caminhos locais).
- Dependências de execução e desenvolvimento são resolvidas em lockfiles com
  hashes; atualizações são intencionais e acompanhadas de `pip-audit`.
- Commits seguem Conventional Commits; documentação muda junto do comportamento.

## Integrações e serviços externos

- Git e remotos configurados em cada repositório; prompts interativos de
  credencial são desativados. Nenhum token é armazenado pelo Fetch All.
- GitHub Actions executa a matriz de qualidade. Não há banco, API própria,
  telemetria, serviço de deploy nem arquivo `.env`.

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

### 2026-07-13 — Varredura no macOS: /System/Volumes e drives de nuvem (PR #1)

- **Contribuição externa (PR #1, @flaviavs-commits):** no macOS a varredura
  completa ficava presa 20+ minutos. Duas causas: descer em
  `/System/Volumes/Data` (espelho do volume de dados inteiro via firmlinks,
  com os discos externos reaparecendo em `/System/Volumes/Data/Volumes/…`,
  fora do alcance da poda de raízes aninhadas) e enumerar
  `~/Library/CloudStorage` (Google Drive/OneDrive via File Provider fazem
  I/O de rede a cada `readdir`). Resultado relatado: de 20+ min para ~41 s.
- **Aplicado do PR:** `mount_skip_paths()` soma `/System/Volumes` quando
  `sys.platform == "darwin"` (`_DARWIN_SKIP_PATHS`), inclusive no caminho de
  fallback; 2 testes travam o comportamento (darwin ganha o skip, Linux não).
- **Adaptação pós-merge:** o PR colocava `"CloudStorage"` nas exclusões
  padrão por **nome**, valendo para todos os SOs — uma pasta de projeto
  chamada `CloudStorage` no Linux/Windows sumiria da varredura em silêncio.
  Trocado por poda por **caminho exato**: `darwin_cloudstorage_paths()`
  enumera `~/Library/CloudStorage` de cada usuário em `/Users` e soma ao
  `mount_skip_paths()` só no macOS. A função aceita `users_root` injetável
  para testes e devolve vazio se `/Users` não existir.
- **Validação:** 2 testes novos (poda só onde a pasta existe, com usuário
  sem CloudStorage e `/Users` inexistente) + teste do darwin atualizado;
  suíte completa com 55 testes passando.

### 2026-07-18 — Padronização integral de qualidade e segurança defensiva

- **Auditoria do repositório:** adotados `pyproject.toml`, `.editorconfig`,
  dependências de execução fixadas com hashes em `requirements.lock`, dependências
  de desenvolvimento pinadas, política de segurança, guia de contribuição e CI
  em Python 3.10/3.12/3.13. O script reutilizável
  `scripts/check_quality.py` concentra compilação, Ruff, testes, cobertura e
  `pip-audit`; o setup do menu agora instala as versões fixadas e considera
  uma versão incompatível como dependência ausente.
- **Correção de segurança temporal:** o estado de cada repositório é analisado
  novamente imediatamente antes de pull, push e commit automático. Se o estado
  mudou depois que o plano foi exibido, a escrita é recusada e registrada como
  falha segura. Pull continua `--ff-only`, e timeouts/erros de processo nas
  ações passam a virar resultados previsíveis em vez de interromper o menu.
- **Precisão do contrato:** a documentação deixou de chamar a fase de análise
  de “somente leitura”. `git fetch` não altera worktree nem commits locais, mas
  atualiza referências remotas e outros metadados em `.git` antes da revisão;
  a confirmação explícita se aplica às ações pull, push e commit automático.
- **Proteção de dados:** mensagens externas mascaram credenciais embutidas em
  URLs, parâmetros sensíveis e formatos conhecidos de token do GitHub antes de
  chegar à tela ou ao Markdown. O relatório também neutraliza quebras de linha
  e crases vindas de caminhos/mensagens, evitando injeção de estrutura.
- **Entradas e persistência:** `config.json` passou a validar a raiz, listas de
  texto e `max_workers` (1–256); cache com tipos inválidos é descartado. Config
  e cache são gravados por arquivo temporário + substituição, reduzindo risco
  de corrupção em interrupções.
- **Estados Git:** rebase por `rebase-apply`/`rebase-merge` e revert em andamento
  entram na classificação de conflito; falhas de `remote`, `status` e contagem
  de commits deixam de poder ser interpretadas como estado seguro.
- **Validação real:** 68 testes passaram, inclusive novos casos de plano
  obsoleto, rebase, timeout, segredos, esquema de configuração e cache; Ruff e
  compilação passaram; cobertura de branches da lógica não visual ficou em
  81% (mínimo automatizado: 80%); `pip-audit` não encontrou vulnerabilidades
  conhecidas nas dependências fixadas.

### 2026-07-18 — Conclusão da conformidade integral

- **Arquitetura final:** o antigo `start_app.py` monolítico foi reduzido à
  porta de entrada; bootstrap e validação do ambiente foram movidos para
  `environment.py`, e a interface interativa passou a viver em `menu.py`. O
  domínio e as integrações permanecem independentes da apresentação.
- **Menu completo:** a configuração interativa agora cobre caminhos, exclusões
  personalizadas e paralelismo, além das ações obrigatórias Iniciar,
  Instalar/Setup, Configurar, Status e Sair.
- **Reprodutibilidade:** os locks de execução e desenvolvimento incluem versões
  transitivas e hashes. A automação local e a CI auditam ambos.
- **Rastreabilidade:** `docs/QUALITY.md` relaciona cada guia aplicável ao código
  e registra por que guias de funcionalidades inexistentes estão fora do
  escopo. README, política de segurança e contribuição refletem o fluxo final.
- **Evidência final:** `scripts/check_quality.py` passou integralmente no Python
  3.12: 76 testes, cobertura de branches de 87%, Ruff, compilação, links e
  consistência do ambiente sem falhas; `pip-audit` não encontrou
  vulnerabilidades conhecidas nos locks de execução ou desenvolvimento.

### 2026-07-31 — Correção: mudanças não commitadas escondidas atrás de "sem upstream"

- **Bug corrigido:** quando um repositório estava num branch sem upstream
  configurado (ex.: `feat/uso-publico` sem `push -u`) e também tinha arquivos
  modificados/não rastreados, `analyze_repo` classificava como `NO_UPSTREAM`
  e o `detail` só mencionava a falta de upstream — as mudanças no working
  tree ficavam invisíveis na linha resumo do relatório. Parecia que o Fetch
  All estava "ignorando" o repositório, quando na verdade só omitia parte do
  diagnóstico (o repositório continuava listado em "problemas", sem nenhuma
  ação automática — comportamento conservador correto).
- **Correção:** `detail` de `NO_UPSTREAM` agora soma a contagem de arquivos
  sujos quando eles existem, em `fetchall/gitrepo.py`.
- **Teste:** `test_no_upstream_with_dirty_files_reports_both` em
  `tests/test_gitrepo.py`, cobrindo branch sem upstream com arquivo não
  commitado.

### 2026-08-04 — Verificação do fluxo Git no macOS

- **Verificação solicitada:** a implementação de `fetch`, `pull` e `push` foi
  revisada e validada com a suíte completa; o fluxo continua conservador:
  `fetch --all --prune`, `pull --ff-only` e `push` somente para branch à frente
  com upstream configurado.
- **Evidência local:** neste checkout, `origin` está configurado para fetch e
  push, `main` rastreia `origin/main` e a análise real retornou `Atualizado`,
  `ahead=0`, `behind=0` após o fetch.
- **Validação:** `scripts/check_quality.py` passou com 77 testes, 87% de
  cobertura de branches, Ruff, links, compilação e `pip-audit` sem
  vulnerabilidades conhecidas. Repositórios sem upstream, sujos, divergentes,
  destacados ou com erro de fetch permanecem intencionalmente sem ação
  automática; isso explica casos que ficam não sincronizados e são listados
  como pendência para intervenção manual.

### 2026-08-04 — Auditoria adicional de funções específicas do macOS

- **Resultado:** o terminal disponível é Linux, portanto não foi possível
  afirmar execução nativa em um Mac. Os caminhos específicos foram validados
  por testes com `sys.platform == "darwin"`: parser do `mount`, volumes locais,
  poda de `/System/Volumes`, exclusão exata de `~/Library/CloudStorage`,
  bootstrap e relançamento por subprocesso.
- **Validação:** 14 testes específicos de macOS/varredura e sincronização
  passaram; a suíte completa anterior também passou. A confirmação final de
  permissões, File Provider e credenciais depende de executar em um Mac real.
