import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = "D:/2026数模/审题codex";
const variant = process.env.BUILD_VARIANT || "result2";
const question = variant === "result4-2" ? "Q4-2" : "Q2";
const payloadStem = variant === "result4-2" ? "q4_2" : "q2";
const templatePath = path.join(root, "source_materials", "C题", "附件", "附件5", `${variant}.xlsx`);
const payloadPath = path.join(root, "intermediate", `${payloadStem}_workbook_payload.json`);
const outputPath = path.join(root, "results", `${variant}.xlsx`);
const validationPath = path.join(root, "validation", `${variant}_workbook_validation.json`);
const previewDir = path.join(root, "previews");

const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
if (payload.plans.length !== 334) throw new Error(`Q2 plan days must be 334, got ${payload.plans.length}`);
if (payload.storage_four_hour.length !== 334 * 6) throw new Error("Q2 storage payload must be 2004 rows");

const naturalLabel = (slot) => {
  const fmt = (minute) => minute === 1440 ? "24:00" : `${String(Math.floor(minute / 60)).padStart(2, "0")}:${String(minute % 60).padStart(2, "0")}`;
  return `${fmt(slot * 10)}-${fmt((slot + 1) * 10)}`;
};
const asDate = (iso) => new Date(`${iso}T00:00:00`);
const isoDate = (value) => {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === "number") return new Date(Date.UTC(1899, 11, 30) + value * 86400000).toISOString().slice(0, 10);
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? String(value).slice(0, 10) : parsed.toISOString().slice(0, 10);
};
const maxAbs = (a, b) => Math.max(0, ...a.map((value, idx) => Math.abs(Number(value) - Number(b[idx]))));

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(templatePath));
const plan = workbook.worksheets.getItem("计划购电量");
const storage = workbook.worksheets.getItem("充放电量");
const emergency = workbook.worksheets.getItem("紧急购电量");

plan.getRange("B1:EO1").values = [[...Array.from({ length: 144 }, (_, slot) => naturalLabel(slot))]];
plan.getRange("A2:A335").values = payload.plans.map((row) => [asDate(row.date)]);
plan.getRange("B2:EO335").values = payload.plans.map((row) => row.purchase_kwh);
plan.getRange("EP2:EP335").values = payload.plans.map((row) => [row.total_purchase_kwh]);
plan.getRange("EQ2:EQ335").values = payload.plans.map((row) => [row.total_cost_yuan]);
plan.getRange("A2:A335").format.numberFormat = "m/d/yy";
plan.getRange("B2:EP335").format.numberFormat = "0.0000";
plan.getRange("EQ2:EQ335").format.numberFormat = "0.00";
plan.getRange("ES1").copyFrom(plan.getRange("A1"), "all");
plan.getRange("ES2:ES3").copyFrom(plan.getRange("A2"), "all");
plan.getRange("ES1:ES3").values = [
  ["A01 时间标签说明"],
  ["原模板标签整体后移10分钟；本文件纠正为自然日00:00-24:00。"],
  ["输入按对应槽右端点离散；这是冻结工作口径，不是官方勘误。"],
];
plan.getRange("ES1").format.font = { bold: true };
plan.getRange("ES2:ES3").format.wrapText = false;
plan.getRange("ES1:ES3").format.columnWidth = 60;

const templateStorageBlock = storage.getRange("A2:F7");
for (let day = 1; day < 334; day += 1) {
  storage.getRangeByIndexes(1 + day * 6, 0, 6, 6).copyFrom(templateStorageBlock, "all");
}
storage.getRange("A2:F2005").clear({ applyTo: "contents" });
const storageMatrix = [];
for (let day = 0; day < 334; day += 1) {
  const rows = payload.storage_four_hour.slice(day * 6, day * 6 + 6);
  for (let block = 0; block < 6; block += 1) {
    const row = rows[block];
    storageMatrix.push([
      block === 0 ? asDate(row.date) : null,
      row.interval,
      row.charge_kwh,
      row.discharge_kwh,
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

const eventRows = payload.emergency_events;
const emergencyLastRow = Math.max(11, eventRows.length + 1);
for (let row = 3; row <= eventRows.length + 1; row += 1) {
  emergency.getRange(`A${row}:C${row}`).copyFrom(emergency.getRange("A2:C2"), "all");
}
emergency.getRange(`A2:C${emergencyLastRow}`).clear({ applyTo: "contents" });
if (eventRows.length) {
  emergency.getRange(`A2:C${eventRows.length + 1}`).values = eventRows.map((row) => [
    asDate(row.date), row.interval, row.purchase_kwh,
  ]);
  emergency.getRange(`A2:A${eventRows.length + 1}`).format.numberFormat = "m/d/yy";
  emergency.getRange(`C2:C${eventRows.length + 1}`).format.numberFormat = "0.0000";
  emergency.getRange(`A2:C${eventRows.length + 1}`).format.font = { name: "Arial", size: 10, bold: false };
}

workbook.recalculate();
await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.mkdir(path.dirname(validationPath), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);

const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const savedPlan = saved.worksheets.getItem("计划购电量");
const savedStorage = saved.worksheets.getItem("充放电量");
const savedEmergency = saved.worksheets.getItem("紧急购电量");
const savedPlanValues = savedPlan.getRange("B2:EO335").values;
const expectedPlanFlat = payload.plans.flatMap((row) => row.purchase_kwh);
const savedPlanFlat = savedPlanValues.flat().map(Number);
const savedTotals = savedPlan.getRange("EP2:EP335").values.flat().map(Number);
const savedCosts = savedPlan.getRange("EQ2:EQ335").values.flat().map(Number);
const savedStorageValues = savedStorage.getRange("A2:F2005").values;
const savedEventValues = eventRows.length ? savedEmergency.getRange(`A2:C${eventRows.length + 1}`).values : [];

const savedStorageCharge = savedStorageValues.map((row) => Number(row[2]));
const savedStorageDischarge = savedStorageValues.map((row) => Number(row[3]));
const savedStorageSoc = savedStorageValues.flatMap((row, idx) => idx % 6 < 2 ? [Number(row[5])] : []);
const expectedStorageSoc = payload.storage_four_hour.flatMap((row, idx) => idx % 6 === 0 ? [row.soc_open_day_kwh] : idx % 6 === 1 ? [row.soc_close_day_kwh] : []);
const eventKeysExact = savedEventValues.every((row, idx) => isoDate(row[0]) === eventRows[idx].date && row[1] === eventRows[idx].interval);

const inspections = {};
for (const [name, options] of Object.entries({
  plan_head: { kind: "table", sheetId: "计划购电量", range: "A1:H5", include: "values,formulas", tableMaxRows: 5, tableMaxCols: 8, maxChars: 6000 },
  plan_tail: { kind: "table", sheetId: "计划购电量", range: "EM1:ES4", include: "values,formulas", tableMaxRows: 4, tableMaxCols: 7, maxChars: 6000 },
  storage_head: { kind: "table", sheetId: "充放电量", range: "A1:F13", include: "values,formulas", tableMaxRows: 13, tableMaxCols: 6, maxChars: 6000 },
  storage_tail: { kind: "table", sheetId: "充放电量", range: "A1994:F2005", include: "values,formulas", tableMaxRows: 12, tableMaxCols: 6, maxChars: 6000 },
  emergency_head: { kind: "table", sheetId: "紧急购电量", range: `A1:C${Math.min(12, eventRows.length + 1)}`, include: "values,formulas", tableMaxRows: 12, tableMaxCols: 3, maxChars: 6000 },
  formula_errors: { kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: `${variant} final formula error scan`, maxChars: 6000 },
})) {
  inspections[name] = (await saved.inspect(options)).ndjson;
}

const renderJobs = [
  ["计划购电量", "A1:Q8", `${variant}_plan_head.png`, 1.2],
  ["计划购电量", "EM1:ES5", `${variant}_plan_tail.png`, 1.5],
  ["充放电量", "A1:F13", `${variant}_storage_head.png`, 1.5],
  ["充放电量", "A1994:F2005", `${variant}_storage_tail.png`, 1.5],
  ["紧急购电量", `A1:C${Math.min(16, eventRows.length + 1)}`, `${variant}_emergency_head.png`, 1.5],
  ["紧急购电量", `A${Math.max(1, eventRows.length - 10)}:C${eventRows.length + 1}`, `${variant}_emergency_tail.png`, 1.5],
];
for (const [sheetName, range, fileName, scale] of renderJobs) {
  const image = await saved.render({ sheetName, range, scale, format: "png" });
  await fs.writeFile(path.join(previewDir, fileName), new Uint8Array(await image.arrayBuffer()));
}

const checks = {
  sheet_names_exact: [0, 1, 2].map((idx) => saved.worksheets.getItemAt(idx).name).join("|") === "计划购电量|充放电量|紧急购电量",
  plan_days: savedPlanValues.length,
  plan_slot_columns: savedPlanValues[0].length,
  corrected_first_label: savedPlan.getRange("B1").values[0][0],
  corrected_last_label: savedPlan.getRange("EO1").values[0][0],
  max_plan_difference_kwh: maxAbs(savedPlanFlat, expectedPlanFlat),
  max_daily_total_difference_kwh: maxAbs(savedTotals, payload.plans.map((row) => row.total_purchase_kwh)),
  max_daily_cost_difference_yuan: maxAbs(savedCosts, payload.plans.map((row) => row.total_cost_yuan)),
  storage_rows: savedStorageValues.length,
  max_storage_charge_difference_kwh: maxAbs(savedStorageCharge, payload.storage_four_hour.map((row) => row.charge_kwh)),
  max_storage_discharge_difference_kwh: maxAbs(savedStorageDischarge, payload.storage_four_hour.map((row) => row.discharge_kwh)),
  max_storage_soc_difference_kwh: maxAbs(savedStorageSoc, expectedStorageSoc),
  emergency_rows: savedEventValues.length,
  emergency_event_keys_exact: eventKeysExact,
  max_emergency_amount_difference_kwh: maxAbs(savedEventValues.map((row) => Number(row[2])), eventRows.map((row) => row.purchase_kwh)),
  a01_disclosure_visible: savedPlan.getRange("ES1:ES3").values.flat().every((value) => typeof value === "string" && value.length > 0),
};
const validation = {
  schema_version: 1,
  question,
  workbook: `results/${variant}.xlsx`,
  source_template: `source_materials/C题/附件/附件5/${variant}.xlsx`,
  status: "PASS",
  checks,
  inspections,
  previews: renderJobs.map(([, , fileName]) => `previews/${fileName}`),
};
const booleans = [checks.sheet_names_exact, checks.emergency_event_keys_exact, checks.a01_disclosure_visible];
const numerics = [
  checks.max_plan_difference_kwh, checks.max_daily_total_difference_kwh, checks.max_daily_cost_difference_yuan,
  checks.max_storage_charge_difference_kwh, checks.max_storage_discharge_difference_kwh,
  checks.max_storage_soc_difference_kwh, checks.max_emergency_amount_difference_kwh,
];
if (!booleans.every(Boolean) || numerics.some((value) => value > 1e-7) || checks.plan_days !== 334 || checks.plan_slot_columns !== 144 || checks.storage_rows !== 2004 || checks.emergency_rows !== eventRows.length || checks.corrected_first_label !== "00:00-00:10" || checks.corrected_last_label !== "23:50-24:00") {
  validation.status = "FAIL";
}
await fs.writeFile(validationPath, JSON.stringify(validation, null, 2), "utf8");
console.log(JSON.stringify({ status: validation.status, output: outputPath, checks }));
if (validation.status !== "PASS") process.exitCode = 1;
