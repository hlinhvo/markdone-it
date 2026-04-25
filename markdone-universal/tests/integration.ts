export {};

async function main() {
  const baseUrl = Deno.env.get("DOCUSHIFT_BASE_URL") ?? "http://127.0.0.1:7482";
  const fixturePath = Deno.env.get("DOCUSHIFT_TEST_FILE") ?? "";
  const expectedOutputDir = Deno.env.get("DOCUSHIFT_EXPECTED_OUTPUT_DIR") ??
    "../outputs";

  if (!fixturePath) {
    console.error(
      "Set DOCUSHIFT_TEST_FILE to a representative PDF path before running integration tests.",
    );
    Deno.exit(1);
  }

  const fileBytes = await Deno.readFile(fixturePath);
  const fileName = fixturePath.split("/").at(-1) ?? "test.pdf";

  const formData = new FormData();
  formData.append("target", "vault_md");
  formData.append("sourceType", "auto");
  formData.append("yamlFrontmatter", "true");
  formData.append(
    "files",
    new File([fileBytes], fileName, { type: "application/pdf" }),
    fileName,
  );

  const response = await fetch(`${baseUrl}/api/convert`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    console.error(`Conversion request failed with status ${response.status}`);
    console.error(await response.text());
    Deno.exit(1);
  }

  const payload = await response.json();
  if (!Array.isArray(payload.results) || payload.results.length === 0) {
    console.error("No conversion results were returned.");
    Deno.exit(1);
  }

  const first = payload.results[0];
  if (first.status !== "completed") {
    console.error("Conversion did not complete successfully.");
    console.error(JSON.stringify(first, null, 2));
    Deno.exit(1);
  }

  const outputFileName = first.outputFileName;
  if (!outputFileName) {
    console.error("No output filename was returned.");
    Deno.exit(1);
  }

  const outputPath = `${expectedOutputDir}/${outputFileName}`;
  const content = await Deno.readTextFile(outputPath);

  if (!content.startsWith("---\n")) {
    console.error("Expected YAML frontmatter at the start of the generated Markdown.");
    Deno.exit(1);
  }

  console.log("Integration test passed.");
  console.log(`Verified output: ${outputPath}`);
}

await main();

// Made with Bob
