import { notFound } from "next/navigation";
import ListaAbertos from "./ListaAbertos";
import { carregarAbertos } from "@/lib/abertos";
import { recorteDe } from "@/lib/dados";

export const metadata = {
  title: "Licitações abertas — Radar de Licitações",
};

export default function Abertos() {
  const dados = carregarAbertos();
  if (!dados) notFound();

  const coletado = new Date(dados.coletado_em);

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Licitações abertas</h1>
      <p className="mt-3 max-w-3xl text-stone-600 dark:text-stone-300">
        Editais {recorteDe([dados.uf])} com proposta em aberto no momento da coleta.
        Cada item leva à página oficial no PNCP, onde ficam o edital e as
        instruções de participação.
      </p>

      {/* Um retrato datado apresentado como "agora" é uma mentira silenciosa.
          O prazo de cada edital é recalculado no navegador, mas editais
          publicados depois desta coleta simplesmente não estão aqui. */}
      <div
        role="note"
        className="mt-6 rounded-lg border-l-4 border-stone-400 bg-stone-100 p-4 text-sm
                   text-stone-700 dark:border-stone-600 dark:bg-stone-900 dark:text-stone-300"
      >
        <p>
          <strong className="font-medium">Retrato de{" "}
          {coletado.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</strong>
          . Os prazos abaixo são recalculados a cada visita, mas editais publicados
          depois dessa coleta não aparecem — confirme sempre no PNCP antes de agir.
        </p>
        {!dados.completo && (
          <p className="mt-2">
            <strong className="font-medium">Lista incompleta:</strong> a API do PNCP
            informou {dados.total_informado_api} editais e só foi possível ler{" "}
            {dados.total}.
          </p>
        )}
      </div>

      <div className="mt-8">
        <ListaAbertos editais={dados.editais} />
      </div>

      <p className="mt-10 text-sm text-stone-500 dark:text-stone-400">
        <strong className="font-medium">Cadastro permanente</strong> agrupa
        credenciamento, pré-qualificação e manifestação de interesse: são cadastros
        que ficam abertos por meses ou anos, não disputas com data para fechar.
        Ficam separados para que a contagem de prazo não sugira urgência que não
        existe.
      </p>
    </>
  );
}
