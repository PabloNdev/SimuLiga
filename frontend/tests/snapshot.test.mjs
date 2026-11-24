import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const dataDir = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "public",
  "data",
);

async function readJson(name) {
  return JSON.parse(await readFile(path.join(dataDir, name), "utf8"));
}

test("snapshot manifest lists every published file", async () => {
  const manifest = await readJson("manifest.json");

  assert.equal(typeof manifest.generated_at, "string");
  assert.ok(!Number.isNaN(Date.parse(manifest.generated_at)));
  assert.ok(Number.isInteger(manifest.current_matchday));
  assert.ok(manifest.sims > 0);
  assert.ok(manifest.files.length >= 14);

  for (const file of [...manifest.files, "manifest.json"]) {
    await access(path.join(dataDir, file));
  }
});

test("projections match the published matchday and simulation count", async () => {
  const manifest = await readJson("manifest.json");

  for (const mode of ["score", "1x2"]) {
    const projection = await readJson(`projection-${mode}.json`);
    assert.equal(projection.mode, mode);
    assert.equal(projection.start_matchday, manifest.current_matchday);
    assert.equal(projection.n_sims, manifest.sims);
    assert.ok(projection.teams.length > 0);
  }
});

test("champions snapshot keeps both modes and its 36 teams", async () => {
  const manifest = await readJson("manifest.json");

  for (const mode of ["score", "1x2"]) {
    const projection = await readJson(`champions-projection-${mode}.json`);
    assert.equal(projection.mode, mode);
    assert.equal(projection.n_sims, manifest.sims);
    assert.equal(projection.teams.length, 36);

    const matches = await readJson(`champions-matches-${mode}.json`);
    assert.equal(matches.mode, mode);
    assert.ok(matches.matches.length > 0);
  }
});
