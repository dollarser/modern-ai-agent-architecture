#!/usr/bin/env node

import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import createDOMPurify from "dompurify";
import { JSDOM } from "jsdom";

const window = new JSDOM("").window;
const purifier = createDOMPurify(window);
for (const method of ["addHook", "removeHook", "removeHooks", "removeAllHooks", "sanitize"]) {
  createDOMPurify[method] = purifier[method].bind(purifier);
}

const { default: mermaid } = await import("mermaid");

const directory = process.argv[2];
if (!directory) {
  console.error("usage: check_mermaid.mjs <directory>");
  process.exit(2);
}

const files = (await readdir(directory))
  .filter((name) => name.endsWith(".mmd"))
  .sort();

if (files.length === 0) {
  console.error(`No .mmd files found in ${directory}`);
  process.exit(1);
}

const failures = [];
for (const file of files) {
  try {
    const source = await readFile(path.join(directory, file), "utf8");
    await mermaid.parse(source, { suppressErrors: false });
  } catch (error) {
    failures.push(`${file}: ${error instanceof Error ? error.message : String(error)}`);
  }
}

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exit(1);
}

console.log(`Validated ${files.length} Mermaid diagrams`);
