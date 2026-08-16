"""Classificação de itens em segmentos de mercado.

Serve à leitura de inteligência de mercado: um fornecedor quer saber "onde está
sendo comprado o que eu vendo", e para isso a descrição solta não basta — é
preciso agrupar em segmentos.

**O que este módulo é, honestamente:** um dicionário de palavras-chave. Não é
classificador estatístico, não aprende e vai errar em casos ambíguos. Foi
escolhido assim de propósito:

* é **auditável** — dá para ler a regra que classificou cada item, o que um
  modelo treinado não oferece de graça;
* é **corrigível** — errou, adiciona-se a palavra;
* não exige rótulo de treino, que não existe nesta base.

O vocabulário abaixo não foi inventado: saiu da contagem de frequência das
descrições reais de Tocantins. Itens que não casam com nada ficam em
``OUTROS`` — categoria explícita, nunca escondida num segmento qualquer.
"""

from __future__ import annotations

import re
from collections import Counter

OUTROS = "Outros"

# Ordem não importa: a classificação é por pontuação, não por primeira
# ocorrência. Duas palavras do mesmo segmento valem mais que uma de outro.
SEGMENTOS: dict[str, list[str]] = {
    "Alimentação": [
        "ALIMENT", "LEGUME", "FRUTA", "VERDURA", "CARNE", "BOVINA", "FRANGO",
        "PEIXE", "ARROZ", "FEIJAO", "ACUCAR", "CAFE", "LEITE", "PAO", "BISCOITO",
        "MACARRAO", "FARINHA", "OLEO VEGETAL", "MARGARINA", "MANTEIGA", "QUEIJO",
        "OVO", "POLPA", "SUCO", "REFRIGERANTE", "TEMPERO", "CONDIMENTO", "SAL",
        "FRIOS", "IOGURTE", "CEREAL", "MERENDA", "HORTIFRUTI", "IN NATURA",
        "COMESTIVEL", "GENERO ALIMENTICIO",
        # Itens específicos que apareceram nos dados e escapavam dos termos gerais.
        "ALHO", "CEBOLA", "BATATA", "TOMATE", "CENOURA", "ABOBORA", "BETERRABA",
        "REPOLHO", "ALFACE", "PIMENTAO", "CHUCHU", "MANDIOCA", "INHAME",
        "BANANA", "MACA", "LARANJA", "MELANCIA", "MAMAO", "ABACAXI", "MANGA",
        "MELAO", "UVA", "LIMAO", "GOIABA", "MARACUJA", "ACEROLA", "CAJU",
        "CHOCOLATE", "AMENDOIM", "TAPIOCA", "MILHO", "AVEIA", "GELATINA",
        "VINAGRE", "MEL ", "ACHOCOLATADO", "PRESUNTO", "MORTADELA", "SALSICHA",
        "LINGUICA", "REQUEIJAO", "CREME DE LEITE", "LEITE CONDENSADO", "FUBA",
        "COLORAU", "CANELA", "ORE GANO", "COLORIFICO", "EXTRATO DE TOMATE",
        "SARDINHA", "ATUM", "BOLACHA", "ROSQUINHA", "TORRADA", "PIPOCA",
    ],
    "Limpeza e Higiene": [
        "LIMPEZA", "DETERGENTE", "DESINFETANTE", "SANITARIA", "SABAO", "SABONETE",
        "ALVEJANTE", "AGUA SANITARIA", "VASSOURA", "RODO", "ESPONJA", "PANO DE CHAO",
        "PAPEL HIGIENICO", "PAPEL TOALHA", "HIGIENE", "CERA", "LUSTRA", "AMACIANTE",
        "ALCOOL ETILICO", "ALCOOL GEL", "BALDE", "BACIA", "LIXEIRA", "SACO DE LIXO",
    ],
    "Saúde e Medicamentos": [
        "MEDICAMENTO", "FARMAC", "COMPRIMIDO", "AMPOLA", "SERINGA", "AGULHA",
        "LUVA CIRURGICA", "GAZE", "ATADURA", "SORO", "VACINA", "ODONTO", "DENTAL",
        "HOSPITALAR", "CIRURGICO", "CURATIVO", "ANTIBIOTICO", "ANALGESICO",
        "ACIDO FOLICO", "DIPIRONA", "INSULINA", "REAGENTE", "LABORATORIO",
        "ACIDO ACETILSALICILICO", "PARACETAMOL", "IBUPROFENO", "AMOXICILINA",
        "OMEPRAZOL", "METFORMINA", "LOSARTANA", "CAPTOPRIL", "SIMVASTATINA",
        "PRONTUARIO", "ESTETOSCOPIO", "TERMOMETRO CLINICO", "ESFIGMO",
        "CATETER", "SONDA", "ESPARADRAPO", "ALGODAO HIDROFILO", "ABAIXADOR",
    ],
    "Material Escolar e de Escritório": [
        "CANETA", "LAPIS", "APONTADOR", "BORRACHA APAGADORA", "CADERNO", "PAPEL A4",
        "SULFITE", "GRAMPEADOR", "CLIPS", "PASTA", "ENVELOPE", "COLA", "TESOURA",
        "REGUA", "MARCADOR", "APAGADOR", "QUADRO BRANCO", "GIZ", "MOCHILA",
        "ESCOLAR", "EXPEDIENTE", "IMPRESSO", "ALFINETE", "TINTA PARA IMPRESSORA",
        "CARTUCHO", "TONER", "BARBANTE", "CARIMBO", "BLOCO", "FITA ADESIVA",
        "PERFURADOR", "PINCEL ATOMICO", "PAPEL CARTAO", "CARTOLINA", "ETIQUETA",
        "LIVRO", "AGENDA", "CALCULADORA", "PRANCHETA", "PERCEVEJO", "ELASTICO",
        "APAGADOR QUADRO", "CRACHA", "CANETINHA", "GIZ DE CERA", "MASSA DE MODELAR",
        "TINTA GUACHE", "PAPEL CREPOM", "EVA ",
    ],
    "Mobiliário e Eletrodomésticos": [
        "CADEIRA", "MESA", "ARMARIO", "ESTANTE", "SOFA", "POLTRONA", "GAVETEIRO",
        "LONGARINA", "BIRO", "COLCHAO", "CAMA", "GELADEIRA", "FRIGOBAR", "FOGAO",
        "MICROONDAS", "BEBEDOURO", "VENTILADOR", "AR CONDICIONADO", "LIQUIDIFICADOR",
        "FREEZER", "MOBILIARIO",
    ],
    "TI e Eletrônicos": [
        "COMPUTADOR", "NOTEBOOK", "MONITOR", "IMPRESSORA", "SCANNER", "TECLADO",
        "MOUSE", "SWITCH", "ROTEADOR", "SERVIDOR", "SOFTWARE", "LICENCA",
        "CABO REDE", "NOBREAK", "PROJETOR", "TABLET", "CELULAR", "TELEVISOR",
        "CAMERA", "HD ", "SSD", "MEMORIA RAM", "INFORMATICA", "ELETRONIC",
    ],
    "Construção e Manutenção": [
        "CIMENTO", "AREIA", "BRITA", "TIJOLO", "TELHA", "MADEIRA", "PREGO",
        "PARAFUSO", "TINTA", "ARGAMASSA", "HIDRAULIC", "ELETRIC", "LAMPADA",
        "FIO ", "DISJUNTOR", "TUBO", "CONEXAO", "TORNEIRA", "OBRA", "REFORMA",
        "PREDIAL", "CONSTRUCAO", "FERRAMENTA", "ABRACADEIRA",
    ],
    "Veículos e Combustível": [
        "VEICULO", "AUTOMOTIVO", "PNEU", "OLEO LUBRIFICANTE", "GASOLINA", "DIESEL",
        "ETANOL", "COMBUSTIVEL", "PECA MECANICA", "BATERIA AUTOMOTIVA", "FILTRO DE",
        "AMORTECEDOR", "FROTA", "MOTOCICLETA", "CAMINHAO", "ONIBUS",
        "ARLA", "PASTILHA DE FREIO", "CORREIA", "RADIADOR", "EMBREAGEM",
        "PARABRISA", "RETROVISOR", "CAMBIO", "ALTERNADOR", "VELA DE IGNICAO",
    ],
    "Uniformes e EPI": [
        "UNIFORME", "CAMISA", "CAMISETA", "CALCA", "JALECO", "AVENTAL", "BOTA",
        "LUVA", "CAPACETE", "PROTETOR AURICULAR", "OCULOS DE PROTECAO", "EPI",
        "VESTUARIO", "TOUCA", "MASCARA", "COLETE", "FARDAMENTO",
    ],
    "Serviços": [
        "PRESTACAO DE SERVICO", "SERVICO ESPECIALIZADO", "MANUTENCAO",
        "CONSULTORIA", "ASSESSORIA", "TRANSPORTE", "INSTALACAO", "TREINAMENTO",
        "CAPACITACAO", "SEGURANCA E VIGILANCIA", "VIGILANCIA", "PORTARIA",
        "TERCEIRIZACAO", "MAO DE OBRA", "SEGURO", "PUBLICIDADE",
    ],
    # Segmento descoberto ao medir a cobertura: locação de estrutura para evento
    # é volume relevante em compra municipal e não cabia em nenhum outro.
    "Eventos e Locação": [
        "EVENTO", "LOCACAO", "BANHEIRO QUIMICO", "CAMARIM", "PALCO", "TENDA",
        "SONORIZACAO", "ILUMINACAO", "BALAO", "BALOES", "DECORACAO", "BUFFET",
        "COFFEE BREAK", "ARQUIBANCADA", "GRADIL", "TABLADO", "TOLDO",
        "BRINQUEDO INFLAVEL", "FOGOS DE ARTIFICIO", "TROFEU", "MEDALHA",
        "FESTA", "CENOGRAF",
    ],
}

# Pré-compila com fronteira de palavra à esquerda. Sem isso "COLA" casaria dentro
# de "CHOCOLATE" e "SAL" dentro de "SALGADO".
#
# Guardamos a palavra ao lado do padrão porque o desempate mede a especificidade
# pelo tamanho da *palavra*, não do regex: o prefixo `\b`, os escapes e espaços
# no fim ("MEL ") inflariam o padrão e distorceriam a comparação.
_PADROES: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    seg: [(p.strip(), re.compile(r"\b" + re.escape(p))) for p in palavras]
    for seg, palavras in SEGMENTOS.items()
}


def pontuar(texto: str) -> dict[str, tuple[int, int]]:
    """Para cada segmento: ``(nº de palavras casadas, tamanho da maior casada)``.

    O segundo número é o critério de desempate, e existe por um caso real:
    "ALFINETE TIPO AGULHA CABEÇA DE PREGO" casa `ALFINETE` (escritório) e
    `AGULHA` (saúde), uma cada. É alfinete de mapa, não agulha hospitalar — e a
    palavra mais longa é a mais específica, então ela decide.
    """
    if not texto:
        return {}
    pontos: dict[str, tuple[int, int]] = {}
    for seg, padroes in _PADROES.items():
        casadas = [palavra for palavra, p in padroes if p.search(texto)]
        if casadas:
            pontos[seg] = (len(casadas), max(len(c) for c in casadas))
    return pontos


def classificar(texto: str) -> str:
    """Segmento mais bem pontuado, ou ``OUTROS``.

    Só devolve ``OUTROS`` quando nada casou, ou quando dois segmentos empatam
    em quantidade **e** em especificidade — aí dizer qualquer um dos dois seria
    inventar precisão que o texto não dá.
    """
    pontos = pontuar(texto)
    if not pontos:
        return OUTROS

    ordenado = sorted(pontos.items(), key=lambda kv: kv[1], reverse=True)
    if len(ordenado) > 1 and ordenado[0][1] == ordenado[1][1]:
        return OUTROS
    return ordenado[0][0]


def cobertura(textos: list[str]) -> Counter[str]:
    """Distribuição dos segmentos. Serve para medir quanto caiu em ``OUTROS``."""
    return Counter(classificar(t) for t in textos)
