"""Banco SQLite local. Um arquivo só, em dados/conferente.db (fora do Git)."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from . import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS contas (
    id INTEGER PRIMARY KEY,
    escritorio TEXT NOT NULL,
    cnpj TEXT NOT NULL,
    responsavel TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    whatsapp TEXT NOT NULL DEFAULT '',
    senha_hash TEXT NOT NULL,
    plano TEXT NOT NULL DEFAULT 'teste',
    ativo_ate TEXT NOT NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS sessoes (
    token TEXT PRIMARY KEY,
    conta_id INTEGER NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    expira_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pagamentos (
    id INTEGER PRIMARY KEY,
    referencia TEXT NOT NULL UNIQUE,
    conta_id INTEGER NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    plano TEXT NOT NULL,
    valor TEXT NOT NULL,
    provedor TEXT NOT NULL,
    provedor_id TEXT,
    link TEXT,
    status TEXT NOT NULL DEFAULT 'pendente',
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    aprovado_em TEXT,
    informado_em TEXT
);
CREATE INDEX IF NOT EXISTS ix_pag_conta ON pagamentos(conta_id);
"""


def conectar() -> sqlite3.Connection:
    con = sqlite3.connect(config.caminho_banco(), timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def iniciar() -> None:
    with conectar() as con:
        con.executescript(ESQUEMA)
        colunas = {r["name"] for r in con.execute("PRAGMA table_info(pagamentos)")}
        if "informado_em" not in colunas:  # bancos criados antes do Pix manual
            con.execute("ALTER TABLE pagamentos ADD COLUMN informado_em TEXT")


@contextmanager
def transacao():
    con = conectar()
    try:
        with con:
            yield con
    finally:
        con.close()
