"""Análise do v1: dispersão de preço do mesmo item entre órgãos.

O que este módulo afirma, e o que ele deliberadamente **não** afirma:

    Afirma  — "este órgão pagou X% acima da mediana paga por outros órgãos
               pelo mesmo item, na mesma unidade de medida, no mesmo período".
    Não afirma — que houve superfaturamento, irregularidade, fraude ou má-fé.

A diferença não é de estilo, é de responsabilidade. Um preço acima da mediana tem
muitas explicações legítimas: urgência, quantidade menor sem ganho de escala,
especificação técnica superior que a descrição não captura, frete para região remota.
O sistema mostra o número e a metodologia; a interpretação é de quem lê.

Estatística: usamos **mediana e intervalo interquartil**, não média e desvio padrão.
Preços de compras públicas têm cauda longa — um único contrato atípico distorce a
média e o desvio padrão, mas quase não move a mediana e o IQR.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

# Um comparativo entre poucos órgãos não é comparativo, é anedota. Estes mínimos
# são conservadores de propósito: preferimos mostrar menos itens e confiar em cada
# um deles.
MIN_ORGAOS = 3
MIN_OBSERVACOES = 5

# Cerca de Tukey. Observações fora dela não entram nas estatísticas: no PNCP elas
# quase sempre significam item diferente sob o mesmo rótulo, não preço diferente
# pela mesma coisa (ver LIMITACAO abaixo).
FATOR_CERCA = 1.5

# Acima deste coeficiente quartílico a "categoria" não é uma categoria: é um balde.
# Exemplo real da base — "Peça mecânica elétrica veículo automotivo" tem Q1 de
# R$ 0,40 e Q3 de R$ 2.419,04. Comparar preço dentro disso não significa nada.
# Estes casos não são apagados: saem da lista principal e ficam listados à parte.
LIMITE_DISPERSAO = 2.0

LIMITACAO = (
    "LIMITAÇÃO IMPORTANTE: o PNCP não publica especificação técnica do item. Os "
    "campos que a conteriam (informacaoComplementar, ncmNbsCodigo, "
    "catalogoCodigoItem) vieram vazios em 100% dos itens coletados. A descrição "
    "disponível é um rótulo de catálogo, não uma especificação: 'Monitor "
    "computador' abrange tanto um monitor de escritório quanto um painel "
    "profissional de grande porte. Portanto esta comparação mede a faixa de preço "
    "praticada dentro de uma categoria de catálogo — não o preço de um produto "
    "idêntico. Diferenças de preço podem refletir produtos genuinamente diferentes. "
    "Há ainda um efeito de seleção que agrava isso: quando um órgão escreve a "
    "especificação completa na descrição, aquele item deixa de coincidir com o de "
    "qualquer outro e não alcança o mínimo de órgãos exigido. Ou seja, o próprio "
    "agrupamento favorece as descrições mais genéricas — nas categorias "
    "publicadas aqui, 95% das descrições têm 40 caracteres ou menos."
)

METODOLOGIA = (
    "Comparação entre itens com a mesma descrição normalizada (caixa alta, sem "
    "acento e sem pontuação) e a mesma unidade de medida canônica. Considera "
    "apenas o valor unitário homologado — o preço efetivamente adjudicado — de "
    "itens não cancelados com resultado publicado. "
    "Observações fora da cerca de Tukey (1,5 × intervalo interquartil) são "
    "descartadas das estatísticas e reportadas à parte, porque nesta base elas "
    "indicam divergência de especificação com muito mais frequência do que "
    "divergência de preço. A referência é a mediana; a dispersão é medida pelo "
    "coeficiente quartílico (IQR dividido pela mediana), resistente a valores "
    "atípicos. As observações são agregadas por órgão antes da comparação, para "
    "que um órgão com muitas compras não domine a estatística. "
    "Categorias cujo coeficiente de dispersão passa de 2,0 são retiradas da lista "
    "principal e listadas à parte: nelas o rótulo funciona como balde e não como "
    "categoria, e comparar preço dentro dele não significa nada. "
    "Um valor acima da mediana não indica irregularidade: pode refletir urgência, "
    "quantidade, especificação técnica ou logística não capturadas pela descrição."
)


def _agora() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def descrever_recorte(linhas: list[dict[str, Any]]) -> dict[str, Any]:
    """Deduz o recorte a partir dos próprios dados.

    A interface lê daqui em vez de ter a UF escrita no código. Trocar de estado
    passa a ser trocar o arquivo de entrada — sem tocar no frontend.
    """
    ufs = sorted({l.get("uf") for l in linhas if l.get("uf")})

    # Distribuição por segmento sobre *todas* as linhas, não só as publicadas.
    # Vai junto no JSON porque a taxa de "Outros" é o principal indicador de
    # qualidade do classificador, e escondê-la seria vender precisão que ele
    # não tem.
    por_segmento = Counter(l.get("segmento", "Outros") for l in linhas)
    fora = por_segmento.get("Outros", 0)

    return {
        "ufs": ufs,
        "compras": len({l.get("numero_controle_pncp") for l in linhas}),
        "orgaos": len({l.get("orgao_cnpj") for l in linhas}),
        "segmentos": dict(por_segmento.most_common()),
        "cobertura_segmentos": round(100 * (len(linhas) - fora) / len(linhas), 1) if linhas else 0,
        "periodo": [
            min((l["data_publicacao"] for l in linhas if l.get("data_publicacao")), default=None),
            max((l["data_publicacao"] for l in linhas if l.get("data_publicacao")), default=None),
        ],
    }


def carregar(caminho: Path) -> list[dict[str, Any]]:
    with caminho.open(encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def _quartis(valores: Sequence[float]) -> tuple[float, float]:
    """Q1 e Q3. ``statistics.quantiles`` exige n >= 2."""
    if len(valores) < 2:
        return valores[0], valores[0]
    q = statistics.quantiles(valores, n=4, method="inclusive")
    return q[0], q[2]


def analisar_item(chave: str, linhas: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Estatísticas de um item e o desvio de cada órgão em relação à mediana.

    Roda em duas passadas: a primeira estabelece a faixa central e separa as
    observações fora da cerca; a segunda calcula as estatísticas apenas sobre o
    núcleo. Os descartados não somem — voltam no campo ``fora_da_faixa``, porque
    são justamente os casos que merecem inspeção humana.
    """
    if len({l["orgao_cnpj"] for l in linhas}) < MIN_ORGAOS or len(linhas) < MIN_OBSERVACOES:
        return None

    todos = sorted(float(l["valor_unitario_homologado"]) for l in linhas)
    q1_bruto, q3_bruto = _quartis(todos)
    iqr = q3_bruto - q1_bruto
    piso = q1_bruto - FATOR_CERCA * iqr
    teto = q3_bruto + FATOR_CERCA * iqr

    nucleo, descartados = [], []
    for l in linhas:
        alvo = nucleo if piso <= float(l["valor_unitario_homologado"]) <= teto else descartados
        alvo.append(l)

    # Depois de tirar os atípicos o item pode não sustentar mais a comparação.
    # Melhor não publicar do que publicar um comparativo entre dois órgãos.
    orgaos = {l["orgao_cnpj"] for l in nucleo}
    if len(orgaos) < MIN_ORGAOS or len(nucleo) < MIN_OBSERVACOES:
        return None

    precos = sorted(float(l["valor_unitario_homologado"]) for l in nucleo)
    mediana = statistics.median(precos)
    if mediana <= 0:
        return None
    q1, q3 = _quartis(precos)

    # Agregamos por órgão antes de comparar. Sem isso, um órgão que comprou o
    # mesmo item 40 vezes dominaria a estatística e a comparação viraria um
    # retrato dele, não do conjunto.
    por_orgao: dict[str, list[float]] = defaultdict(list)
    nomes: dict[str, str] = {}
    for l in nucleo:
        por_orgao[l["orgao_cnpj"]].append(float(l["valor_unitario_homologado"]))
        nomes[l["orgao_cnpj"]] = l.get("orgao_nome") or ""

    comparativo = []
    for cnpj, vals in por_orgao.items():
        mediana_orgao = statistics.median(vals)
        comparativo.append({
            "orgao_cnpj": cnpj,
            "orgao_nome": nomes[cnpj],
            "compras": len(vals),
            "preco_mediano": round(mediana_orgao, 2),
            "razao_vs_mediana": round(mediana_orgao / mediana, 3),
            "desvio_percentual": round((mediana_orgao / mediana - 1) * 100, 1),
        })
    comparativo.sort(key=lambda c: c["razao_vs_mediana"], reverse=True)

    exemplo = nucleo[0]
    return {
        "chave_item": chave,
        "descricao": exemplo["descricao_normalizada"],
        "descricao_exemplo": exemplo["descricao_original"],
        "unidade": exemplo["unidade_normalizada"],
        "segmento": exemplo.get("segmento", "Outros"),
        "material_ou_servico": exemplo.get("material_ou_servico"),
        "observacoes": len(nucleo),
        "observacoes_brutas": len(linhas),
        "orgaos": len(orgaos),
        "preco_mediano": round(mediana, 2),
        "preco_minimo": round(precos[0], 2),
        "preco_maximo": round(precos[-1], 2),
        "q1": round(q1, 2),
        "q3": round(q3, 2),
        # Coeficiente quartílico de dispersão: IQR sobre mediana. Este é o número
        # que ordena a lista — e não a razão máximo/mínimo, que na prática só
        # ordenava por "qual item tem o registro mais esquisito".
        "dispersao": round(iqr / mediana, 3) if mediana else None,
        "fora_da_faixa": [
            {
                "valor_unitario": round(float(l["valor_unitario_homologado"]), 2),
                "quantidade": l.get("quantidade"),
                "orgao_nome": l.get("orgao_nome"),
                "descricao_original": l.get("descricao_original"),
            }
            for l in sorted(descartados, key=lambda x: float(x["valor_unitario_homologado"]))
        ],
        "comparativo_orgaos": comparativo,
    }


def analisar(
    linhas: Iterable[dict[str, Any]],
    apenas_materiais: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Agrupa por item e devolve as análises, das mais dispersas para as menos.

    ``apenas_materiais`` existe por uma razão observada nos dados: descrições de
    serviço como "Serviços de Gerenciamento de Redes de TIC" aparecem com preços
    de R$ 6.111 a R$ 170.000 — não porque alguém pagou 27x a mais, mas porque o
    escopo contratado sob esse mesmo rótulo é completamente diferente em cada caso.
    Comparar serviços pela descrição produz dispersão falsa. Materiais têm
    descrição muito mais próxima de uma especificação real.

    Devolve ``(comparáveis, amplas_demais)``. A segunda lista existe para ser
    publicada: esconder o que foi descartado seria escolher a dedo o que confirma
    a tese.
    """
    grupos: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for linha in linhas:
        if apenas_materiais and linha.get("material_ou_servico") != "M":
            continue
        grupos[linha["chave_item"]].append(linha)

    analises = [a for chave, ls in grupos.items() if (a := analisar_item(chave, ls))]

    comparaveis, amplas = [], []
    for a in analises:
        (amplas if (a["dispersao"] or 0) > LIMITE_DISPERSAO else comparaveis).append(a)

    # A lista principal é ordenada por *força do dado* — quantos órgãos, quantas
    # compras — e não por dispersão. Ordenar por dispersão colocava no topo
    # exatamente as categorias em que o número significa menos.
    comparaveis.sort(key=lambda a: (a["orgaos"], a["observacoes"]), reverse=True)
    amplas.sort(key=lambda a: a["dispersao"] or 0, reverse=True)
    return comparaveis, amplas


def main() -> None:
    import argparse
    import logging

    dir_dados = Path(__file__).resolve().parent.parent / "dados"
    p = argparse.ArgumentParser(description="Análise de dispersão de preço")
    p.add_argument("--uf", default="TO", help="define os caminhos padrão")
    p.add_argument("--entrada", type=Path, default=None)
    p.add_argument("--saida", type=Path, default=None)
    p.add_argument("--incluir-servicos", action="store_true")
    args = p.parse_args()

    uf = args.uf.lower()
    if args.entrada is None:
        args.entrada = dir_dados / f"itens-{uf}.jsonl"
    if args.saida is None:
        args.saida = dir_dados / f"analise-{uf}.json"

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    linhas = carregar(args.entrada)
    comparaveis, amplas = analisar(linhas, apenas_materiais=not args.incluir_servicos)

    args.saida.write_text(
        json.dumps(
            {"metodologia": METODOLOGIA,
             "limitacao": LIMITACAO,
             "criterios": {"min_orgaos": MIN_ORGAOS, "min_observacoes": MIN_OBSERVACOES,
                           "fator_cerca": FATOR_CERCA,
                           "limite_dispersao": LIMITE_DISPERSAO,
                           "apenas_materiais": not args.incluir_servicos},
             "gerado_em": _agora(),
             "recorte": descrever_recorte(linhas),
             "itens": comparaveis,
             "categorias_amplas": [
                 {"descricao": a["descricao_exemplo"], "unidade": a["unidade"],
                  "observacoes": a["observacoes"], "orgaos": a["orgaos"],
                  "dispersao": a["dispersao"], "q1": a["q1"], "q3": a["q3"]}
                 for a in amplas
             ]},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    logging.info("%d linhas -> %d comparáveis + %d amplas demais em %s",
                 len(linhas), len(comparaveis), len(amplas), args.saida)

    for a in comparaveis[:12]:
        logging.info(
            "  %-42s n=%-3d órgãos=%-2d mediana=%10.2f dispersão=%.2f descartados=%d",
            a["descricao"][:42], a["observacoes"], a["orgaos"],
            a["preco_mediano"], a["dispersao"] or 0, len(a["fora_da_faixa"]),
        )


if __name__ == "__main__":
    main()
