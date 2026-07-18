# Como contribuir

Obrigado por considerar uma contribuição ao Fetch All. Mudanças pequenas,
testáveis e conservadoras são especialmente bem-vindas: o programa trabalha
com repositórios reais e prioriza não alterar estados ambíguos.

## Preparar o ambiente

Use Python 3.10 ou mais recente e Git no `PATH`:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install -r requirements-dev.lock
```

No Windows, o interpretador do último comando fica em
`.venv\Scripts\python.exe`.

Ao atualizar dependências, edite o arquivo `.in` correspondente e regenere o
lock com hashes, sem alterar manualmente as dependências transitivas:

```bash
.venv/bin/pip-compile --generate-hashes --strip-extras \
  --output-file=requirements.lock requirements.in
.venv/bin/pip-compile --generate-hashes --strip-extras --allow-unsafe \
  --output-file=requirements-dev.lock requirements-dev.in
```

## Validar uma mudança

Antes de enviar uma contribuição, execute:

```bash
.venv/bin/python scripts/check_quality.py
```

O comando verifica compilação, lint, formatação, links locais da documentação,
testes, cobertura mínima e vulnerabilidades conhecidas nas dependências. A
suíte é offline; apenas a auditoria de dependências consulta fontes externas.
Em uma rede indisponível, use `--skip-audit` e registre essa limitação na
contribuição.

Ao corrigir um bug ou mudar uma regra de sincronização, inclua um teste de
regressão. Atualize também o README e acrescente uma entrada datada ao
`IA.md` quando comportamento, arquitetura ou comandos mudarem.

## Commits e pull requests

- Use commits coesos no formato `tipo: descrição`, como `fix: revalida estado antes do push`.
- Não inclua `config.json`, `scan_cache.json`, `passadas/`, credenciais ou caminhos locais.
- Explique o problema, a solução, a validação executada e qualquer risco restante.
