"""Carga do JSONL normalizado para o Postgres.

A carga é **idempotente por reconstrução**: o schema é recriado e os dados entram
do zero a cada execução. Isso é possível porque o Postgres aqui é uma cópia
analítica derivada — a fonte da verdade é o JSONL bruto em disco, que por sua vez
é derivado do PNCP. Nada se perde ao recriar, e some toda uma classe de bug de
carga incremental (linha duplicada, atualização parcial).

Conexão via variável de ambiente ``DATABASE_URL``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import psycopg

log = logging.getLogger("radar.carregar")

DIR_DADOS = Path(__file__).resolve().parent.parent / "dados"
SCHEMA = Path(__file__).resolve().parent / "schema.sql"

LOTE = 1000


def _ler_jsonl(caminho: Path) -> list[dict[str, Any]]:
    with caminho.open(encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def criar_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA.read_text(encoding="utf-8"))
    log.info("schema recriado")


def carregar_compras(conn: psycopg.Connection, itens: list[dict[str, Any]]) -> int:
    """Uma linha por compra, deduplicada a partir das linhas de item."""
    compras: dict[str, tuple] = {}
    for i in itens:
        chave = i["numero_controle_pncp"]
        if chave in compras:
            continue
        compras[chave] = (
            chave,
            i.get("orgao_cnpj"),
            i.get("orgao_nome"),
            i.get("unidade_administrativa"),
            i.get("uf"),
            i.get("municipio"),
            i.get("esfera"),
            i.get("poder"),
            None,  # modalidade_id — a fatia é toda Pregão Eletrônico
            None,
            int(i["ano"]) if i.get("ano") else None,
            None,
            i.get("data_publicacao"),
        )

    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO compra (numero_controle_pncp, orgao_cnpj, orgao_nome,
                   unidade_administrativa, uf, municipio, esfera, poder,
                   modalidade_id, modalidade_nome, ano, objeto, data_publicacao)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            list(compras.values()),
        )
    return len(compras)


def carregar_itens(conn: psycopg.Connection, itens: list[dict[str, Any]]) -> int:
    linhas = [
        (
            i["numero_controle_pncp"], i.get("numero_item"),
            i.get("descricao_original"), i["descricao_normalizada"],
            i.get("unidade_original"), i.get("unidade_normalizada"), i["chave_item"],
            i.get("material_ou_servico"), i.get("quantidade"),
            i["valor_unitario_homologado"], i.get("valor_unitario_estimado"),
            i.get("valor_total_homologado"),
            i.get("fornecedor_cnpj"), i.get("fornecedor_nome"),
            i.get("fornecedor_porte_id"), i.get("data_resultado"),
        )
        for i in itens
    ]
    with conn.cursor() as cur:
        for inicio in range(0, len(linhas), LOTE):
            cur.executemany(
                """INSERT INTO item_resultado (numero_controle_pncp, numero_item,
                       descricao_original, descricao_normalizada, unidade_original,
                       unidade_normalizada, chave_item, material_ou_servico,
                       quantidade, valor_unitario_homologado, valor_unitario_estimado,
                       valor_total_homologado, fornecedor_cnpj, fornecedor_nome,
                       fornecedor_porte_id, data_resultado)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                linhas[inicio:inicio + LOTE],
            )
    return len(linhas)


def carregar_analise(conn: psycopg.Connection, analise: dict[str, Any]) -> int:
    linhas = [
        (
            a["chave_item"], a["descricao"], a.get("descricao_exemplo"), a.get("unidade"),
            a["observacoes"], a["orgaos"], a["preco_mediano"],
            a.get("preco_minimo"), a.get("preco_maximo"), a.get("q1"), a.get("q3"),
            a.get("amplitude"), json.dumps(a["comparativo_orgaos"], ensure_ascii=False),
        )
        for a in analise["itens"]
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO analise_item (chave_item, descricao, descricao_exemplo,
                   unidade, observacoes, orgaos, preco_mediano, preco_minimo,
                   preco_maximo, q1, q3, amplitude, comparativo)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            linhas,
        )
    return len(linhas)


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Carrega o JSONL normalizado no Postgres")
    p.add_argument("--itens", type=Path, default=DIR_DADOS / "itens.jsonl")
    p.add_argument("--analise", type=Path, default=DIR_DADOS / "analise.json")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.dsn:
        raise SystemExit(
            "defina DATABASE_URL (ou passe --dsn). Para o Neon provisionado pela "
            "Vercel: vercel env pull .env.local"
        )

    itens = _ler_jsonl(args.itens)
    analise = json.loads(args.analise.read_text(encoding="utf-8"))

    # Uma transação só: ou o banco fica inteiro consistente, ou não muda nada.
    # Como recriamos o schema, uma falha no meio sem isso deixaria o banco vazio.
    with psycopg.connect(args.dsn) as conn:
        criar_schema(conn)
        n_compras = carregar_compras(conn, itens)
        n_itens = carregar_itens(conn, itens)
        n_analise = carregar_analise(conn, analise)
        conn.commit()

    log.info("carregado: %d compras, %d itens, %d análises",
             n_compras, n_itens, n_analise)


if __name__ == "__main__":
    main()
