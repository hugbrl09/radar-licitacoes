import fs from "node:fs";
import path from "node:path";

export type EditalAberto = {
  numero_controle_pncp: string | null;
  objeto: string;
  segmento: string;
  orgao_nome: string | null;
  orgao_cnpj: string | null;
  unidade_nome: string | null;
  municipio: string | null;
  uf: string | null;
  modalidade: string;
  /** Credenciamento e afins: cadastro permanente, não disputa com prazo. */
  cadastro_permanente: boolean;
  valor_global: number | null;
  data_publicacao: string | null;
  data_fim_proposta: string | null;
  link: string | null;
};

export type Abertos = {
  coletado_em: string;
  uf: string;
  total: number;
  total_informado_api: number;
  /** false quando alguma página se perdeu — a interface precisa dizer isso. */
  completo: boolean;
  paginas_perdidas: number[];
  com_prazo: number;
  cadastro_permanente: number;
  editais: EditalAberto[];
};

const CAMINHO = path.join(process.cwd(), "data", "abertos.json");

let cache: Abertos | null = null;

/** Devolve null quando a coleta nunca rodou — a página some em vez de quebrar. */
export function carregarAbertos(): Abertos | null {
  if (cache) return cache;
  if (!fs.existsSync(CAMINHO)) return null;
  cache = JSON.parse(fs.readFileSync(CAMINHO, "utf-8")) as Abertos;
  return cache;
}
