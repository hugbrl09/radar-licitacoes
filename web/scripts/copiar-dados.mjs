/**
 * Copia o resultado da análise do pipeline Python para dentro do app.
 *
 * O app lê de `web/data/` em vez de alcançar `../ingestao/dados/` para que o
 * diretório `web/` seja autocontido: é ele que vai para a Vercel, e um build lá
 * não tem o pipeline Python nem o JSONL bruto por perto.
 */
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const aqui = dirname(fileURLToPath(import.meta.url));
// Qual UF vai para o site. Trocar de estado é trocar esta variável e reprocessar.
const uf = (process.env.RADAR_UF ?? "to").toLowerCase();
const dados = join(aqui, "..", "..", "ingestao", "dados");
const destinoDir = join(aqui, "..", "data");

const arquivos = [
  { origem: `analise-${uf}.json`, destino: "analise.json", obrigatorio: true },
  { origem: `abertos-${uf}.json`, destino: "abertos.json", obrigatorio: false },
];

mkdirSync(destinoDir, { recursive: true });

for (const { origem, destino, obrigatorio } of arquivos) {
  const de = join(dados, origem);
  const para = join(destinoDir, destino);

  if (!existsSync(de)) {
    // Não é erro fatal quando já existe cópia: quem clona o repositório recebe
    // os JSON versionados e roda o app sem ter rodado a ingestão.
    if (existsSync(para)) {
      console.log(`${origem} não encontrado no pipeline — mantendo a cópia existente`);
      continue;
    }
    if (!obrigatorio) {
      console.log(`${origem} ausente (opcional) — seguindo sem ele`);
      continue;
    }
    console.error(`não encontrado: ${de}`);
    console.error("rode antes, em ingestao/: uv run python -m radar.analise");
    process.exit(1);
  }

  copyFileSync(de, para);
  console.log(`${origem} -> data/${destino}`);
}
