"""Ingestão da fatia do PNCP para JSONL bruto.

Escreve uma linha por compra, com os itens aninhados e o resultado de cada item
junto. A camada bruta preserva o que a API devolveu, sem interpretação — filtrar e
normalizar é trabalho do passo seguinte, para que um erro de normalização possa ser
corrigido sem baixar tudo de novo.

Uso:

    uv run python -m radar.ingest --limite 50
    uv run python -m radar.ingest --uf DF --completo
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any

from radar.pncp import (
    MODALIDADE_PREGAO_ELETRONICO,
    SITUACAO_ITEM_CANCELADO,
    ClientePNCP,
    ErroPNCP,
)

log = logging.getLogger("radar.ingest")

DIR_DADOS = Path(__file__).resolve().parent.parent / "dados"


def coletar_compra(cliente: ClientePNCP, compra: dict[str, Any]) -> dict[str, Any] | None:
    """Busca itens e resultados de uma compra e monta o registro bruto."""
    cnpj = compra.get("orgao_cnpj")
    ano = compra.get("ano")
    seq = compra.get("numero_sequencial")
    if not (cnpj and ano and seq):
        return None

    try:
        itens = cliente.listar_itens(cnpj, ano, seq)
    except ErroPNCP:
        log.warning("itens indisponíveis para %s/%s/%s", cnpj, ano, seq)
        return None

    itens_coletados = []
    for item in itens:
        # Itens anulados/revogados/cancelados vêm misturados na listagem. Eles são
        # preservados no bruto, mas marcados, para que a análise possa excluí-los
        # sem precisar rebaixar os dados.
        cancelado = item.get("situacaoCompraItem") == SITUACAO_ITEM_CANCELADO

        resultados: list[dict[str, Any]] = []
        if item.get("temResultado") and not cancelado:
            try:
                resultados = cliente.listar_resultados(cnpj, ano, seq, item["numeroItem"])
            except ErroPNCP:
                log.warning("resultados indisponíveis: %s/%s/%s item %s",
                            cnpj, ano, seq, item.get("numeroItem"))

        item["_cancelado"] = cancelado
        item["_resultados"] = resultados
        itens_coletados.append(item)

    return {
        "numero_controle_pncp": compra.get("numero_controle_pncp"),
        "orgao_cnpj": cnpj,
        "orgao_id": compra.get("orgao_id"),
        "orgao_nome": compra.get("orgao_nome"),
        "unidade_nome": compra.get("unidade_nome"),
        "uf": compra.get("uf"),
        "municipio_nome": compra.get("municipio_nome"),
        "esfera_nome": compra.get("esfera_nome"),
        "poder_nome": compra.get("poder_nome"),
        "modalidade_id": compra.get("modalidade_licitacao_id"),
        "modalidade_nome": compra.get("modalidade_licitacao_nome"),
        "ano": ano,
        "numero_sequencial": seq,
        "objeto": compra.get("description"),
        "data_publicacao": compra.get("data_publicacao_pncp"),
        "situacao": compra.get("situacao_nome"),
        "cancelado": compra.get("cancelado"),
        "itens": itens_coletados,
    }


def ingerir(
    uf: str,
    modalidade: int,
    saida: Path,
    limite: int | None,
    completo: bool,
    pausa: float,
) -> None:
    saida.parent.mkdir(parents=True, exist_ok=True)
    dir_cache = DIR_DADOS / "cache"

    # Retomada: se o arquivo já existe, pulamos o que já foi gravado. Junto com o
    # cache em disco, isso torna a ingestão interrompível sem perda.
    ja_gravados: set[str] = set()
    if saida.exists():
        with saida.open(encoding="utf-8") as fh:
            for linha in fh:
                try:
                    ja_gravados.add(json.loads(linha)["numero_controle_pncp"])
                except (json.JSONDecodeError, KeyError):
                    continue
        log.info("retomando: %d compras já gravadas", len(ja_gravados))

    escritas = 0
    itens_totais = 0
    itens_com_resultado = 0

    with ClientePNCP(dir_cache) as cliente, saida.open("a", encoding="utf-8") as fh:
        fonte = (
            cliente.iterar_compras_por_orgao(uf, modalidade)
            if completo
            else cliente.iterar_compras(uf, modalidade, limite=limite)
        )

        for compra in fonte:
            if compra.get("numero_controle_pncp") in ja_gravados:
                continue

            registro = coletar_compra(cliente, compra)
            if registro is None:
                continue

            fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
            fh.flush()  # durabilidade: uma queda no meio não perde o já baixado

            escritas += 1
            itens_totais += len(registro["itens"])
            itens_com_resultado += sum(1 for i in registro["itens"] if i["_resultados"])

            if escritas % 25 == 0:
                log.info(
                    "%d compras | %d itens | %d com resultado | rede=%d cache=%d",
                    escritas, itens_totais, itens_com_resultado,
                    cliente.chamadas_rede, cliente.acertos_cache,
                )

            if limite is not None and escritas >= limite:
                break

            if pausa:
                time.sleep(pausa)

        log.info(
            "FIM — %d compras, %d itens, %d com resultado | rede=%d cache=%d",
            escritas, itens_totais, itens_com_resultado,
            cliente.chamadas_rede, cliente.acertos_cache,
        )

        # Buracos precisam ser ditos em voz alta. Uma ingestão com páginas perdidas
        # ainda é utilizável, mas quem for analisar precisa saber que ela é parcial.
        if cliente.paginas_falhadas:
            log.warning(
                "ATENÇÃO: %d página(s) não puderam ser lidas — a fatia está incompleta",
                len(cliente.paginas_falhadas),
            )
            registro_falhas = saida.with_suffix(".falhas.json")
            registro_falhas.write_text(
                json.dumps(cliente.paginas_falhadas, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.warning("detalhe em %s", registro_falhas)


def main() -> None:
    p = argparse.ArgumentParser(description="Ingestão de contratações do PNCP")
    p.add_argument("--uf", default="DF")
    p.add_argument("--modalidade", type=int, default=MODALIDADE_PREGAO_ELETRONICO)
    p.add_argument("--limite", type=int, default=None, help="máximo de compras")
    p.add_argument("--completo", action="store_true",
                   help="cobertura completa da fatia, particionando por órgão")
    p.add_argument("--saida", type=Path, default=DIR_DADOS / "compras.jsonl")
    p.add_argument("--pausa", type=float, default=0.2,
                   help="segundos entre compras, para não martelar a API")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    # httpx loga uma linha por requisição; com milhares de chamadas isso afoga o
    # progresso da ingestão.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    ingerir(args.uf, args.modalidade, args.saida, args.limite, args.completo, args.pausa)


if __name__ == "__main__":
    main()
