"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

type Linha = {
  slug: string;
  descricao: string;
  descricaoExemplo: string;
  unidade: string;
  segmento: string;
  observacoes: number;
  orgaos: number;
  precoMediano: string;
  faixa: string;
  dispersao: number | null;
  foraDaFaixa: number;
};

const TODOS = "Todos";

export default function BuscaItens({ linhas }: { linhas: Linha[] }) {
  const [termo, setTermo] = useState("");
  const [segmento, setSegmento] = useState(TODOS);

  // Só oferecemos segmentos que existem nos dados publicados — um filtro que
  // devolve lista vazia é uma promessa quebrada.
  const segmentos = useMemo(() => {
    const contagem = new Map<string, number>();
    for (const l of linhas) contagem.set(l.segmento, (contagem.get(l.segmento) ?? 0) + 1);
    return [...contagem.entries()].sort((a, b) => b[1] - a[1]);
  }, [linhas]);

  const filtradas = useMemo(() => {
    const t = termo.trim().toLowerCase();
    return linhas.filter((l) => {
      if (segmento !== TODOS && l.segmento !== segmento) return false;
      if (!t) return true;
      return (
        l.descricao.toLowerCase().includes(t) ||
        l.descricaoExemplo.toLowerCase().includes(t)
      );
    });
  }, [linhas, termo, segmento]);

  return (
    <div>
      <label className="block">
        <span className="sr-only">Buscar item</span>
        <input
          type="search"
          value={termo}
          onChange={(e) => setTermo(e.target.value)}
          placeholder="Buscar item — ex.: arroz, cadeira, notebook"
          className="w-full rounded-lg border border-stone-300 bg-white px-4 py-3 text-base
                     placeholder:text-stone-400 focus:border-stone-500 focus:outline-none
                     dark:border-stone-700 dark:bg-stone-900 dark:placeholder:text-stone-500"
        />
      </label>

      <div className="mt-4 flex flex-wrap gap-2">
        {[[TODOS, linhas.length] as const, ...segmentos].map(([nome, n]) => {
          const ativo = segmento === nome;
          return (
            <button
              key={nome}
              type="button"
              onClick={() => setSegmento(nome)}
              aria-pressed={ativo}
              className={`rounded-full border px-3 py-1 text-sm transition-colors ${
                ativo
                  ? "border-stone-900 bg-stone-900 text-white dark:border-stone-100 dark:bg-stone-100 dark:text-stone-900"
                  : "border-stone-300 text-stone-600 hover:border-stone-500 dark:border-stone-700 dark:text-stone-300"
              }`}
            >
              {nome}{" "}
              <span className={ativo ? "opacity-70" : "text-stone-400"}>{n}</span>
            </button>
          );
        })}
      </div>

      <p className="mt-3 text-sm text-stone-500 dark:text-stone-400">
        {filtradas.length === linhas.length
          ? `${linhas.length} categorias de item com comparação possível`
          : `${filtradas.length} de ${linhas.length} categorias`}
      </p>

      <ul className="mt-4 divide-y divide-stone-200 dark:divide-stone-800">
        {filtradas.map((l) => (
          <li key={l.slug}>
            <Link
              href={`/item/${l.slug}`}
              className="flex flex-wrap items-baseline gap-x-4 gap-y-1 py-4
                         hover:bg-stone-100 dark:hover:bg-stone-900"
            >
              <span className="font-medium">{l.descricaoExemplo}</span>
              <span className="text-xs uppercase tracking-wide text-stone-500 dark:text-stone-400">
                por {l.unidade.toLowerCase()}
              </span>
              <span className="ml-auto tabular-nums">{l.precoMediano}</span>
              <span className="w-full text-sm text-stone-500 dark:text-stone-400">
                faixa central {l.faixa} · {l.observacoes} compras em {l.orgaos} órgãos
                {l.foraDaFaixa > 0 &&
                  ` · ${l.foraDaFaixa} registro${l.foraDaFaixa > 1 ? "s" : ""} fora da faixa`}
              </span>
            </Link>
          </li>
        ))}
      </ul>

      {filtradas.length === 0 && (
        <p className="py-12 text-center text-stone-500 dark:text-stone-400">
          Nenhuma categoria encontrada{termo && ` para “${termo}”`}
          {segmento !== TODOS && ` em ${segmento}`}.
        </p>
      )}
    </div>
  );
}
