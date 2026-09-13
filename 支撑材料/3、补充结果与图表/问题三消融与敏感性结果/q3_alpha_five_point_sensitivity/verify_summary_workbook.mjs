import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbookPath = "D:/2026数模/审题codex/experiments/q3_alpha_five_point_sensitivity/results/q3_alpha_five_point_summary.xlsx";
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const summary = workbook.worksheets.getItem("敏感性汇总");
const checks = workbook.worksheets.getItem("复算校验");
const summaryValues = summary.getRange("A4:J9").values;
const checkValues = checks.getRange("A3:H10").values;
const noFormulaError = [...summaryValues.flat(), ...checkValues.flat()].every((value) => typeof value !== "string" || !value.startsWith("#"));
const titleOK = summary.getRange("A1").values[0][0] === "Q3 负载反馈系数 α 五点敏感性汇总";
const alpha05Row = summary.getRange("A7:J7").values[0];
const alpha05OK = Number(alpha05Row[0]) === 0.5 && alpha05Row[9] === "PASS";
const result = { status: noFormulaError && titleOK && alpha05OK ? "PASS" : "FAIL", noFormulaError, titleOK, alpha05OK, sheets: [summary.name, checks.name] };
await fs.writeFile("D:/2026数模/审题codex/experiments/q3_alpha_five_point_sensitivity/validation/q3_alpha_five_point_workbook_validation.json", JSON.stringify(result, null, 2), "utf8");
console.log(JSON.stringify(result));
if (result.status !== "PASS") process.exitCode = 1;
