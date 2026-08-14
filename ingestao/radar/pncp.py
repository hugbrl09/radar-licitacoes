"""Único ponto de acesso à rede do projeto.

Todo o resto do sistema fala com o PNCP através daqui. Isso é deliberado: a API de
busca que usamos é interna e não documentada (ver DECISIONS.md §4), então ela pode
mudar sem aviso. Concentrando o acesso num módulo só, trocar a fonte de dados vira
uma mudança local em vez de uma caçada pelo repositório.

São duas APIs distintas:

  * ``/api/search/``   descobre *quais* compras existem (rápida, filtrável por UF)
  * ``/api/pncp/v1/``  traz itens e preços de *uma* compra específica
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

BASE_BUSCA = "https://pncp.gov.br/api/search/"
BASE_DETALHE = "https://pncp.gov.br/api/pncp/v1"

# A API de busca corta a conexão para clientes que não parecem browser. Não é
# autenticação — é filtro de tráfego. Sem estes headers a requisição falha com
# "conexão fechada" em vez de um status HTTP.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://pncp.gov.br/app/editais",
}

# A API do PNCP é intermitente: 503, 504 e conexão cortada no meio da resposta são
# rotina, não exceção. Toda chamada passa por retry com backoff exponencial e jitter.
# 8 tentativas com teto de 30s dão ~2 minutos de paciência por requisição, o que na
# prática atravessa as janelas de instabilidade observadas.
TENTATIVAS = 8
ESPERA_BASE = 2.0
ESPERA_MAXIMA = 30.0
TIMEOUT = httpx.Timeout(90.0, connect=15.0)

MODALIDADE_PREGAO_ELETRONICO = 6

# A busca é servida por Elasticsearch com max_result_window=10000: além desse
# offset ela falha de forma determinística, e repetir não adianta. Contornado
# particionando por órgão (DECISIONS.md §8).
OFFSET_MAXIMO = 10_000
TAM_PAGINA = 50

# Falhas isoladas são soluço da API e a varredura segue em frente; várias seguidas
# significam serviço fora do ar, quando insistir só castiga um sistema em apuros.
MAX_FALHAS_SEGUIDAS = 3

# situacaoCompraItem == 3 significa Anulado/Revogado/Cancelado. Estes itens vêm
# misturados na listagem normal e precisam sair antes de qualquer média.
SITUACAO_ITEM_CANCELADO = 3


class ErroPNCP(RuntimeError):
    """A API não respondeu depois de todas as tentativas."""


class ClientePNCP:
    """Cliente HTTP com cache em disco e retry.

    O cache não é otimização — é o que torna a ingestão possível. Como a API cai
    com frequência, uma execução interrompida na metade não pode significar
    recomeçar do zero. Respostas ficam em disco e uma reexecução só bate na rede
    para o que ainda falta.
    """

    def __init__(self, dir_cache: Path | str, usar_cache: bool = True) -> None:
        self.dir_cache = Path(dir_cache)
        self.dir_cache.mkdir(parents=True, exist_ok=True)
        self.usar_cache = usar_cache
        self._cliente = httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
        self.acertos_cache = 0
        self.chamadas_rede = 0
        # Páginas que falharam mesmo depois de todas as tentativas. Uma página
        # perdida é um *buraco* nos dados, não apenas menos registros — por isso
        # fica registrada em vez de ser engolida em silêncio.
        self.paginas_falhadas: list[dict[str, Any]] = []

    def __enter__(self) -> "ClientePNCP":
        return self

    def __exit__(self, *_: object) -> None:
        self.fechar()

    def fechar(self) -> None:
        self._cliente.close()

    # ------------------------------------------------------------------ cache

    def _caminho_cache(self, url: str, params: dict[str, Any] | None) -> Path:
        chave = url + "?" + json.dumps(params or {}, sort_keys=True)
        digest = hashlib.sha256(chave.encode()).hexdigest()[:20]
        # Subdiretório de 2 caracteres evita milhares de arquivos numa pasta só,
        # o que degrada o filesystem no Windows.
        pasta = self.dir_cache / digest[:2]
        pasta.mkdir(exist_ok=True)
        return pasta / f"{digest}.json"

    # -------------------------------------------------------------------- get

    def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        caminho = self._caminho_cache(url, params)

        if self.usar_cache and caminho.exists():
            self.acertos_cache += 1
            return json.loads(caminho.read_text(encoding="utf-8"))

        dados = self._get_com_retry(url, params)
        caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        return dados

    def _get_com_retry(self, url: str, params: dict[str, Any] | None) -> Any:
        ultimo_erro: Exception | None = None

        for tentativa in range(1, TENTATIVAS + 1):
            try:
                self.chamadas_rede += 1
                resposta = self._cliente.get(url, params=params)

                # 404 é resposta legítima: a compra existe no índice de busca mas
                # não tem itens publicados. Não adianta tentar de novo.
                if resposta.status_code == 404:
                    return None

                resposta.raise_for_status()
                return resposta.json()

            except (httpx.HTTPStatusError, httpx.TransportError, json.JSONDecodeError) as erro:
                ultimo_erro = erro
                if tentativa == TENTATIVAS:
                    break
                # Backoff exponencial com jitter: sem o jitter, várias requisições
                # que falharam juntas voltariam juntas e derrubariam de novo. O teto
                # evita que as últimas tentativas virem esperas de vários minutos.
                espera = min(ESPERA_BASE * (2 ** (tentativa - 1)), ESPERA_MAXIMA)
                espera += random.uniform(0, 1)
                log.warning(
                    "tentativa %d/%d falhou (%s) — aguardando %.1fs",
                    tentativa, TENTATIVAS, type(erro).__name__, espera,
                )
                time.sleep(espera)

        raise ErroPNCP(f"falha após {TENTATIVAS} tentativas: {url} {params}") from ultimo_erro

    # ------------------------------------------------------------------ busca

    def buscar_compras(
        self,
        uf: str,
        modalidade: int,
        pagina: int = 1,
        tam_pagina: int = TAM_PAGINA,
        orgao_id: str | None = None,
    ) -> dict[str, Any]:
        """Uma página do índice de busca. Devolve ``{items, total}``.

        Note o que *não* é enviado: ``ordenacao``. O valor ``-data`` é aceito e não
        ordena nada; o default devolve ordem de indexação crescente, que é estável
        para paginar porque documentos novos entram no fim (DECISIONS.md §9).
        """
        params: dict[str, Any] = {
            "tipos_documento": "edital",
            "status": "todos",
            "ufs": uf,            # plural! "uf" no singular derruba a conexão
            "modalidades": modalidade,
            "pagina": pagina,
            "tam_pagina": tam_pagina,
        }
        if orgao_id is not None:
            # Aceita o orgao_id interno (numérico), não o CNPJ. Passar CNPJ aqui
            # devolve zero resultados sem erro nenhum.
            params["orgaos"] = orgao_id
        return self._get(BASE_BUSCA, params)

    def iterar_compras(
        self,
        uf: str,
        modalidade: int,
        limite: int | None = None,
        tam_pagina: int = TAM_PAGINA,
        orgao_id: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Percorre as páginas da busca, respeitando o teto de offset da API.

        Para de paginar antes de ``OFFSET_MAXIMO`` porque além dele a API falha de
        forma determinística. Varrer mais que isso exige particionar por órgão —
        ver :func:`iterar_compras_por_orgao`.
        """
        vistos = 0
        pagina = 1
        falhas_seguidas = 0

        while True:
            if (pagina - 1) * tam_pagina >= OFFSET_MAXIMO:
                log.warning(
                    "teto de %d resultados atingido (uf=%s orgao=%s) — "
                    "particione por órgão para cobertura completa",
                    OFFSET_MAXIMO, uf, orgao_id,
                )
                return

            # Uma página que não volta nem depois de todas as tentativas não pode
            # derrubar a ingestão inteira: o resto da fatia continua sendo útil.
            # Registramos o buraco e seguimos.
            try:
                lote = self.buscar_compras(uf, modalidade, pagina, tam_pagina, orgao_id)
                falhas_seguidas = 0
            except ErroPNCP:
                self.paginas_falhadas.append(
                    {"uf": uf, "modalidade": modalidade, "pagina": pagina, "orgao_id": orgao_id}
                )
                falhas_seguidas += 1
                log.error("página %d falhou definitivamente (buraco registrado)", pagina)
                # Várias falhas seguidas significam API fora do ar, não soluço.
                # Insistir só gasta tempo e castiga um serviço já em dificuldade.
                if falhas_seguidas >= MAX_FALHAS_SEGUIDAS:
                    log.error("%d páginas seguidas falharam — interrompendo a varredura",
                              falhas_seguidas)
                    return
                pagina += 1
                continue

            itens = lote.get("items") or []
            if not itens:
                return

            for compra in itens:
                yield compra
                vistos += 1
                if limite is not None and vistos >= limite:
                    return

            pagina += 1

    def descobrir_orgaos(
        self, uf: str, modalidade: int, tam_pagina: int = TAM_PAGINA
    ) -> dict[str, str]:
        """Varre a janela visível do índice coletando ``{orgao_id: nome}``.

        Primeiro passo da estratégia de particionamento: a janela de 10.000 não
        cobre todas as *compras*, mas cobre praticamente todos os *órgãos*, porque
        cada órgão aparece muitas vezes.
        """
        orgaos: dict[str, str] = {}
        for compra in self.iterar_compras(uf, modalidade, tam_pagina=tam_pagina):
            oid = compra.get("orgao_id")
            if oid:
                orgaos[str(oid)] = compra.get("orgao_nome") or ""
        return orgaos

    def iterar_compras_por_orgao(
        self, uf: str, modalidade: int, tam_pagina: int = TAM_PAGINA
    ) -> Iterator[dict[str, Any]]:
        """Cobertura completa da fatia, contornando o teto de offset.

        Descobre os órgãos e depois pagina dentro de cada um. Nenhum órgão sozinho
        chega perto de 10.000 compras, então cada partição é varrida por inteiro.
        Deduplica por ``numero_controle_pncp`` porque as duas passadas se sobrepõem.
        """
        orgaos = self.descobrir_orgaos(uf, modalidade, tam_pagina)
        log.info("descobertos %d órgãos em %s", len(orgaos), uf)

        vistos: set[str] = set()
        for i, (oid, nome) in enumerate(sorted(orgaos.items()), start=1):
            log.info("[%d/%d] órgão %s — %s", i, len(orgaos), oid, nome[:50])
            for compra in self.iterar_compras(
                uf, modalidade, tam_pagina=tam_pagina, orgao_id=oid
            ):
                chave = compra.get("numero_controle_pncp") or compra.get("id")
                if chave in vistos:
                    continue
                vistos.add(chave)
                yield compra

    # ---------------------------------------------------------------- detalhe

    def listar_itens(self, cnpj: str, ano: int | str, sequencial: int | str) -> list[dict[str, Any]]:
        """Itens de uma compra, com valor *estimado*."""
        url = f"{BASE_DETALHE}/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens"
        return self._get(url) or []

    def listar_resultados(
        self, cnpj: str, ano: int | str, sequencial: int | str, numero_item: int
    ) -> list[dict[str, Any]]:
        """Resultados de um item: preço *homologado* e fornecedor vencedor.

        É daqui que sai o número que a análise compara — o valor efetivamente
        adjudicado, não a estimativa do órgão (DECISIONS.md §5).
        """
        url = f"{BASE_DETALHE}/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens/{numero_item}/resultados"
        return self._get(url) or []
