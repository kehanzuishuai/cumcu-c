import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = "D:/2026数模/审题codex";
const variant = process.env.BUILD_VARIANT || "result3";
const question = variant === "result4-3" ? "Q4-3" : "Q3";
const payloadStem = variant === "result4-3" ? "q4_3" : "q3";
const templatePath = process.env.TEMPLATE_PATH || path.join(root, "source_materials", "C题", "附件", "附件5", `${variant}.xlsx`);
const payloadPath = process.env.PAYLOAD_PATH || path.join(root, "intermediate", `${payloadStem}_workbook_payload.json`);
const outputPath = process.env.OUTPUT_PATH || path.join(root, "results", `${variant}.xlsx`);
const validationPath = process.env.VALIDATION_PATH || path.join(root, "validation", `${variant}_workbook_validation.json`);
const previewDir = process.env.PREVIEW_DIR || path.join(root, "previews");
const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
if (payload.plans.length !== 334 || payload.storage_four_hour.length !== 2004) throw new Error("Q3 payload shape mismatch");

const fmtMinute = (minute) => minute === 1440 ? "24:00" : `${String(Math.floor(minute / 60)).padStart(2, "0")}:${String(minute % 60).padStart(2, "0")}`;
const naturalLabels = Array.from({ length: 144 }, (_, slot) => `${fmtMinute(slot * 10)}-${fmtMinute((slot + 1) * 10)}`);
const asDate = (iso) => new Date(`${iso}T00:00:00`);
const isoDate = (value) => {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === "number") return new Date(Date.UTC(1899, 11, 30) + value * 86400000).toISOString().slice(0, 10);
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? String(value).slice(0, 10) : parsed.toISOString().slice(0, 10);
};
const maxAbs = (a, b) => Math.max(0, ...a.map((value, idx) => Math.abs(Number(value) - Number(b[idx]))));

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(templatePath));
const original = workbook.worksheets.getItem("计划购电量");
const adjusted = workbook.worksheets.getItem("调整购电量");
const storage = workbook.worksheets.getItem("充放电量");
const emergency = workbook.worksheets.getItem("紧急购电量");

function fillPlanSheet(sheet, field, totalField) {
  sheet.getRange("B1:EO1").values = [naturalLabels];
  sheet.getRange("A2:A335").values = payload.plans.map((row) => [asDate(row.date)]);
  sheet.getRange("B2:EO335").values = payload.plans.map((row) => row[field]);
  sheet.getRange("EP2:EP335").values = payload.plans.map((row) => [row[totalField]]);
  sheet.getRange("EQ2:EQ335").values = payload.plans.map((row) => [row.total_cost_yuan]);
  sheet.getRange("A2:A335").format.numberFormat = "m/d/yy";
  sheet.getRange("B2:EP335").format.numberFormat = "0.0000";
  sheet.getRange("EQ2:EQ335").format.numberFormat = "0.00";
  sheet.getRange("ES1").copyFrom(sheet.getRange("A1"), "all");
  sheet.getRange("ES2:ES3").copyFrom(sheet.getRange("A2"), "all");
  sheet.getRange("ES1:ES3").values = [
    ["A01 时间标签说明"],
    ["原模板标签整体后移10分钟；本文件纠正为自然日00:00-24:00。"],
    ["输入按对应槽右端点离散；这是冻结工作口径，不是官方勘误。"],
  ];
  sheet.getRange("ES1").format.font = { bold: true };
  sheet.getRange("ES2:ES3").format.wrapText = false;
  sheet.getRange("ES1:ES3").format.columnWidth = 60;
}
fillPlanSheet(original, "original_purchase_kwh", "original_total_kwh");
fillPlanSheet(adjusted, "effective_purchase_kwh", "effective_total_kwh");

const templateBlock = storage.getRange("A2:F7");
for (let day = 1; day < 334; day += 1) storage.getRangeByIndexes(1 + day * 6, 0, 6, 6).copyFrom(templateBlock, "all");
storage.getRange("A2:F2005").clear({ applyTo: "contents" });
const storageMatrix = [];
for (let day = 0; day < 334; day += 1) {
  const rows = payload.storage_four_hour.slice(day * 6, day * 6 + 6);
  for (let block = 0; block < 6; block += 1) {
    const row = rows[block];
    storageMatrix.push([
      block === 0 ? asDate(row.date) : null, row.interval, row.charge_kwh, row.discharge_kwh,
      block === 0 ? "0:00" : block === 1 ? "24:00" : null,
      block === 0 ? row.soc_open_day_kwh : block === 1 ? row.soc_close_day_kwh : null,
    ]);
  }
}
storage.getRange("A2:F2005").values = storageMatrix;
storage.getRange("A2:A2005").format.numberFormat = "m/d/yy";
storage.getRange("C2:D2005").format.numberFormat = "0.0000";
storage.getRange("F2:F2005").format.numberFormat = "0.0000";
storage.getRange("A2:F2005").format.font = { name: "Arial", size: 10, bold: false };

const events = payload.emergency_events;
const lastEventRow = Math.max(11, events.length + 1);
for (let row = 3; row <= events.length + 1; row += 1) emergency.getRange(`A${row}:C${row}`).copyFrom(emergency.getRange("A2:C2"), "all");
emergency.getRange(`A2:C${lastEventRow}`).clear({ applyTo: "contents" });
if (events.length) {
  emergency.getRange(`A2:C${events.length + 1}`).values = events.map((row) => [asDate(row.date), row.interval, row.purchase_kwh]);
  emergency.getRange(`A2:A${events.length + 1}`).format.numberFormat = "m/d/yy";
  emergency.getRange(`C2:C${events.length + 1}`).format.numberFormat = "0.0000";
  emergency.getRange(`A2:C${events.length + 1}`).format.font = { name: "Arial", size: 10, bold: false };
}

workbook.recalculate();
await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.mkdir(path.dirname(validationPath), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
await (await SpreadsheetFile.exportXlsx(workbook)).save(outputPath);

const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const savedOriginal = saved.worksheets.getItem("计划购电量");
const savedAdjusted = saved.worksheets.getItem("调整购电量");
const savedStorage = saved.worksheets.getItem("充放电量");
const savedEmergency = saved.worksheets.getItem("紧急购电量");
const originalValues = savedOriginal.getRange("B2:EO335").values.flat().map(Number);
const adjustedValues = savedAdjusted.getRange("B2:EO335").values.flat().map(Number);
const storageValues = savedStorage.getRange("A2:F2005").values;
const eventValues = events.length ? savedEmergency.getRange(`A2:C${events.length + 1}`).values : [];
const expectedSoc = payload.storage_four_hour.flatMap((row, idx) => idx % 6 === 0 ? [row.soc_open_day_kwh] : idx % 6 === 1 ? [row.soc_close_day_kwh] : []);
const savedSoc = storageValues.flatMap((row, idx) => idx % 6 < 2 ? [Number(row[5])] : []);
const eventKeysExact = eventValues.every((row, idx) => isoDate(row[0]) === events[idx].date && row[1] === events[idx].interval);

const inspections = {};
for (const [name, options] of Object.entries({
  original_head: { kind: "table", sheetId: "计划购电量", range: "A1:H5", include: "values,formulas", tableMaxRows: 5, tableMaxCols: 8, maxChars: 6000 },
  original_tail: { kind: "table", sheetId: "计划购电量", range: "EM1:ES4", include: "values,formulas", tableMaxRows: 4, tableMaxCols: 7, maxChars: 6000 },
  adjusted_head: { kind: "table", sheetId: "调整购电量", range: "A1:H5", include: "values,formulas", tableMaxRows: 5, tableMaxCols: 8, maxChars: 6000 },
  adjusted_tail: { kind: "table", sheetId: "调整购电量", range: "EM1:ES4", include: "values,formulas", tableMaxRows: 4, tableMaxCols: 7, maxChars: 6000 },
  storage_head: { kind: "table", sheetId: "充放电量", range: "A1:F13", include: "values,formulas", tableMaxRows: 13, tableMaxCols: 6, maxChars: 6000 },
  storage_tail: { kind: "table", sheetId: "充放电量", range: "A1994:F2005", include: "values,formulas", tableMaxRows: 12, tableMaxCols: 6, maxChars: 6000 },
  emergency_head: { kind: "table", sheetId: "紧急购电量", range: `A1:C${Math.min(12, events.length + 1)}`, include: "values,formulas", tableMaxRows: 12, tableMaxCols: 3, maxChars: 6000 },
  formula_errors: { kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: `${variant} final formula error scan`, maxChars: 6000 },
})) inspections[name] = (await saved.inspect(options)).ndjson;

const renderJobs = [
  ["计划购电量", "A1:Q8", `${variant}_original_head.png`, 1.2], ["计划购电量", "EM1:ES5", `${variant}_original_tail.png`, 1.5],
  ["调整购电量", "A1:Q8", `${variant}_adjusted_head.png`, 1.2], ["调整购电量", "EM1:ES5", `${variant}_adjusted_tail.png`, 1.5],
  ["充放电量", "A1:F13", `${variant}_storage_head.png`, 1.5], ["充放电量", "A1994:F2005", `${variant}_storage_tail.png`, 1.5],
  ["紧急购电量", `A1:C${Math.min(16, events.length + 1)}`, `${variant}_emergency_head.png`, 1.5],
  ["紧急购电量", `A${Math.max(1, events.length - 10)}:C${events.length + 1}`, `${variant}_emergency_tail.png`, 1.5],
];
for (const [sheetName, range, fileName, scale] of renderJobs) {
  const image = await saved.render({ sheetName, range, scale, format: "png" });
  await fs.writeFile(path.join(previewDir, fileName), new Uint8Array(await image.arrayBuffer()));
}

const checks = {
  sheet_names_exact: [0, 1, 2, 3].map((idx) => saved.worksheets.getItemAt(idx).name).join("|") === "计划购电量|调整购电量|充放电量|紧急购电量",
  corrected_headers_exact: savedOriginal.getRange("B1:EO1").values[0].every((value, idx) => value === naturalLabels[idx]) && savedAdjusted.getRange("B1:EO1").values[0].every((value, idx) => value === naturalLabels[idx]),
  max_original_plan_difference_kwh: maxAbs(originalValues, payload.plans.flatMap((row) => row.original_purchase_kwh)),
  max_effective_plan_difference_kwh: maxAbs(adjustedValues, payload.plans.flatMap((row) => row.effective_purchase_kwh)),
  max_original_total_difference_kwh: maxAbs(savedOriginal.getRange("EP2:EP335").values.flat(), payload.plans.map((row) => row.original_total_kwh)),
  max_effective_total_difference_kwh: maxAbs(savedAdjusted.getRange("EP2:EP335").values.flat(), payload.plans.map((row) => row.effective_total_kwh)),
  max_original_cost_difference_yuan: maxAbs(savedOriginal.getRange("EQ2:EQ335").values.flat(), payload.plans.map((row) => row.total_cost_yuan)),
  max_adjusted_cost_difference_yuan: maxAbs(savedAdjusted.getRange("EQ2:EQ335").values.flat(), payload.plans.map((row) => row.total_cost_yuan)),
  storage_rows: storageValues.length,
  max_storage_charge_difference_kwh: maxAbs(storageValues.map((row) => row[2]), payload.storage_four_hour.map((row) => row.charge_kwh)),
  max_storage_discharge_difference_kwh: maxAbs(storageValues.map((row) => row[3]), payload.storage_four_hour.map((row) => row.discharge_kwh)),
  max_storage_soc_difference_kwh: maxAbs(savedSoc, expectedSoc),
  emergency_rows: eventValues.length, emergency_keys_exact: eventKeysExact,
  max_emergency_amount_difference_kwh: maxAbs(eventValues.map((row) => row[2]), events.map((row) => row.purchase_kwh)),
  a01_disclosure_visible: [savedOriginal, savedAdjusted].every((sheet) => sheet.getRange("ES1:ES3").values.flat().every((value) => typeof value === "string" && value.length > 0)),
};
const numericChecks = Object.entries(checks).filter(([key]) => key.startsWith("max_")).map(([, value]) => value);
const validation = { schema_version: 1, question, workbook: `results/${variant}.xlsx`, source_template: `source_materials/C题/附件/附件5/${variant}.xlsx`, status: "PASS", checks, inspections, previews: renderJobs.map(([, , name]) => `previews/${name}`) };
if (!checks.sheet_names_exact || !checks.corrected_headers_exact || !checks.emergency_keys_exact || !checks.a01_disclosure_visible || checks.storage_rows !== 2004 || checks.emergency_rows !== events.length || numericChecks.some((value) => value > 1e-7)) validation.status = "FAIL";
await fs.writeFile(validationPath, JSON.stringify(validation, null, 2), "utf8");
console.log(JSON.stringify({ status: validation.status, output: outputPath, checks }));
if (validation.status !== "PASS") process.exitCode = 1;
