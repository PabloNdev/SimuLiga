import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const ROOTS = ["app", "components", "lib"];
const EXTENSIONS = new Set([".ts", ".tsx"]);

function collectSourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return collectSourceFiles(path);
    return EXTENSIONS.has(entry.name.slice(entry.name.lastIndexOf(".")))
      ? [path]
      : [];
  });
}

const files = ROOTS.flatMap((root) => collectSourceFiles(root));

const KNOWN_CORRUPTIONS = [
  "Proyecci?n",
  "proyecci?n",
  "ning?n",
  "ah? se",
  "aqu?.",
  " ? actual",
  " ? pretemporada",
];

test("frontend source files contain no Unicode replacement characters", () => {
  for (const file of files) {
    const text = readFileSync(file, "utf8");
    assert.equal(
      text.includes("\uFFFD"),
      false,
      `${file} contains U+FFFD replacement characters`,
    );
  }
});

test("frontend source files contain no corrupted Spanish text", () => {
  for (const file of files) {
    const lines = readFileSync(file, "utf8").split("\n");
    for (const [index, line] of lines.entries()) {
      for (const corruption of KNOWN_CORRUPTIONS) {
        assert.equal(
          line.includes(corruption),
          false,
          `${file}:${index + 1} contains "${corruption}"`,
        );
      }
      assert.doesNotMatch(
        line,
        /<\/strong> \?\{" "\}/,
        `${file}:${index + 1} contains a corrupted separator`,
      );
      assert.doesNotMatch(
        line,
        /jornada \{state\.startMatchday\}\?/,
        `${file}:${index + 1} contains corrupted punctuation`,
      );
    }
  }
});
