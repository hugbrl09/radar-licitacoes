"""Testes do classificador por segmento.

Como no resto do projeto, os casos vêm de descrições reais observadas nos dados
de Tocantins — inclusive os casos que o classificador errava antes.
"""

from radar.segmentos import OUTROS, classificar, cobertura


class TestClassificacaoBasica:
    def test_alimento(self):
        assert classificar("LEGUME IN NATURA") == "Alimentação"
        assert classificar("CARNE BOVINA IN NATURA") == "Alimentação"
        assert classificar("ARROZ BENEFICIADO") == "Alimentação"

    def test_limpeza(self):
        assert classificar("AGUA SANITARIA") == "Limpeza e Higiene"
        assert classificar("DESINFETANTE") == "Limpeza e Higiene"

    def test_escritorio(self):
        assert classificar("APONTADOR LAPIS") == "Material Escolar e de Escritório"
        assert classificar("BORRACHA APAGADORA ESCRITA") == "Material Escolar e de Escritório"

    def test_ti(self):
        assert classificar("NOTEBOOK") == "TI e Eletrônicos"
        assert classificar("CABO REDE COMPUTADOR") == "TI e Eletrônicos"

    def test_eventos(self):
        # Segmento que só apareceu depois de medir a cobertura.
        assert classificar("BANHEIRO QUIMICO MEDINDO 2 30 METROS") == "Eventos e Locação"
        assert classificar("BALOES N 9 BOA QUALIDADE CORES VARIADAS") == "Eventos e Locação"


class TestDesempate:
    def test_palavra_mais_especifica_vence(self):
        """Caso real que caía em Outros antes do desempate por especificidade.

        Casa ALFINETE (escritório) e AGULHA (saúde), uma cada. É alfinete de
        mapa, não agulha hospitalar — a palavra mais longa decide.
        """
        desc = "ALFINETE TIPO AGULHA CABECA DE PREGO N 29"
        assert classificar(desc) == "Material Escolar e de Escritório"

    def test_empate_real_vira_outros(self):
        """Quando nem quantidade nem especificidade decidem, não se inventa.

        "COLA" (escritório) e "OVO" (alimentação)… não: têm tamanhos diferentes.
        Empate de verdade precisa de palavras do mesmo tamanho — "TENDA"
        (eventos) e "TINTA" (construção), 5 letras cada, uma de cada segmento.
        """
        assert classificar("TENDA COM TINTA") == OUTROS

    def test_desempate_usa_tamanho_da_palavra_e_nao_do_regex(self):
        """`MEL ` tem espaço no fim; isso não pode contar como especificidade."""
        # "CHOCOLATE" (9) é mais específica que "MEL" (3): alimentação nos dois
        # casos, mas o que se testa aqui é que o espaço não infla a pontuação.
        from radar.segmentos import pontuar
        p = pontuar("MEL DE ABELHA")
        assert p["Alimentação"][1] == len("MEL")


class TestFronteiraDePalavra:
    def test_nao_casa_dentro_de_outra_palavra(self):
        """Sem fronteira, COLA casaria em CHOCOLATE e SAL em SALGADO."""
        assert classificar("BARRA DE CHOCOLATE") == "Alimentação"

    def test_texto_vazio(self):
        assert classificar("") == OUTROS
        assert classificar("XYZABC INEXISTENTE") == OUTROS


class TestCobertura:
    def test_cobertura_conta_todos(self):
        textos = ["ARROZ BENEFICIADO", "NOTEBOOK", "ZZZZZ"]
        c = cobertura(textos)
        assert c["Alimentação"] == 1
        assert c["TI e Eletrônicos"] == 1
        assert c[OUTROS] == 1
        assert sum(c.values()) == len(textos)
