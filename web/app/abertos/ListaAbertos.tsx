"use client";

import { useMemo, useState } from "react";
import type { EditalAberto } from "@/lib/abertos";

const TODOS = "Todos";

type Filtro = "com_prazo" | "cadastro" | "todos";

/** Dias até a data. Negativo = já venceu.
 *
 *  Calculado no navegador, e não no build, de propósito: um "faltam 4 dias"
 *  gravado na página estaria errado no dia seguinte. A página guarda a data
 *  absoluta e a conta é refeita a cada visita.
 */
function diasAte(iso: string | null): number | null {
  if (!iso) return null;
  const alvo = new Date(iso).getTime();
  if (Number.isNaN(alvo)) return null;
  return Math.floor((alvo - Date.now()) / 86_400_000);
}

function rotuloPrazo(dias: number | null): { texto: string; urgente: boolean } {
  if (dias === null) return { texto: "sem data", urgente: false };
  if (dias < 0) return { texto: "encerrado", urgente: false };
  if (dias === 0) return { texto: "encerra hoje", urgente: true };
  if (dias === 1) return { texto: "encerra amanhã", urgente: true };
  if (dias <= 7) return { texto: dias + " dias", urgente: true };
  return { texto: dias + " dias", urgente: false };
}

const brl = (v: number) =>
  v.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  });

const chip = (ativo: boolean) =>
  `rounded-full border px-3 py-1 text-sm transition-colors ${
    ativo
      ? "border-stone-900 bg-stone-900 text-white dark:border-stone-100 dark:bg-stone-100 dark:text-stone-900"
      : "border-stone-300 text-stone-600 hover:border-stone-500 dark:border-stone-700 dark:text-stone-300"
  }`;

export default function ListaAbertos({ editais }: { editais: EditalAberto[] }) {
  const [termo, setTermo] = useState("");
  const [segmento, setSegmento] = useState(TODOS);
  const [filtro, setFiltro] = useState<Filtro>("com_prazo");

  const segmentos = useMemo(() => {
    const c = new Map<string, number>();
    for (const e of editais) c.set(e.segmento, (c.get(e.segmento) ?? 0) + 1);
    return [...c.entries()].sort((a, b) => b[1] - a[1]);
  }, [editais]);

  const visiveis = useMemo(() => {
    const t = termo.trim().toLowerCase();
    return editais
      .map((e) => ({ e, dias: diasAte(e.data_fim_proposta) }))
      .filter(({ e, dias }) => {
        if (filtro === "com_prazo" && e.cadastro_permanente) return false;
        if (filtro === "cadastro" && !e.cadastro_permanente) return false;
        // Encerrado desde a coleta: some da visão com prazo, mas continua
        // acessível em "Todos" — o dado não é apagado, só deixa de ser lead.
        if (filtro === "com_prazo" && dias !== null && dias < 0) return false;
        if (segmento !== TODOS && e.segmento !== segmento) return false;
        if (!t) return true;
        return (
          e.objeto.toLowerCase().includes(t) ||
          (e.orgao_nome ?? "").toLowerCase().includes(t) ||
          (e.municipio ?? "").toLowerCase().includes(t)
        );
      })
      .sort((a, b) => {
        // Quem encerra antes aparece antes; sem data vai para o fim.
        if (a.dias === null) return 1;
        if (b.dias === null) return -1;
        return a.dias - b.dias;
      });
  }, [editais, termo, segmento, filtro]);

  const abas: { id: Filtro; rotulo: string; n: number }[] = [
    {
      id: "com_prazo",
      rotulo: "Com prazo",
      n: editais.filter((e) => !e.cadastro_permanente).length,
    },
    {
      id: "cadastro",
      rotulo: "Cadastro permanente",
      n: editais.filter((e) => e.cadastro_permanente).length,
    },
    { id: "todos", rotulo: "Todos", n: editais.length },
  ];

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {abas.map((a) => (
          <button
            key={a.id}
            type="button"
            aria-pressed={filtro === a.id}
            onClick={() => setFiltro(a.id)}
            className={`rounded-lg border px-3 py-2 text-sm transition-colors ${
              filtro === a.id
                ? "border-stone-900 bg-stone-900 text-white dark:border-stone-100 dark:bg-stone-100 dark:text-stone-900"
                : "border-stone-300 text-stone-600 hover:border-stone-500 dark:border-stone-700 dark:text-stone-300"
            }`}
          >
            {a.rotulo} <span className="opacity-60">{a.n}</span>
          </button>
        ))}
      </div>

      <label className="mt-4 block">
        <span className="sr-only">Buscar edital</span>
        <input
          type="search"
          value={termo}
          onChange={(e) => setTermo(e.target.value)}
          placeholder="Buscar por objeto, órgão ou município"
          className="w-full rounded-lg border border-stone-300 bg-white px-4 py-3 text-base
                     placeholder:text-stone-400 focus:border-stone-500 focus:outline-none
                     dark:border-stone-700 dark:bg-stone-900 dark:placeholder:text-stone-500"
        />
      </label>

      <div className="mt-3 flex flex-wrap gap-2">
        {[[TODOS, editais.length] as const, ...segmentos].map(([nome, n]) => (
          <button
            key={nome}
            type="button"
            onClick={() => setSegmento(nome)}
            aria-pressed={segmento === nome}
            className={chip(segmento === nome)}
          >
            {nome}{" "}
            <span className={segmento === nome ? "opacity-70" : "text-stone-400"}>
              {n}
            </span>
          </button>
        ))}
      </div>

      <p className="mt-4 text-sm text-stone-500 dark:text-stone-400">
        {visiveis.length} {visiveis.length === 1 ? "edital" : "editais"}
      </p>

      <ul className="mt-2 divide-y divide-stone-200 dark:divide-stone-800">
        {visiveis.map(({ e, dias }) => {
          const prazo = rotuloPrazo(dias);
          return (
            <li key={e.numero_controle_pncp ?? e.objeto} className="py-4">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span
                  className={`shrink-0 rounded px-2 py-0.5 text-xs font-medium ${
                    e.cadastro_permanente
                      ? "bg-stone-200 text-stone-700 dark:bg-stone-800 dark:text-stone-300"
                      : prazo.urgente
                        ? "bg-amber-100 text-amber-900 dark:bg-amber-900/50 dark:text-amber-100"
                        : "bg-stone-200 text-stone-700 dark:bg-stone-800 dark:text-stone-300"
                  }`}
                >
                  {e.cadastro_permanente ? "cadastro permanente" : prazo.texto}
                </span>
                <span className="text-xs uppercase tracking-wide text-stone-500 dark:text-stone-400">
                  {e.modalidade}
                </span>
                {e.valor_global != null && (
                  <span className="ml-auto text-sm tabular-nums text-stone-600 dark:text-stone-300">
                    {brl(e.valor_global)}
                  </span>
                )}
              </div>

              <p className="mt-1.5 text-sm leading-snug">
                {e.link ? (
                  <a
                    href={e.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:underline"
                  >
                    {e.objeto}
                  </a>
                ) : (
                  e.objeto
                )}
              </p>

              <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">
                {e.orgao_nome}
                {e.municipio && ` · ${e.municipio}`}
                {e.data_fim_proposta && !e.cadastro_permanente && (
                  <>
                    {" · até "}
                    {new Date(e.data_fim_proposta).toLocaleString("pt-BR", {
                      dateStyle: "short",
                      timeStyle: "short",
                    })}
                  </>
                )}
              </p>
            </li>
          );
        })}
      </ul>

      {visiveis.length === 0 && (
        <p className="py-12 text-center text-stone-500 dark:text-stone-400">
          Nenhum edital encontrado com estes filtros.
        </p>
      )}
    </div>
  );
}
