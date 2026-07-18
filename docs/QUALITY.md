# Contrato de Qualidade do Fetch All

Este documento registra como os guias aplicáveis do **Felixo System Design**
são atendidos e quais itens não pertencem ao escopo desta ferramenta CLI.

## Guias aplicáveis

### Guia mínimo

- Responsabilidades separadas entre ambiente, TUI, scanner, Git, orquestração,
  apresentação, segurança e persistência.
- Entradas externas (`config.json`, cache e saídas do Git) são validadas ou
  neutralizadas na fronteira correspondente.
- Mudanças críticas e bugs têm testes de regressão.
- README e `IA.md` são atualizados junto de mudanças observáveis.
- Dependências de execução e desenvolvimento usam versões e hashes fixos.

### Backend

- **Domínio:** `gitrepo.py` classifica estados e encapsula operações Git.
- **Serviço:** `syncer.py` monta e executa o plano, revalidando cada escrita.
- **Integração:** subprocessos Git ficam isolados e nunca usam `shell=True`.
- **Configuração:** `config.py` valida tipos e limites; não há segredo salvo.
- **Persistência:** `storage.py` faz substituição atômica; `cache.py` tolera
  corrupção descartando apenas o cache.
- **Observabilidade:** a TUI mostra falhas e `runlog.py` mantém relatório por
  passada sem registrar credenciais conhecidas.

### Menu obrigatório

`start_app.py` é a porta de entrada única e abre uma TUI com as ações
Iniciar/Rodar, Instalar/Setup, Configurar, Status e Sair. O bootstrap textual
anterior à TUI é mínimo e existe somente quando Rich/Questionary ainda não
estão disponíveis; ele oferece criar o ambiente isolado e não executa a
sincronização.

Os arquivos em `scripts/` são ferramentas internas de manutenção, sem usuário
final, e usam a exceção prevista pelo guia: não recebem menus próprios porque
são chamados pela CI ou por quem desenvolve. Eles continuam documentados,
tratam erros e têm responsabilidade única.

### README e contexto IA

- O README segue header centralizado, até cinco badges, links rápidos, índice,
  destaque, estrutura, funcionalidades, instalação, guia para iniciantes,
  limitações, segurança, licença, autoria e contribuição.
- `IA.md` preserva a linha do tempo e mantém um resumo vivo do estado atual.

## Checklist de segurança

| Risco | Tratamento |
|---|---|
| Injeção de comando | Argumentos são passados como lista; `shell=True` não é usado. |
| Exposição de credenciais | URLs, parâmetros sensíveis e tokens conhecidos são mascarados. |
| Operação destrutiva | Plano, confirmação negativa por padrão e revalidação antes da escrita. |
| Escrita parcial | Configuração e cache usam arquivo temporário único + substituição. |
| Dependência vulnerável | `pip-audit` faz parte da automação e da CI. |
| XSS, CSRF, autenticação, autorização e rate limit | Não aplicáveis: não há HTTP, navegador, contas ou API. |

## Guias fora do escopo

O projeto não possui frontend web, API HTTP, banco de dados, CPF, criptografia
educacional, scraping, integração com Notion/GitHub API ou deploy em Railway.
Por isso, os guias opcionais dessas funcionalidades não adicionam requisitos a
esta entrega. A interface de terminal é regida pelo guia de `start_app.py`.

## Critério de pronto

Execute:

```bash
.venv/bin/python scripts/check_quality.py
```

No Windows, use `.venv\Scripts\python.exe`. O comando deve concluir
compilação, consistência das dependências, lint,
formatação, links locais, testes, cobertura mínima e auditoria sem falhas. A CI
repete a validação nas versões de Python declaradas em
`.github/workflows/quality.yml`.
