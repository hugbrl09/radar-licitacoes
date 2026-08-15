import type { Metadata } from "next";
import Link from "next/link";
import { carregarAnalise, recorteDe } from "@/lib/dados";
import "./globals.css";

export function generateMetadata(): Metadata {
  const recorte = recorteDe(carregarAnalise().recorte.ufs);
  return {
    title: "Radar de Licitações — faixas de preço em compras públicas",
    description: `Faixas de preço praticadas em compras públicas ${recorte}, a partir dos dados abertos do PNCP.`,
  };
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const recorte = recorteDe(carregarAnalise().recorte.ufs);

  return (
    <html lang="pt-BR">
      <body className="min-h-screen bg-stone-50 text-stone-900 antialiased dark:bg-stone-950 dark:text-stone-100">
        <header className="border-b border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900">
          <div className="mx-auto flex max-w-5xl flex-wrap items-baseline gap-x-6 gap-y-2 px-6 py-5">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              Radar de Licitações
            </Link>
            <span className="text-sm text-stone-500 dark:text-stone-400">
              Compras públicas {recorte} · dados abertos do PNCP
            </span>
            <nav className="ml-auto flex gap-5 text-sm">
              <Link href="/" className="hover:underline">
                Itens
              </Link>
              <Link href="/metodologia" className="hover:underline">
                Metodologia
              </Link>
            </nav>
          </div>
        </header>

        <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>

        <footer className="mx-auto max-w-5xl px-6 py-12 text-sm text-stone-500 dark:text-stone-400">
          <p>
            Projeto de estudo sobre dados abertos. As informações são derivadas do
            Portal Nacional de Contratações Públicas (PNCP) e apresentadas no nível
            de órgão e CNPJ.{" "}
            <Link href="/metodologia" className="underline">
              Leia a metodologia e as limitações
            </Link>{" "}
            antes de interpretar qualquer número desta página.
          </p>
        </footer>
      </body>
    </html>
  );
}
