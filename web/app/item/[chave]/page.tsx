import Link from "next/link";
import { notFound } from "next/navigation";
import { brl, indicePorSlug, numero } from "@/lib/dados";

export function generateStaticParams() {
  return [...indicePorSlug().keys()].map((chave) => ({ chave }));
}

export default async function ItemPage({
  params,
}: {
  params: Promise<{ chave: string }>;
}) {
  const { chave } = await params;
  const item = indicePorSlug().get(chave);
  if (!item) notFound();

  const maior = item.comparativo_orgaos[0];
  const menor = item.comparativo_orgaos[item.comparativo_orgaos.length - 1];

  return (
    <>
      <Link
        href="/"
        className="text-sm text-stone-500 hover:underline dark:text-stone-400"
      >
        ← todos os itens
      </Link>

      <h1 className="mt-4 text-2xl font-semibold tracking-tight">
        {item.descricao_exemplo}
      </h1>
      <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">
        preço por {item.unidade.toLowerCase()} · {numero(item.observacoes)} compras
        homologadas em {item.orgaos} órgãos
      </p>

      <dl className="mt-8 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-stone-200 bg-stone-200 sm:grid-cols-4 dark:border-stone-800 dark:bg-stone-800">
        {[
          ["Mediana", brl(item.preco_mediano)],
          ["Faixa central (Q1–Q3)", `${brl(item.q1)} – ${brl(item.q3)}`],
          ["Menor", brl(item.preco_minimo)],
          ["Maior", brl(item.preco_maximo)],
        ].map(([rotulo, valor]) => (
          <div key={rotulo} className="bg-white p-4 dark:bg-stone-900">
            <dt className="text-xs uppercase tracking-wide text-stone-500 dark:text-stone-400">
              {rotulo}
            </dt>
            <dd className="mt-1 font-medium tabular-nums">{valor}</dd>
          </div>
        ))}
      </dl>

      <h2 className="mt-12 text-lg font-semibold">Comparação entre órgãos</h2>
      <p className="mt-2 max-w-3xl text-sm text-stone-600 dark:text-stone-300">
        Cada órgão entra uma vez, pelo seu preço mediano — assim um órgão que comprou
        muitas vezes não domina a estatística. O desvio é medido contra a mediana do
        conjunto.{" "}
        <strong className="font-medium">
          Um valor acima da mediana não indica irregularidade
        </strong>
        : pode refletir urgência, quantidade menor, especificação superior ou
        logística que a descrição não captura.
      </p>

      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[36rem] text-sm">
          <thead>
            <tr className="border-b border-stone-300 text-left dark:border-stone-700">
              <th className="py-2 pr-4 font-medium">Órgão</th>
              <th className="py-2 pr-4 text-right font-medium">Compras</th>
              <th className="py-2 pr-4 text-right font-medium">Preço mediano</th>
              <th className="py-2 text-right font-medium">vs. mediana</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-200 dark:divide-stone-800">
            {item.comparativo_orgaos.map((o) => (
              <tr key={o.orgao_cnpj}>
                <td className="py-3 pr-4">
                  <span className="block">{o.orgao_nome}</span>
                  <span className="text-xs text-stone-500 dark:text-stone-400">
                    CNPJ {o.orgao_cnpj}
                  </span>
                </td>
                <td className="py-3 pr-4 text-right tabular-nums">{o.compras}</td>
                <td className="py-3 pr-4 text-right tabular-nums">
                  {brl(o.preco_mediano)}
                </td>
                <td className="py-3 text-right tabular-nums">
                  {o.desvio_percentual > 0 ? "+" : ""}
                  {o.desvio_percentual.toLocaleString("pt-BR", {
                    minimumFractionDigits: 1,
                    maximumFractionDigits: 1,
                  })}
                  %
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {maior && menor && maior !== menor && (
        <p className="mt-4 text-sm text-stone-600 dark:text-stone-300">
          Neste conjunto, o preço mediano de {maior.orgao_nome} é{" "}
          {(maior.preco_mediano / menor.preco_mediano).toLocaleString("pt-BR", {
            maximumFractionDigits: 1,
          })}
          × o de {menor.orgao_nome}. A diferença é um ponto de partida para
          investigação, não uma conclusão.
        </p>
      )}

      {item.fora_da_faixa.length > 0 && (
        <section className="mt-12">
          <h2 className="text-lg font-semibold">Registros fora da faixa</h2>
          <p className="mt-2 max-w-3xl text-sm text-stone-600 dark:text-stone-300">
            {item.fora_da_faixa.length > 1
              ? `Estes ${item.fora_da_faixa.length} registros ficaram`
              : "Este registro ficou"}{" "}
            fora da cerca estatística e{" "}
            <strong className="font-medium">não</strong>{" "}
            {item.fora_da_faixa.length > 1 ? "entram" : "entra"} nos números acima. Nesta
            base, um valor muito distante costuma indicar{" "}
            <strong className="font-medium">
              item diferente sob o mesmo rótulo
            </strong>{" "}
            — e não preço diferente pela mesma coisa. Ficam listados para inspeção.
          </p>
          <ul className="mt-4 divide-y divide-stone-200 text-sm dark:divide-stone-800">
            {item.fora_da_faixa.map((f, i) => (
              <li key={i} className="flex flex-wrap gap-x-4 py-3">
                <span className="font-medium tabular-nums">
                  {brl(f.valor_unitario)}
                </span>
                <span className="text-stone-500 dark:text-stone-400">
                  {f.quantidade ? `${numero(f.quantidade)} un.` : ""}
                </span>
                <span className="text-stone-600 dark:text-stone-300">
                  {f.orgao_nome}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="mt-12 text-sm text-stone-500 dark:text-stone-400">
        Agrupamento por descrição normalizada e unidade canônica.{" "}
        <Link href="/metodologia" className="underline">
          Como este número foi calculado
        </Link>
        .
      </p>
    </>
  );
}
