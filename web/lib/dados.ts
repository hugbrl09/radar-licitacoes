import fs from "node:fs";
import path from "node:path";

/**
 * Carrega o resultado da análise gerada pelo pipeline Python.
 *
 * A leitura é feita em tempo de build (Server Component), não em requisição:
 * o dado é um retrato imutável de uma ingestão, então não há o que revalidar
 * a cada acesso.
 */

export type ComparativoOrgao = {
  orgao_cnpj: string;
  orgao_nome: string;
  compras: number;
  preco_mediano: number;
  razao_vs_mediana: number;
  desvio_percentual: number;
};

export type ForaDaFaixa = {
  valor_unitario: number;
  quantidade: number | null;
  orgao_nome: string | null;
  descricao_original: string | null;
};

export type ItemAnalisado = {
  chave_item: string;
  descricao: string;
  descricao_exemplo: string;
  unidade: string;
  material_ou_servico: string | null;
  observacoes: number;
  observacoes_brutas: number;
  orgaos: number;
  preco_mediano: number;
  preco_minimo: number;
  preco_maximo: number;
  q1: number;
  q3: number;
  dispersao: number | null;
  fora_da_faixa: ForaDaFaixa[];
  comparativo_orgaos: ComparativoOrgao[];
};

export type CategoriaAmpla = {
  descricao: string;
  unidade: string;
  observacoes: number;
  orgaos: number;
  dispersao: number;
  q1: number;
  q3: number;
};

export type Analise = {
  metodologia: string;
  limitacao: string;
  criterios: {
    min_orgaos: number;
    min_observacoes: number;
    fator_cerca: number;
    limite_dispersao: number;
    apenas_materiais: boolean;
  };
  gerado_em: string;
  itens: ItemAnalisado[];
  /** Categorias amplas demais para comparação. Publicadas de propósito: omitir
   *  o que foi descartado seria escolher a dedo o que confirma a tese. */
  categorias_amplas: CategoriaAmpla[];
};

const CAMINHO = path.join(process.cwd(), "data", "analise.json");

let cache: Analise | null = null;

export function carregarAnalise(): Analise {
  if (!cache) {
    cache = JSON.parse(fs.readFileSync(CAMINHO, "utf-8")) as Analise;
  }
  return cache;
}

/**
 * A chave do item ("CABO REDE COMPUTADOR|UNIDADE") não serve como segmento de
 * URL. Geramos um slug estável e guardamos o caminho de volta, em vez de tentar
 * reconstruir a chave a partir do slug — a transformação não é reversível.
 */
export function gerarSlug(chave: string): string {
  // ̀-ͯ é a faixa de marcas diacríticas combinantes que o NFD separa.
  return chave
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function indicePorSlug(): Map<string, ItemAnalisado> {
  const indice = new Map<string, ItemAnalisado>();
  for (const item of carregarAnalise().itens) {
    let slug = gerarSlug(item.chave_item);
    // Colisão é improvável, mas silenciosa se acontecer: sufixamos para que
    // dois itens distintos nunca compartilhem a mesma página.
    if (indice.has(slug)) {
      let n = 2;
      while (indice.has(`${slug}-${n}`)) n++;
      slug = `${slug}-${n}`;
    }
    indice.set(slug, item);
  }
  return indice;
}

export const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export const numero = (v: number) => v.toLocaleString("pt-BR");
