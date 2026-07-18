"""Redação de dados sensíveis antes de exibir ou persistir saídas externas."""

from __future__ import annotations

import re

_URL_CREDENTIALS = re.compile(r"(?i)\b(https?://)[^/@\s]+@")
_SECRET_PARAMETERS = re.compile(
    r"(?i)\b(access_token|auth_token|oauth_token|password|passwd|token)=([^&\s]+)"
)
_KNOWN_TOKEN_FORMATS = re.compile(
    r"\b(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})\b"
)


def redact_sensitive_text(text: str) -> str:
    """Mascara credenciais comuns em URLs, parâmetros e tokens do GitHub."""
    redacted = _URL_CREDENTIALS.sub(r"\1***@", text)
    redacted = _SECRET_PARAMETERS.sub(r"\1=***", redacted)
    return _KNOWN_TOKEN_FORMATS.sub("***", redacted)
