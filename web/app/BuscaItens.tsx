"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

type Linha = {
  slug: string;
  descricao: string;
  descricaoExemplo: string;
  unidade: string;
  observacoes: number;
  orgaos: number;
  precoMediano: string;
  faixa: string;
  dispersao: number | null;
  foraDaFaixa: number;
};

export default function BuscaItens({ linhas }: { linhas: Linha[] }) {
  const [termo, setTermo] = useState("");

  const filtradas = useMemo(() => {
    const t = termo.trim().toLowerCase();
    if (!t) return linhas;
    return linhas.filter(
      (l) =>
        l.descricao.toLowerCase().includes(t) ||
        l.descricaoExemplo.toLowerCase().includes(t),
    );
  }, [linhas, termo]);

  return (
    <div>
      <label className="block">
        <span className="sr-only">Buscar item</span>
        <input
          type="search"
          value={termo}
          onChange={(e) => setTermo(e.target.value)}
          placeholder="Buscar item — ex.: monitor, cadeira, cabo"
          className="w-full rounded-lg border border-stone-300 bg-white px-4 py-3 text-base
                     placeholder:text-stone-400 focus:border-stone-500 focus:outline-none
                     dark:border-stone-700 dark:bg-stone-900 dark:placeholder:text-stone-500"
        />
      </label>

      <p className="mt-3 text-sm text-stone-500 dark:text-stone-400">
        {filtradas.length === linhas.length
          ? `${linhas.length} categorias de item com comparação possível`
          : `${filtradas.length} de ${linhas.length} categorias`}
      </p>

      <ul className="mt-6 divide-y divide-stone-200 dark:divide-stone-800">
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
          Nenhuma categoria encontrada para “{termo}”.
        </p>
      )}
    </div>
  );
}
