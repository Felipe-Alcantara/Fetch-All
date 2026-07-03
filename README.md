# 🔄 Fetch All

![Python](https://img.shields.io/badge/Python-3.12+-blue?style=for-the-badge&logo=python&logoColor=white)
![Git](https://img.shields.io/badge/Git-obrigat%C3%B3rio-F05032?style=for-the-badge&logo=git&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Testes](https://img.shields.io/badge/Testes-unittest-brightgreen?style=for-the-badge)

Sincronizador seguro de repositórios git locais: varre todos os discos do
computador, faz fetch em tudo e sincroniza apenas o que é 100% seguro —
avisando antes de qualquer ação.

---

## 📋 Índice

- [Sobre o Projeto](#-sobre-o-projeto)
- [Segurança em primeiro lugar](#-segurança-em-primeiro-lugar)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Funcionalidades](#-funcionalidades)
- [Como Usar](#-como-usar)
- [Testes](#-testes)
- [Limitações](#-limitações)
- [Ideias para quem quiser contribuir](#-ideias-para-quem-quiser-contribuir)
- [Licença](#-licença)
- [Autor](#-autor)

---

## 📋 Sobre o Projeto

Quem tem muitos projetos git espalhados pelo computador conhece o medo de
trocar de máquina sem ter certeza de que tudo subiu para o remoto. O
**Fetch All** resolve isso: varre automaticamente **todos os discos locais**
em busca de repositórios git, faz `fetch` em todos em paralelo e monta um
plano de sincronização — `pull --ff-only` nos que estão atrás do remoto e
`push` nos que estão à frente — que só é executado após a sua confirmação.

---

## 🛡 Segurança em primeiro lugar

Repositórios em qualquer estado arriscado são **apenas reportados, nunca
tocados**:

- mudanças não commitadas ou arquivos não rastreados;
- histórico divergente entre local e remoto (exigiria merge/rebase);
- merge, rebase ou cherry-pick em andamento;
- sem remoto, branch sem upstream ou HEAD desanexado;
- erro de fetch (rede, credenciais, remoto removido).

O pull é sempre `--ff-only`: nunca cria commit de merge nem sobrescreve nada.

---

## 📁 Estrutura do Projeto

```
start_app.py          # porta de entrada — menu interativo
fetchall/
  config.py           # leitura/gravação do config.json
  cache.py            # cache da última varredura (execuções rápidas)
  scanner.py          # detecção de discos e varredura por repositórios
  gitrepo.py          # análise de estado e ações git (fetch/pull/push)
  syncer.py           # orquestração: plano em duas fases (analisar → executar)
  report.py           # tabelas e painéis no terminal (rich)
tests/                # suíte de testes (repositórios git temporários, offline)
```

---

## 🚀 Funcionalidades

### 🔍 Varredura automática (`fetchall/scanner.py`)
Detecta todos os discos locais (fixos e removíveis) e encontra qualquer
repositório git, incluindo aninhados. Pastas pesadas ou de sistema
(`node_modules`, `Windows`, caches de assistentes de IA, bibliotecas Steam
etc.) são puladas por padrão, com lista de exclusões editável.

### ⚡ Cache de varredura (`fetchall/cache.py`)
Após a primeira varredura completa, as execuções seguintes podem usar a
varredura **rápida**: analisa direto os repositórios já conhecidos, sem
percorrer os discos de novo. Repositórios apagados são descartados na hora.

### 🔀 Sincronização em duas fases (`fetchall/syncer.py`)
Fase 1 só lê (varredura + fetch paralelo + classificação); fase 2 executa
pulls e pushes — e só roda depois que você revisa o plano e confirma.

---

## 🎯 Como Usar

Forma mais simples — abre o menu interativo onde você instala, configura e inicia:

```bash
python start_app.py
```

No menu você escolhe: **Iniciar/Rodar** (varre e sincroniza), **Instalar/Setup**
(dependências `rich` e `questionary`), **Configurar** (restringir a varredura a
pastas específicas e editar exclusões) e **Status/Sair**.

### Requisitos

- Python 3.10+ (3.12+ no Windows para detecção automática de discos)
- Git instalado e no `PATH`, com credenciais já configuradas (o programa
  nunca pede senha; repositórios sem credencial aparecem como erro de fetch)

### Configuração

Por padrão não é preciso configurar nada: com a lista de caminhos vazia, o
programa varre todos os discos locais. Preferências ficam em `config.json`
e o cache em `scan_cache.json`, ambos na raiz e ignorados pelo git por
conterem caminhos locais.

---

## 🧪 Testes

A suíte roda offline (os "remotos" são repositórios bare em pastas
temporárias) e cobre a classificação de estados, o scanner, a configuração
e o cache:

```bash
python -m unittest discover -s tests
```

---

## ⚠ Limitações

- Sincroniza apenas o branch atual de cada repositório.
- Não cria upstream automaticamente (`push -u`); branches sem upstream são
  apenas reportados.
- Repositórios novos só aparecem na varredura completa (o cache é um atalho).

---

## 🤝 Ideias para quem quiser contribuir

- Exportar o relatório final em arquivo (Markdown/JSON) para auditoria.
- Agendamento periódico da sincronização.
- Suporte a criar upstream automaticamente (`push -u`) mediante confirmação.

---

## 📄 Licença

MIT — veja [LICENSE](LICENSE).

## 👤 Autor

**Felipe Martin** — projeto pessoal para administrar dezenas de repositórios
git antes de trocar de máquina, seguindo o padrão de qualidade
*Felixo System Design*.

⭐ Se este projeto te ajudou, deixe uma estrela no GitHub!
