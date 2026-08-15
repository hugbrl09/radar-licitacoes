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
  /** Deduzido dos próprios dados pelo pipeline — a UF não fica escrita no código
   *  da interface, então trocar de estado não exige mexer aqui. */
  recorte: {
    ufs: string[];
    compras: number;
    orgaos: number;
    periodo: [string | null, string | null];
  };
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
/** Limite do trecho legível do slug.
 *
 *  Existe porque descrições reais chegam a 300+ caracteres: compras municipais
 *  trazem a especificação inteira no campo de descrição ("abacaxi pérola 1a
 *  qualidade in natura tamanho e coloração uniforme polpa firme livres de
 *  sujidades…"). Um slug desse tamanho estoura o limite de caminho do Windows
 *  na hora de gerar as páginas estáticas. */
const MAX_SLUG = 60;

/** Hash determinístico (djb2) só para desempatar slugs truncados. Não é
 *  criptográfico e nem precisa ser — só precisa ser estável entre builds. */
function hashCurto(s: string): string {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
}

export function gerarSlug(chave: string): string {
  // ̀-ͯ é a faixa de marcas diacríticas combinantes que o NFD separa.
  const base = chave
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

  if (base.length <= MAX_SLUG) return base;

  // Trunca na fronteira de palavra para não cortar no meio, e carimba o hash da
  // chave completa — duas descrições que começam igual continuam com URLs
  // distintas.
  const cortado = base.slice(0, MAX_SLUG).replace(/-[^-]*$/, "");
  return `${cortado}-${hashCurto(chave)}`;
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

/** Nome e artigo de cada UF.
 *
 *  O artigo não é enfeite: em português, nome de estado rege artigo de um jeito
 *  que não dá para deduzir do nome. Diz-se "do Tocantins" e "do Pará", mas "de
 *  Goiás" e "de Pernambuco"; e "da Bahia". Como a UF é parâmetro do pipeline, a
 *  regra precisa valer para qualquer estado, não só para o recorte atual.
 *
 *  artigo "" = não leva artigo. */
const UF: Record<string, { nome: string; artigo: "o" | "a" | "" }> = {
  AC: { nome: "Acre", artigo: "o" },
  AL: { nome: "Alagoas", artigo: "" },
  AP: { nome: "Amapá", artigo: "o" },
  AM: { nome: "Amazonas", artigo: "o" },
  BA: { nome: "Bahia", artigo: "a" },
  CE: { nome: "Ceará", artigo: "o" },
  DF: { nome: "Distrito Federal", artigo: "o" },
  ES: { nome: "Espírito Santo", artigo: "o" },
  GO: { nome: "Goiás", artigo: "" },
  MA: { nome: "Maranhão", artigo: "o" },
  MT: { nome: "Mato Grosso", artigo: "o" },
  MS: { nome: "Mato Grosso do Sul", artigo: "o" },
  MG: { nome: "Minas Gerais", artigo: "" },
  PA: { nome: "Pará", artigo: "o" },
  PB: { nome: "Paraíba", artigo: "a" },
  PR: { nome: "Paraná", artigo: "o" },
  PE: { nome: "Pernambuco", artigo: "" },
  PI: { nome: "Piauí", artigo: "o" },
  RJ: { nome: "Rio de Janeiro", artigo: "o" },
  RN: { nome: "Rio Grande do Norte", artigo: "o" },
  RS: { nome: "Rio Grande do Sul", artigo: "o" },
  RO: { nome: "Rondônia", artigo: "" },
  RR: { nome: "Roraima", artigo: "" },
  SC: { nome: "Santa Catarina", artigo: "" },
  SP: { nome: "São Paulo", artigo: "" },
  SE: { nome: "Sergipe", artigo: "" },
  TO: { nome: "Tocantins", artigo: "o" },
};

const juntar = (partes: string[]) =>
  partes.length <= 1
    ? partes[0] ?? ""
    : `${partes.slice(0, -1).join(", ")} e ${partes[partes.length - 1]}`;

/** Nome puro: "Tocantins". Para título e rótulo, onde não cabe artigo. */
export function nomearRecorte(ufs: string[]): string {
  if (ufs.length === 0) return "Brasil";
  return juntar(ufs.map((u) => UF[u]?.nome ?? u));
}

/** Com artigo: "o Tocantins", "a Bahia", "Goiás". */
export function recorteComArtigo(ufs: string[]): string {
  if (ufs.length === 0) return "o Brasil";
  return juntar(
    ufs.map((u) => {
      const e = UF[u];
      if (!e) return u;
      return e.artigo ? `${e.artigo} ${e.nome}` : e.nome;
    }),
  );
}

/** Contraído com "de": "do Tocantins", "da Bahia", "de Goiás". */
export function recorteDe(ufs: string[]): string {
  if (ufs.length === 0) return "do Brasil";
  return juntar(
    ufs.map((u) => {
      const e = UF[u];
      if (!e) return `de ${u}`;
      if (e.artigo === "o") return `do ${e.nome}`;
      if (e.artigo === "a") return `da ${e.nome}`;
      return `de ${e.nome}`;
    }),
  );
}

export const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export const numero = (v: number) => v.toLocaleString("pt-BR");
