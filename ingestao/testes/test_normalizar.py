"""Testes da normalização.

Os casos abaixo não são inventados: todos saíram de variações observadas nos dados
reais do PNCP durante a sondagem da API.
"""

from radar.normalizar import (
    achatar_compra,
    chave_item,
    normalizar_texto,
    normalizar_unidade,
)


class TestNormalizarTexto:
    def test_caixa_e_acento(self):
        assert normalizar_texto("Serviço") == "SERVICO"

    def test_espaco_duplo_colapsa(self):
        # Visto no PNCP: "Integração de  Sistemas" com espaço duplo do meio.
        assert normalizar_texto("Integração de  Sistemas") == "INTEGRACAO DE SISTEMAS"

    def test_espaco_nas_bordas(self):
        # Visto no PNCP: unidade "Unidade " com espaço à direita.
        assert normalizar_texto("  Cabo Rede  ") == "CABO REDE"

    def test_pontuacao_vira_espaco(self):
        assert normalizar_texto("Aparelho / Acessório") == "APARELHO ACESSORIO"

    def test_vazio_e_nulo(self):
        assert normalizar_texto("") == ""
        assert normalizar_texto(None) == ""


class TestNormalizarUnidade:
    def test_variacoes_de_unidade_convergem(self):
        # As três formas apareceram no mesmo lote de 95 itens.
        assert normalizar_unidade("UNIDADE") == "UNIDADE"
        assert normalizar_unidade("Unidade") == "UNIDADE"
        assert normalizar_unidade("Unidade ") == "UNIDADE"

    def test_sinonimos(self):
        assert normalizar_unidade("UND") == "UNIDADE"
        assert normalizar_unidade("un") == "UNIDADE"
        assert normalizar_unidade("Pares") == "PAR"
        assert normalizar_unidade("KG") == "QUILOGRAMA"

    def test_unidade_desconhecida_e_preservada(self):
        # Não inventamos mapeamento: o que não conhecemos passa normalizado e ponto.
        assert normalizar_unidade("Garrafão 20 L") == "GARRAFAO 20 L"


class TestChaveItem:
    def test_mesma_coisa_escrita_diferente_agrupa(self):
        assert chave_item("Caneleira", "Par ") == chave_item("CANELEIRA", "PARES")

    def test_unidade_diferente_nao_agrupa(self):
        """O ponto mais importante do módulo.

        Cabo vendido por metro e por unidade tem preço que não se compara. Juntar
        os dois produziria uma dispersão enorme e totalmente artificial.
        """
        assert chave_item("Cabo Rede", "METRO") != chave_item("Cabo Rede", "UNIDADE")

    def test_descricao_vazia_nao_gera_chave(self):
        assert chave_item("", "UNIDADE") == ""
        assert chave_item(None, "UNIDADE") == ""


def _compra(itens):
    return {
        "numero_controle_pncp": "00000000000000-1-000001/2025",
        "orgao_cnpj": "00000000000000",
        "orgao_nome": "ORGAO TESTE",
        "uf": "DF",
        "ano": "2025",
        "itens": itens,
    }


class TestAchatarCompra:
    def test_item_cancelado_fica_de_fora(self):
        compra = _compra([{
            "numeroItem": 1, "descricao": "Caneleira", "unidadeMedida": "Par",
            "_cancelado": True,
            "_resultados": [{"valorUnitarioHomologado": 84.97}],
        }])
        assert list(achatar_compra(compra)) == []

    def test_resultado_cancelado_fica_de_fora(self):
        compra = _compra([{
            "numeroItem": 1, "descricao": "Caneleira", "unidadeMedida": "Par",
            "_cancelado": False,
            "_resultados": [{
                "valorUnitarioHomologado": 84.97,
                "dataCancelamento": "2025-03-01",
            }],
        }])
        assert list(achatar_compra(compra)) == []

    def test_orcamento_sigiloso_vira_none_e_nao_zero(self):
        """Estimado 0 com orçamento sigiloso é ausência de dado, não preço zero."""
        compra = _compra([{
            "numeroItem": 1, "descricao": "Serviço de rede", "unidadeMedida": "UNIDADE",
            "orcamentoSigiloso": True, "valorUnitarioEstimado": 0, "_cancelado": False,
            "_resultados": [{"valorUnitarioHomologado": 170000.0}],
        }])
        linha = list(achatar_compra(compra))[0]
        assert linha["valor_unitario_estimado"] is None
        assert linha["valor_unitario_homologado"] == 170000.0

    def test_homologado_zero_e_descartado(self):
        compra = _compra([{
            "numeroItem": 1, "descricao": "Adaptador", "unidadeMedida": "UNIDADE",
            "_cancelado": False,
            "_resultados": [{"valorUnitarioHomologado": 0}],
        }])
        assert list(achatar_compra(compra)) == []

    def test_linha_completa(self):
        compra = _compra([{
            "numeroItem": 3, "descricao": "Cabo Rede Computador",
            "unidadeMedida": "Unidade ", "materialOuServico": "M",
            "valorUnitarioEstimado": 633.03, "quantidade": 10, "_cancelado": False,
            "_resultados": [{
                "valorUnitarioHomologado": 449.9,
                "quantidadeHomologada": 10,
                "niFornecedor": "11111111000191",
                "nomeRazaoSocialFornecedor": "FORNECEDOR TESTE LTDA",
            }],
        }])
        linha = list(achatar_compra(compra))[0]
        assert linha["chave_item"] == "CABO REDE COMPUTADOR|UNIDADE"
        assert linha["valor_unitario_homologado"] == 449.9
        assert linha["valor_unitario_estimado"] == 633.03
        assert linha["fornecedor_cnpj"] == "11111111000191"
        assert linha["orgao_cnpj"] == "00000000000000"
