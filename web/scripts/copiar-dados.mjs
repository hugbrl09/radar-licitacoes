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
const origem = join(aqui, "..", "..", "ingestao", "dados", `analise-${uf}.json`);
const destino = join(aqui, "..", "data", "analise.json");

if (!existsSync(origem)) {
  // Não é erro fatal: quem clona o repositório recebe o data/analise.json
  // versionado e consegue rodar o app sem ter rodado a ingestão.
  if (existsSync(destino)) {
    console.log("análise não encontrada no pipeline — mantendo a cópia existente");
    process.exit(0);
  }
  console.error(`análise não encontrada em ${origem}`);
  console.error("rode antes: uv run python -m radar.analise (em ingestao/)");
  process.exit(1);
}

mkdirSync(dirname(destino), { recursive: true });
copyFileSync(origem, destino);
console.log(`análise copiada para ${destino}`);
