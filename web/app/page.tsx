import Link from "next/link";
import BuscaItens from "./BuscaItens";
import {
  brl,
  carregarAnalise,
  gerarSlug,
  indicePorSlug,
  nomearRecorte,
} from "@/lib/dados";

export default function Home() {
  const analise = carregarAnalise();
  const indice = indicePorSlug();

  const slugPorChave = new Map<string, string>();
  for (const [slug, item] of indice) slugPorChave.set(item.chave_item, slug);

  const linhas = analise.itens.map((item) => ({
    slug: slugPorChave.get(item.chave_item) ?? gerarSlug(item.chave_item),
    descricao: item.descricao,
    descricaoExemplo: item.descricao_exemplo,
    unidade: item.unidade,
    observacoes: item.observacoes,
    orgaos: item.orgaos,
    precoMediano: brl(item.preco_mediano),
    faixa: `${brl(item.q1)} – ${brl(item.q3)}`,
    dispersao: item.dispersao,
    foraDaFaixa: item.fora_da_faixa.length,
  }));

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">
        Faixas de preço em compras públicas
      </h1>
      <p className="mt-3 max-w-3xl text-stone-600 dark:text-stone-300">
        Quanto os órgãos públicos de {nomearRecorte(analise.recorte.ufs)} pagaram,
        por unidade, em pregões eletrônicos registrados no PNCP. Os valores são os{" "}
        <strong className="font-medium">efetivamente homologados</strong> — o preço
        adjudicado ao fornecedor, não a estimativa feita antes da disputa.
      </p>

      {/* A limitação vem antes dos números, não depois. Quem lê a página precisa
          saber o que ela não pode afirmar antes de ver qualquer valor. */}
      <div
        role="note"
        className="mt-6 rounded-lg border-l-4 border-amber-500 bg-amber-50 p-4 text-sm
                   text-amber-950 dark:bg-amber-950/40 dark:text-amber-100"
      >
        <p className="font-medium">Antes de interpretar estes números</p>
        <p className="mt-1">
          O PNCP não publica a especificação técnica dos itens — apenas um rótulo de
          catálogo. “Condimento”, por exemplo, aparece aqui de R$ 0,02 a R$ 44,00,
          porque o mesmo rótulo cobre desde um sachê de sal até um pote de especiaria.
          Estes números descrevem a{" "}
          <strong className="font-medium">
            faixa de preço praticada dentro de uma categoria
          </strong>
          , e não o preço de um produto idêntico. Diferenças podem refletir produtos
          genuinamente diferentes.{" "}
          <Link href="/metodologia" className="underline">
            Metodologia completa
          </Link>
          .
        </p>
      </div>

      <div className="mt-10">
        <BuscaItens linhas={linhas} />
      </div>
    </>
  );
}
