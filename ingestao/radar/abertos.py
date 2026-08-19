"""Licitações com proposta em aberto — a camada rasa do projeto.

Enquanto o resto do pipeline desce ao nível de item para comparar preço, aqui
paramos no nível da compra. É deliberado: análise de item custa ~4,4 requisições
por compra, e esta visão precisa ser ampla e recente, não profunda.

O que ela responde: *o que está aberto agora, para quem vende ao governo*.

Duas armadilhas tratadas aqui:

1. **Só ``status=recebendo_proposta`` filtra.** Qualquer outro valor — inclusive
   inventado, como ``abertas`` ou ``encerrado`` — é aceito e **ignorado em
   silêncio**, devolvendo a base inteira. Um filtro que não filtra é pior que um
   filtro que falha.
2. **Credenciamento não é disputa com prazo.** É cadastro permanente, fica aberto
   por meses ou anos e responde por ~40% dos editais abertos. Misturá-lo numa
   lista de "fecha logo" daria urgência falsa, então ele vem marcado.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from radar.pncp import BASE_BUSCA, ClientePNCP, ErroPNCP
from radar.segmentos import classificar
from radar.normalizar import normalizar_texto

log = logging.getLogger("radar.abertos")

DIR_DADOS = Path(__file__).resolve().parent.parent / "dados"

# O único valor de status que a API respeita de fato.
STATUS_ABERTO = "recebendo_proposta"

# Modalidades que são cadastro permanente, não disputa com data de fechamento.
MODALIDADES_CADASTRO = {"Credenciamento", "Pré-qualificação", "Manifestação de Interesse"}

TAM_PAGINA = 100


def _link_pncp(cnpj: str | None, ano: str | None, seq: str | None) -> str | None:
    """Página do edital no portal.

    O caminho é ``/app/compras/`` — verificado, devolve 200. ``/app/editais/`` e
    ``/compras/`` não funcionam, apesar de o campo ``item_url`` da busca vir como
    ``/compras/{cnpj}/{ano}/{seq}``.
    """
    if not (cnpj and ano and seq):
        return None
    return f"https://pncp.gov.br/app/compras/{cnpj}/{ano}/{seq}"


def coletar(cliente: ClientePNCP, uf: str) -> tuple[list[dict[str, Any]], int, list[int]]:
    """Editais com proposta em aberto de uma UF.

    Devolve ``(itens, total_informado, paginas_falhadas)``. O total informado pela
    API e as páginas perdidas sobem junto porque a interface precisa poder dizer
    "esta lista está incompleta" — 300 de 450 apresentados como se fossem tudo
    seria uma mentira silenciosa.
    """
    coletados: list[dict[str, Any]] = []
    falhadas: list[int] = []
    total = 0
    pagina = 1

    while True:
        try:
            lote = cliente._get(BASE_BUSCA, {
                "tipos_documento": "edital",
                "status": STATUS_ABERTO,
                "ufs": uf,
                "pagina": pagina,
                "tam_pagina": TAM_PAGINA,
            })
        except ErroPNCP:
            log.error("página %d falhou", pagina)
            falhadas.append(pagina)
            # Uma página perdida não encerra a varredura: as seguintes ainda
            # valem. Só paramos quando a API devolve página vazia.
            if len(falhadas) >= 3:
                log.error("3 páginas falharam — interrompendo")
                break
            pagina += 1
            continue

        itens = lote.get("items") or []
        if not itens:
            break

        if pagina == 1:
            total = lote.get("total", 0)
            log.info("%s: %d editais abertos segundo a API", uf, total)

        coletados.extend(itens)
        pagina += 1

    return coletados, total, falhadas


def montar(bruto: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Converte o retorno da busca no registro que a interface consome."""
    saida = []
    for e in bruto:
        objeto = e.get("description") or ""
        modalidade = e.get("modalidade_licitacao_nome") or ""

        saida.append({
            "numero_controle_pncp": e.get("numero_controle_pncp"),
            "objeto": objeto,
            "segmento": classificar(normalizar_texto(objeto)),
            "orgao_nome": e.get("orgao_nome"),
            "orgao_cnpj": e.get("orgao_cnpj"),
            "unidade_nome": e.get("unidade_nome"),
            "municipio": e.get("municipio_nome"),
            "uf": e.get("uf"),
            "modalidade": modalidade,
            # Marcado, não filtrado: quem procura credenciamento quer achá-lo.
            "cadastro_permanente": modalidade in MODALIDADES_CADASTRO,
            "valor_global": e.get("valor_global"),
            "data_publicacao": e.get("data_publicacao_pncp"),
            # Data absoluta de propósito. O "faltam N dias" é calculado no
            # navegador — se fosse gravado aqui, envelheceria junto com o build.
            "data_fim_proposta": e.get("data_fim_vigencia"),
            "link": _link_pncp(e.get("orgao_cnpj"), e.get("ano"), e.get("numero_sequencial")),
        })
    return saida


def main() -> None:
    import argparse
    from datetime import datetime, timezone

    p = argparse.ArgumentParser(description="Coleta editais com proposta em aberto")
    p.add_argument("--uf", default="TO")
    p.add_argument("--saida", type=Path, default=None)
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
                        datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    uf = args.uf.upper()
    saida = args.saida or DIR_DADOS / f"abertos-{uf.lower()}.json"

    # Sem cache: uma lista de "aberto agora" servida de cache é uma lista errada.
    with ClientePNCP(DIR_DADOS / "cache", usar_cache=False) as cliente:
        bruto, total_api, falhadas = coletar(cliente, uf)

    editais = montar(bruto)
    com_prazo = sum(1 for e in editais if not e["cadastro_permanente"])

    saida.write_text(json.dumps({
        "coletado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "uf": uf,
        "total": len(editais),
        # Quanto a API disse existir, contra quanto conseguimos ler.
        "total_informado_api": total_api,
        "completo": not falhadas and len(editais) >= total_api,
        "paginas_perdidas": falhadas,
        "com_prazo": com_prazo,
        "cadastro_permanente": len(editais) - com_prazo,
        "editais": editais,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("%d de %d editais (%d com prazo, %d cadastro permanente) -> %s",
             len(editais), total_api, com_prazo, len(editais) - com_prazo, saida)
    if falhadas:
        log.warning("ATENÇÃO: %d página(s) perdida(s) — a lista está incompleta",
                    len(falhadas))


if __name__ == "__main__":
    main()
