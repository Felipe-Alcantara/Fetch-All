# 🔄 Fetch All

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)
![SO](https://img.shields.io/badge/Windows%20%C2%B7%20Linux%20%C2%B7%20macOS-suportados-blueviolet?style=for-the-badge)
![Git](https://img.shields.io/badge/Git-obrigat%C3%B3rio-F05032?style=for-the-badge&logo=git&logoColor=white)
[![Qualidade](https://img.shields.io/github/actions/workflow/status/Felipe-Alcantara/Fetch-All/quality.yml?branch=main&style=for-the-badge&label=qualidade)](https://github.com/Felipe-Alcantara/Fetch-All/actions/workflows/quality.yml)
![Licença](https://img.shields.io/badge/Licen%C3%A7a-MIT-green?style=for-the-badge)

**Sincronize repositórios Git locais com revisão prévia e ações conservadoras.**

[🚀 Como usar](#-como-usar) • [⭐ Segurança](#-sincronização-segura-) • [📖 Documentação](#-documentação) • [🤝 Contribuir](#-contribuições)

</div>

---

## 📋 Índice

- [🛡️ **Sincronização segura**](#-sincronização-segura-) ⭐ **DESTAQUE**
- [📋 Sobre o Projeto](#-sobre-o-projeto)
- [📁 Estrutura do Projeto](#-estrutura-do-projeto)
- [🚀 Funcionalidades](#-funcionalidades)
- [📖 Documentação](#-documentação)
- [🎯 Como Usar](#-como-usar)
- [📚 Guia Rápido](#-guia-rápido)
- [🔧 Funcionalidades Técnicas](#-funcionalidades-técnicas)
- [🧪 Qualidade e Testes](#-qualidade-e-testes)
- [⚠️ Limitações](#-limitações)
- [🔒 Segurança](#-segurança)
- [📝 Licença](#-licença)
- [👤 Autor](#-autor)
- [🤝 Contribuições](#-contribuições)

---

## 🛡️ Sincronização segura ⭐

> **REVISE O PLANO COMPLETO ANTES DE QUALQUER PULL, PUSH OU COMMIT.**

O Fetch All faz `fetch`, classifica cada repositório e apresenta as ações
possíveis. Pull, push e commit automático exigem confirmação explícita e o
estado é revalidado imediatamente antes da escrita.

### 💡 Por que usar?

- **🎯 Conservador:** pull sempre usa `--ff-only`; históricos divergentes não são mesclados.
- **🔍 Auditável:** cada passada gera um relatório Markdown local.
- **🛡️ Defensivo:** conflitos, worktrees sujos e planos obsoletos são preservados.
- **💻 Portável:** detecta discos locais em Windows, Linux e macOS.

---

## 📋 Sobre o Projeto

Quem mantém muitos projetos Git espalhados pelo computador pode perder a visão
do que ainda não chegou ao remoto. O **Fetch All** encontra repositórios nos
discos locais, atualiza suas referências remotas e monta um plano seguro para o
branch atual de cada um.

O `fetch` da fase de análise atualiza metadados dentro de `.git`, mas não altera
o worktree nem cria commits locais. As operações que mudam o branch ou o remoto
só acontecem depois da revisão e confirmação no menu.

---

## 📁 Estrutura do Projeto

```text
Fetch-All/
├── 📁 .github/workflows/       # Integração contínua em Python 3.10, 3.12 e 3.13
├── 📁 docs/                    # Contratos e evidências de qualidade
├── 📁 fetchall/                # Aplicação modular
│   ├── environment.py          # Bootstrap e diagnóstico do ambiente
│   ├── menu.py                 # Interface TUI e delegação de ações
│   ├── scanner.py              # Descoberta de discos e repositórios
│   ├── gitrepo.py              # Análise e operações Git conservadoras
│   ├── syncer.py               # Orquestração e revalidação do plano
│   ├── config.py               # Configuração validada
│   ├── cache.py                # Cache da última varredura
│   ├── runlog.py               # Relatório Markdown de cada passada
│   ├── security.py             # Redação de credenciais e tokens
│   └── storage.py              # Persistência atômica
├── 📁 scripts/                 # Ferramentas internas de manutenção
├── 📁 tests/                   # Testes unitários, integração Git e regressão
├── start_app.py                # Porta de entrada única do programa
├── pyproject.toml              # Ruff e cobertura
├── requirements.lock           # Dependências de execução com hashes
├── requirements-dev.lock       # Ferramentas de qualidade com hashes
├── IA.md                       # Memória técnica e estado atual
├── README.md                   # Este arquivo
└── LICENSE                     # Licença MIT
```

---

## 🚀 Funcionalidades

### 🔍 Varredura automática (`fetchall/scanner.py`)

**`scanner.py`**

- Detecta discos fixos e removíveis locais.
- Pula montagens virtuais, de rede e diretórios pesados configurados.
- Varre discos distintos em paralelo e deduplica raízes aninhadas.
- Exemplo: `[/, /mnt/dados]` → `[ProjetoA, ProjetoB]`.

### 🔀 Sincronização conservadora (`fetchall/gitrepo.py`, `fetchall/syncer.py`)

**`gitrepo.py`** e **`syncer.py`**

- Classificam atualizado, pull, push, divergência, conflito e erros.
- Revalidam o estado imediatamente antes de cada ação.
- Interrompem apenas o repositório que falhar.
- Exemplo: `behind=2, worktree limpo` → `pull --ff-only` planejado.

### ⚡ Cache local (`fetchall/cache.py`)

**`cache.py`**

- Reutiliza repositórios conhecidos em uma varredura rápida.
- Descarta entradas que não existem mais.
- Invalida o cache quando as raízes mudam.
- Exemplo: `scan_cache.json válido` → análise direta sem percorrer o disco.

### 📌 Commit automático opcional (`fetchall/syncer.py`)

**`execute_auto_commits()`**

- Aceita somente worktrees sujos que não estejam atrás do remoto.
- Mostra candidatos e mensagem antes da confirmação.
- Executa commit, pull fast-forward e push em sequência protegida.
- Exemplo: `DIRTY, behind=0` → candidato; `DIRTY, behind=1` → preservado.

### 📝 Registro de passadas (`fetchall/runlog.py`)

**`runlog.py`**

- Registra ações concluídas, recusadas e pendências.
- Neutraliza novas linhas e Markdown vindos de mensagens externas.
- Mantém caminhos locais fora do controle de versão.
- Exemplo: uma execução → `passadas/AAAA-MM-DD_HH-MM-SS.md`.

---

## 📖 Documentação

- 📖 [Contrato e checklist de qualidade](docs/QUALITY.md)
- 📖 [Como contribuir](CONTRIBUTING.md)
- 📖 [Política de segurança](SECURITY.md)
- 📖 [Contexto operacional para IA](IA.md)
- 📖 [Licença MIT](LICENSE)

---

## 🎯 Como Usar

### Opção 1: menu interativo — recomendado

#### Instalação

Não é necessário instalar dependências manualmente. Na primeira execução, o
bootstrap oferece criar `.venv` e instalar o lockfile homologado.

#### Execução

```bash
# Abra a porta de entrada única do programa
python start_app.py
```

Se o sistema não disponibilizar `python`, use:

```bash
# Nome comum do interpretador em Linux e macOS
python3 start_app.py
```

O menu oferece **Iniciar/Rodar**, **Instalar/Setup**, **Configurar**, **Status**
e **Sair**. A configuração de caminhos, exclusões e paralelismo acontece no
próprio menu, sem edição manual obrigatória.

### Requisitos

- Windows, Linux ou macOS.
- Python 3.10 ou mais recente.
- Git disponível no `PATH`, com credenciais já configuradas.
- Rede acessível aos remotos durante `fetch`, pull ou push.

---

## 📚 Guia Rápido

### Para Iniciantes

1. Rode `python start_app.py`.
2. Escolha **Status** para conferir Python, Git e ambiente local.
3. Use **Configurar** se quiser limitar a busca a uma pasta.
4. Escolha **Iniciar** e leia o plano antes de confirmar qualquer ação.

### Para Desenvolvedores

1. Crie `.venv`.
2. Instale `requirements.lock` e `requirements-dev.lock` em comandos separados.
3. Rode `.venv/bin/python scripts/check_quality.py` antes de contribuir.
4. Atualize README e `IA.md` quando o comportamento mudar.

### Para Uso Prático

- **Antes de trocar de computador:** use varredura completa.
- **Na rotina diária:** use o cache e escolha varredura rápida.
- **Ao encontrar divergência:** resolva manualmente; o Fetch All não cria merge.

---

## 🔧 Funcionalidades Técnicas

- **`analyze_repo(path)`**: faz fetch opcional e classifica o branch atual.
- **`scan_and_analyze(config)`**: descobre, analisa em paralelo e monta o plano.
- **`execute_plan(plan)`**: revalida e executa apenas pulls/pushes ainda seguros.
- **`atomic_write_text(path, content)`**: persiste configuração e cache sem escrita parcial.
- **`redact_sensitive_text(text)`**: mascara credenciais e formatos conhecidos de token.

Configurações locais ficam em `config.json`; o cache fica em
`scan_cache.json`. Ambos são ignorados pelo Git porque contêm caminhos da
máquina. O programa não usa banco de dados, servidor web ou arquivo `.env`.

---

## 🧪 Qualidade e Testes

Prepare o ambiente de desenvolvimento:

```bash
# Crie o ambiente virtual
python -m venv .venv

# Instale primeiro a aplicação e depois as ferramentas, ambos com hashes
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install -r requirements-dev.lock

# Execute a mesma validação usada pela integração contínua
.venv/bin/python scripts/check_quality.py
```

No Windows, substitua `.venv/bin/python` por `.venv\Scripts\python.exe`. O
comando valida compilação, dependências, Ruff, formatação, links internos,
testes com cobertura de branches e vulnerabilidades conhecidas. A cobertura
mínima automatizada da lógica não visual é 80%; a TUI fica fora apenas da
métrica percentual, e as regras que ela aciona permanecem cobertas.

---

## ⚠️ Limitações

- **Branch atual:** somente o branch em checkout é sincronizado.
- **Upstream:** branches sem upstream são reportados; não há `push -u` automático.
- **Cache:** repositórios novos exigem uma varredura completa.
- **Subárvores:** o paralelismo da varredura é por disco, não por pasta do mesmo disco.
- **Rede:** a auditoria e operações Git dependem dos serviços externos correspondentes.

---

## 🔒 Segurança

⚠️ **IMPORTANTE:** revise a lista de arquivos antes de autorizar commit
automático. Ele usa `git add -A` e inclui arquivos não rastreados.

- Comandos externos usam listas de argumentos e nunca `shell=True`.
- `GIT_TERMINAL_PROMPT=0` impede prompts de credencial ocultos durante a análise.
- Mensagens mascaram credenciais em URLs, parâmetros sensíveis e tokens conhecidos.
- Pull usa `--ff-only`; conflitos e divergências exigem intervenção manual.
- Configuração externa é validada e persistida atomicamente.

Relate problemas sensíveis conforme [SECURITY.md](SECURITY.md).

---

## 📝 Licença

Este projeto está sob a licença MIT — veja [LICENSE](LICENSE).

---

## 👤 Autor

**Felipe Martin**

- GitHub: [@Felipe-Alcantara](https://github.com/Felipe-Alcantara)
- Repositório: [Fetch All](https://github.com/Felipe-Alcantara/Fetch-All)

---

## 🤝 Contribuições

Contribuições são bem-vindas. Consulte [CONTRIBUTING.md](CONTRIBUTING.md) para:

- reportar bugs com reprodução objetiva;
- propor melhorias de segurança ou portabilidade;
- expandir formatos de relatório;
- melhorar testes e documentação.

---

⭐ Se o Fetch All foi útil, considere dar uma estrela no GitHub!
