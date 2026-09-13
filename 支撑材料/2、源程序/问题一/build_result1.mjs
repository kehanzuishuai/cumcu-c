import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = "D:/2026数模/审题codex";
const templatePath = path.join(root, "source_materials", "C题", "附件", "附件5", "result1.xlsx");
const payloadPath = path.join(root, "intermediate", "q1_workbook_payload.json");
const outputPath = path.join(root, "results", "result1.xlsx");
const previewDir = path.join(root, "previews");
const validationPath = path.join(root, "validation", "result1_workbook_validation.json");

const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
if (payload.purchase_plan.length !== 144) {
  throw new Error(`Q1 workbook payload must contain 144 slots, got ${payload.purchase_plan.length}`);
}

const source = await FileBlob.load(templatePath);
const workbook = await SpreadsheetFile.importXlsx(source);
const plan = workbook.worksheets.getItem("计划购电量");
const storage = workbook.worksheets.getItem("充放电量");

const labels = payload.purchase_plan.map((row) => [row.interval]);
const purchases = payload.purchase_plan.map((row) => [row.purchase_kwh]);
plan.getRange("A2:A145").values = labels;
plan.getRange("B2:B145").values = purchases;
plan.getRange("B2:B145").format.numberFormat = "0.0000";

// A01 is an acknowledged official-source conflict.  The visible note prevents a
// corrected natural-day label map from being mistaken for an official erratum.
plan.getRange("D1").copyFrom(plan.getRange("A1"), "all");
plan.getRange("D2:D3").copyFrom(plan.getRange("A2"), "all");
plan.getRange("D1:D3").values = [
  ["A01 时间标签说明"],
  ["本文件将原模板整体后移10分钟的标签纠正为自然日0:00-24:00。"],
  ["输入0:10…24:00按对应10分钟槽的右端点离散值使用；这是用户确认的工作口径，不是官方勘误。"],
];
plan.getRange("D1").format.font = { bold: true };
plan.getRange("D2:D3").format.wrapText = true;
plan.getRange("D1:D3").format.verticalAlignment = "center";
plan.getRange("D1:D3").format.columnWidth = 64;
plan.getRange("D2:D3").format.rowHeight = 34;

const storageRows = payload.storage_four_hour_summary;
if (storageRows.length !== 6) {
  throw new Error(`Q1 storage summary must contain 6 blocks, got ${storageRows.length}`);
}
storage.getRange("B2:B7").values = storageRows.map((row) => [row.charge_kwh]);
storage.getRange("C2:C7").values = storageRows.map((row) => [row.discharge_kwh]);
storage.getRange("E2:E3").values = [
  [payload.soc_endpoints_kwh["0:00"]],
  [payload.soc_endpoints_kwh["24:00"]],
];
storage.getRange("B2:C7").format.numberFormat = "0.0000";
storage.getRange("E2:E3").format.numberFormat = "0.0000";

workbook.recalculate();
await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
await fs.mkdir(path.dirname(validationPath), { recursive: true });
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);

const savedBlob = await FileBlob.load(outputPath);
const saved = await SpreadsheetFile.importXlsx(savedBlob);
const savedPlan = saved.worksheets.getItem("计划购电量");
const savedStorage = saved.worksheets.getItem("充放电量");

const savedLabels = savedPlan.getRange("A2:A145").values.map((row) => row[0]);
const savedPurchases = savedPlan.getRange("B2:B145").values.map((row) => Number(row[0]));
const savedCharge = savedStorage.getRange("B2:B7").values.map((row) => Number(row[0]));
const savedDischarge = savedStorage.getRange("C2:C7").values.map((row) => Number(row[0]));
const savedSoc = savedStorage.getRange("E2:E3").values.map((row) => Number(row[0]));
const expectedPurchases = payload.purchase_plan.map((row) => row.purchase_kwh);
const expectedCharge = storageRows.map((row) => row.charge_kwh);
const expectedDischarge = storageRows.map((row) => row.discharge_kwh);

const maxAbs = (a, b) => Math.max(...a.map((value, i) => Math.abs(value - b[i])));
const labelsMatch = savedLabels.every((value, i) => value === labels[i][0]);
const sheetNames = [
  saved.worksheets.getItemAt(0).name,
  saved.worksheets.getItemAt(1).name,
];

const inspections = {};
for (const [name, options] of Object.entries({
  plan_head: { kind: "table", sheetId: "计划购电量", range: "A1:D8", include: "values,formulas", tableMaxRows: 8, tableMaxCols: 4, maxChars: 6000 },
  plan_tail: { kind: "table", sheetId: "计划购电量", range: "A140:D145", include: "values,formulas", tableMaxRows: 6, tableMaxCols: 4, maxChars: 6000 },
  storage: { kind: "table", sheetId: "充放电量", range: "A1:E7", include: "values,formulas", tableMaxRows: 7, tableMaxCols: 5, maxChars: 6000 },
  formula_errors: { kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: "result1 final formula error scan", maxChars: 6000 },
})) {
  const inspected = await saved.inspect(options);
  inspections[name] = inspected.ndjson;
}

const renderJobs = [
  ["计划购电量", "A1:D145", "result1_plan_full.png", 1],
  ["计划购电量", "A1:D12", "result1_plan_head.png", 1.5],
  ["计划购电量", "A136:D145", "result1_plan_tail.png", 1.5],
  ["充放电量", "A1:E7", "result1_storage.png", 1.5],
];
for (const [sheetName, range, fileName, scale] of renderJobs) {
  const preview = await saved.render({ sheetName, range, scale, format: "png" });
  await fs.writeFile(path.join(previewDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}

const validation = {
  schema_version: 1,
  question: "Q1",
  workbook: path.relative(root, outputPath).replaceAll("\\", "/"),
  source_template: path.relative(root, templatePath).replaceAll("\\", "/"),
  status: "PASS",
  checks: {
    sheet_names_exact: JSON.stringify(sheetNames) === JSON.stringify(["计划购电量", "充放电量"]),
    purchase_rows: savedPurchases.length,
    corrected_natural_day_labels_exact: labelsMatch,
    first_label: savedLabels[0],
    last_label: savedLabels.at(-1),
    max_purchase_difference_kwh: maxAbs(savedPurchases, expectedPurchases),
    max_charge_difference_kwh: maxAbs(savedCharge, expectedCharge),
    max_discharge_difference_kwh: maxAbs(savedDischarge, expectedDischarge),
    soc_endpoint_difference_kwh: maxAbs(savedSoc, [payload.soc_endpoints_kwh["0:00"], payload.soc_endpoints_kwh["24:00"]]),
    a01_disclosure_visible: savedPlan.getRange("D1:D3").values.flat().every((value) => typeof value === "string" && value.length > 0),
  },
  inspections,
  previews: renderJobs.map(([, , fileName]) => path.join("previews", fileName).replaceAll("\\", "/")),
};
const numericChecks = [
  validation.checks.max_purchase_difference_kwh,
  validation.checks.max_charge_difference_kwh,
  validation.checks.max_discharge_difference_kwh,
  validation.checks.soc_endpoint_difference_kwh,
];
const booleanChecks = [
  validation.checks.sheet_names_exact,
  validation.checks.corrected_natural_day_labels_exact,
  validation.checks.a01_disclosure_visible,
];
if (!booleanChecks.every(Boolean) || numericChecks.some((value) => value > 1e-9)) {
  validation.status = "FAIL";
}
await fs.writeFile(validationPath, JSON.stringify(validation, null, 2), "utf8");
console.log(JSON.stringify({ status: validation.status, output: outputPath, checks: validation.checks }));
if (validation.status !== "PASS") process.exitCode = 1;
