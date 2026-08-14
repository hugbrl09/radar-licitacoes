import { brl, carregarAnalise } from "@/lib/dados";

export const metadata = {
  title: "Metodologia — Radar de Licitações",
};

export default function Metodologia() {
  const { metodologia, limitacao, criterios, gerado_em, itens, categorias_amplas } =
    carregarAnalise();

  return (
    <article className="max-w-3xl">
      <h1 className="text-2xl font-semibold tracking-tight">
        Metodologia e limitações
      </h1>
      <p className="mt-3 text-stone-600 dark:text-stone-300">
        Toda afirmação desta página precisa ser auditável por quem discorda dela —
        inclusive pelos órgãos citados. Por isso o cálculo está descrito aqui, e não
        num rodapé.
      </p>

      <div
        role="note"
        className="mt-8 rounded-lg border-l-4 border-amber-500 bg-amber-50 p-5
                   text-amber-950 dark:bg-amber-950/40 dark:text-amber-100"
      >
        <h2 className="font-semibold">A limitação mais importante</h2>
        <p className="mt-2 text-sm leading-relaxed">{limitacao}</p>
      </div>

      <h2 className="mt-10 text-lg font-semibold">Como o número é calculado</h2>
      <p className="mt-2 leading-relaxed text-stone-700 dark:text-stone-300">
        {metodologia}
      </p>

      <h2 className="mt-10 text-lg font-semibold">O que este projeto não afirma</h2>
      <ul className="mt-3 list-disc space-y-2 pl-5 text-stone-700 dark:text-stone-300">
        <li>
          Não afirma que houve superfaturamento, irregularidade, fraude ou má-fé. Um
          preço acima da mediana tem muitas explicações legítimas.
        </li>
        <li>
          Não identifica pessoas físicas. A agregação é feita em CNPJ e órgão — nome
          e CPF de sócio são dado pessoal sob a LGPD; CNPJ de empresa e identificação
          de órgão público não são.
        </li>
        <li>
          Não cobre todas as compras públicas. O recorte é Distrito Federal, pregão
          eletrônico, apenas itens com resultado homologado publicado.
        </li>
      </ul>

      <h2 className="mt-10 text-lg font-semibold">Critérios aplicados</h2>
      <dl className="mt-3 space-y-2 text-stone-700 dark:text-stone-300">
        <div className="flex gap-3">
          <dt className="min-w-56 text-stone-500 dark:text-stone-400">
            Mínimo de órgãos por item
          </dt>
          <dd className="tabular-nums">{criterios.min_orgaos}</dd>
        </div>
        <div className="flex gap-3">
          <dt className="min-w-56 text-stone-500 dark:text-stone-400">
            Mínimo de observações
          </dt>
          <dd className="tabular-nums">{criterios.min_observacoes}</dd>
        </div>
        <div className="flex gap-3">
          <dt className="min-w-56 text-stone-500 dark:text-stone-400">
            Cerca de atípicos
          </dt>
          <dd className="tabular-nums">{criterios.fator_cerca} × IQR</dd>
        </div>
        <div className="flex gap-3">
          <dt className="min-w-56 text-stone-500 dark:text-stone-400">Escopo</dt>
          <dd>
            {criterios.apenas_materiais
              ? "apenas materiais (serviços excluídos)"
              : "materiais e serviços"}
          </dd>
        </div>
        <div className="flex gap-3">
          <dt className="min-w-56 text-stone-500 dark:text-stone-400">
            Categorias publicadas
          </dt>
          <dd className="tabular-nums">{itens.length}</dd>
        </div>
        <div className="flex gap-3">
          <dt className="min-w-56 text-stone-500 dark:text-stone-400">
            Dados processados em
          </dt>
          <dd>{new Date(gerado_em).toLocaleString("pt-BR")}</dd>
        </div>
      </dl>

      <h2 className="mt-10 text-lg font-semibold">Por que serviços ficam de fora</h2>
      <p className="mt-2 leading-relaxed text-stone-700 dark:text-stone-300">
        Nos dados reais, a descrição “Serviços de Gerenciamento de Redes de
        Tecnologia da Informação e Comunicação” aparece com valores homologados de R$
        6.111, R$ 25.000 e R$ 170.000. Não é alguém pagando 27 vezes mais pela mesma
        coisa — é escopo contratado completamente diferente sob o mesmo rótulo.
        Comparar serviços pela descrição produziria alarme falso, então a análise se
        restringe a materiais, cuja descrição fica mais próxima de uma especificação.
      </p>

      <h2 className="mt-10 text-lg font-semibold">
        Categorias descartadas por serem amplas demais
      </h2>
      <p className="mt-2 leading-relaxed text-stone-700 dark:text-stone-300">
        Estas {categorias_amplas.length} categorias atenderam a todos os critérios,
        mas a faixa de preço dentro delas é larga a ponto de a comparação não
        significar nada — o rótulo funciona como balde, não como categoria. Ficam
        listadas aqui porque omitir o que foi descartado seria escolher a dedo o que
        confirma a tese.
      </p>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[32rem] text-sm">
          <thead>
            <tr className="border-b border-stone-300 text-left dark:border-stone-700">
              <th className="py-2 pr-4 font-medium">Categoria</th>
              <th className="py-2 pr-4 text-right font-medium">Faixa central</th>
              <th className="py-2 text-right font-medium">Dispersão</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-200 dark:divide-stone-800">
            {categorias_amplas.map((c) => (
              <tr key={`${c.descricao}-${c.unidade}`}>
                <td className="py-2 pr-4">{c.descricao}</td>
                <td className="py-2 pr-4 text-right tabular-nums">
                  {brl(c.q1)} – {brl(c.q3)}
                </td>
                <td className="py-2 text-right tabular-nums">
                  {c.dispersao.toLocaleString("pt-BR", {
                    maximumFractionDigits: 1,
                  })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="mt-10 text-lg font-semibold">Fonte</h2>
      <p className="mt-2 leading-relaxed text-stone-700 dark:text-stone-300">
        Portal Nacional de Contratações Públicas (PNCP), dados abertos. O valor
        utilizado é o <em>valor unitário homologado</em>, extraído do resultado de
        cada item. Itens anulados, revogados ou cancelados são descartados, assim
        como resultados posteriormente cancelados.
      </p>
    </article>
  );
}
