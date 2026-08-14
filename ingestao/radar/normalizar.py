"""Normalização do texto livre dos itens e achatamento do JSONL bruto.

Este é o passo onde o projeto ganha ou perde credibilidade. Comparar preço unitário
entre órgãos exige que "a mesma coisa" seja de fato reconhecida como a mesma coisa —
e o PNCP entrega descrição e unidade como texto livre, digitado por milhares de
servidores diferentes.

As transformações aqui são todas **conservadoras**: preferimos deixar de agrupar dois
itens iguais a agrupar dois itens diferentes. Um falso agrupamento vira número errado
na cara do usuário; um agrupamento perdido só reduz a amostra.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Unidades vistas nos dados reais escritas de várias formas: 'UNIDADE', 'Unidade',
# 'Unidade ' (com espaço no fim). Depois de normalizar caixa e espaço, o que sobra
# são sinônimos genuínos, resolvidos por este mapa.
SINONIMOS_UNIDADE = {
    "UN": "UNIDADE",
    "UND": "UNIDADE",
    "UNI": "UNIDADE",
    "UNID": "UNIDADE",
    "UNIDADES": "UNIDADE",
    "PC": "PECA",
    "PÇ": "PECA",
    "PECAS": "PECA",
    "CX": "CAIXA",
    "CAIXAS": "CAIXA",
    "PCT": "PACOTE",
    "KG": "QUILOGRAMA",
    "QUILO": "QUILOGRAMA",
    "G": "GRAMA",
    "L": "LITRO",
    "LT": "LITRO",
    "ML": "MILILITRO",
    "M": "METRO",
    "MT": "METRO",
    "M2": "METRO QUADRADO",
    "M3": "METRO CUBICO",
    "H": "HORA",
    "HR": "HORA",
    "HRS": "HORA",
    "HORAS": "HORA",
    "PARES": "PAR",
    "RL": "ROLO",
    "FR": "FRASCO",
    "AMP": "AMPOLA",
    "CP": "COMPRIMIDO",
    "COMP": "COMPRIMIDO",
    "SERV": "SERVICO",
    "MES": "MES",
    "MESES": "MES",
}

_NAO_ALFANUM = re.compile(r"[^A-Z0-9 ]+")
_ESPACOS = re.compile(r"\s+")


def remover_acentos(texto: str) -> str:
    """'Serviço' -> 'Servico'. Acento é fonte de divergência sem valor semântico."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def normalizar_texto(texto: str | None) -> str:
    """Caixa alta, sem acento, sem pontuação, espaços colapsados.

    Nos dados reais aparecem descrições como 'Integração de  Sistemas' — com espaço
    duplo do meio. Sem colapsar espaço, isso vira uma chave diferente de
    'Integração de Sistemas' e o agrupamento se perde silenciosamente.
    """
    if not texto:
        return ""
    t = remover_acentos(texto).upper()
    t = _NAO_ALFANUM.sub(" ", t)
    return _ESPACOS.sub(" ", t).strip()


def normalizar_unidade(unidade: str | None) -> str:
    """Reduz a unidade de medida a uma forma canônica."""
    base = normalizar_texto(unidade)
    if not base:
        return ""
    return SINONIMOS_UNIDADE.get(base, base)


def chave_item(descricao: str | None, unidade: str | None) -> str:
    """Chave de agrupamento: descrição normalizada + unidade canônica.

    A unidade entra na chave de propósito. 'CABO DE REDE' vendido por METRO e por
    UNIDADE são preços que não se comparam, e juntá-los produziria uma dispersão
    enorme e inteiramente artificial.
    """
    d = normalizar_texto(descricao)
    u = normalizar_unidade(unidade)
    return f"{d}|{u}" if d else ""


def _preco_estimado(item: dict[str, Any]) -> float | None:
    """Valor estimado, ou ``None`` quando ausente.

    ``orcamentoSigiloso`` faz a API devolver ``0``. Zero aqui **não é um preço** —
    é ausência de informação. Tratar como zero puxaria qualquer média para baixo.
    """
    if item.get("orcamentoSigiloso"):
        return None
    valor = item.get("valorUnitarioEstimado")
    if valor in (None, 0):
        return None
    return float(valor)


def achatar_compra(compra: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Transforma um registro bruto de compra em linhas planas, uma por resultado."""
    for item in compra.get("itens", []):
        if item.get("_cancelado"):
            continue

        descricao = item.get("descricao")
        unidade = item.get("unidadeMedida")
        chave = chave_item(descricao, unidade)
        if not chave:
            continue

        for resultado in item.get("_resultados") or []:
            # Um resultado cancelado depois da homologação não conta.
            if resultado.get("dataCancelamento"):
                continue

            homologado = resultado.get("valorUnitarioHomologado")
            if homologado in (None, 0):
                continue

            yield {
                "chave_item": chave,
                "descricao_original": descricao,
                "descricao_normalizada": normalizar_texto(descricao),
                "unidade_original": unidade,
                "unidade_normalizada": normalizar_unidade(unidade),
                "material_ou_servico": item.get("materialOuServico"),
                "quantidade": resultado.get("quantidadeHomologada") or item.get("quantidade"),
                "valor_unitario_homologado": float(homologado),
                "valor_unitario_estimado": _preco_estimado(item),
                "valor_total_homologado": resultado.get("valorTotalHomologado"),
                "fornecedor_cnpj": resultado.get("niFornecedor"),
                "fornecedor_nome": resultado.get("nomeRazaoSocialFornecedor"),
                "fornecedor_porte_id": resultado.get("porteFornecedorId"),
                "data_resultado": resultado.get("dataResultado"),
                "numero_controle_pncp": compra.get("numero_controle_pncp"),
                "numero_item": item.get("numeroItem"),
                "orgao_cnpj": compra.get("orgao_cnpj"),
                "orgao_nome": compra.get("orgao_nome"),
                "unidade_administrativa": compra.get("unidade_nome"),
                "uf": compra.get("uf"),
                "municipio": compra.get("municipio_nome"),
                "esfera": compra.get("esfera_nome"),
                "poder": compra.get("poder_nome"),
                "ano": compra.get("ano"),
                "data_publicacao": compra.get("data_publicacao"),
            }


def achatar_arquivo(entrada: Path, saida: Path) -> int:
    """Lê o JSONL bruto e grava o JSONL plano. Devolve quantas linhas gerou."""
    saida.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with entrada.open(encoding="utf-8") as fin, saida.open("w", encoding="utf-8") as fout:
        for linha in fin:
            linha = linha.strip()
            if not linha:
                continue
            for plano in achatar_compra(json.loads(linha)):
                fout.write(json.dumps(plano, ensure_ascii=False) + "\n")
                n += 1
    return n


def main() -> None:
    import argparse
    import logging

    dir_dados = Path(__file__).resolve().parent.parent / "dados"
    p = argparse.ArgumentParser(description="Normaliza e achata o JSONL bruto")
    p.add_argument("--entrada", type=Path, default=dir_dados / "compras.jsonl")
    p.add_argument("--saida", type=Path, default=dir_dados / "itens.jsonl")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    n = achatar_arquivo(args.entrada, args.saida)
    logging.info("%d linhas de item gravadas em %s", n, args.saida)


if __name__ == "__main__":
    main()
