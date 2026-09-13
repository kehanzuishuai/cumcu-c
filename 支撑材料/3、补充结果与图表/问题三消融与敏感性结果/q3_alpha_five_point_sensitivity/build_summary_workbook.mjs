import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const experimentRoot = "D:/2026数模/审题codex/experiments/q3_alpha_five_point_sensitivity";
const csvPath = `${experimentRoot}/results/q3_alpha_five_point_summary.csv`;
const validationPath = `${experimentRoot}/validation/q3_alpha_five_point_validation.json`;
const outPath = `${experimentRoot}/results/q3_alpha_five_point_summary.xlsx`;
const previewPath = `${experimentRoot}/intermediate/q3_alpha_five_point_summary_preview.png`;
const inspectPath = `${experimentRoot}/intermediate/q3_alpha_five_point_workbook_inspect.json`;

function parseCsv(text) {
  const [header, ...lines] = text.trim().split(/\r?\n/);
  const fields = header.replace(/^\uFEFF/, "").split(",");
  return lines.map((line) => Object.fromEntries(line.split(",").map((value, index) => [fields[index], value])));
}

const rows = parseCsv(await fs.readFile(csvPath, "utf8"));
const validation = JSON.parse(await fs.readFile(validationPath, "utf8"));
const workbook = Workbook.create();
const summary = workbook.worksheets.add("敏感性汇总");
const checks = workbook.worksheets.add("复算校验");
for (const sheet of [summary, checks]) sheet.showGridLines = false;

summary.getRange("A1:J1").merge();
summary.getRange("A1").values = [["Q3 负载反馈系数 α 五点敏感性汇总"]];
summary.getRange("A1").format = { font: { name: "Arial", size: 14, bold: true, color: "#17365D" }, horizontalAlignment: "left", verticalAlignment: "center" };
summary.getRange("A2:J2").merge();
summary.getRange("A2").values = [["范围：2025-02-01 至 2025-12-31；除 α 外，均沿用冻结 Q3 的 Q80 修正、0/6/12/18 更新、储能与 A08 主结算口径。"]];
summary.getRange("A2").format = { font: { name: "Arial", size: 10, italic: true, color: "#595959" }, horizontalAlignment: "left", verticalAlignment: "center" };
const headers = [["α", "正常购电费用\n(元)", "购电调整费用\n(元)", "紧急购电费用\n(元)", "总购电费用\n(元)", "紧急购电量\n(kWh)", "期末 SOC\n(kWh)", "分项复算总费\n(元)", "复算差\n(元)", "校验状态"]];
summary.getRange("A4:J4").values = headers;
summary.getRange("A4:J4").format = { fill: "#1F4E78", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true, borders: { preset: "outside", style: "thin", color: "#1F4E78" } };
summary.getRange("A5:G9").values = rows.map((r) => [
  Number(r.alpha), Number(r.normal_purchase_cost_yuan), Number(r.purchase_adjustment_cost_yuan),
  Number(r.emergency_purchase_cost_yuan), Number(r.total_purchase_cost_yuan), Number(r.emergency_purchase_kwh),
  Number(r.terminal_soc_kwh),
] );
summary.getRange("H5").formulas = [["=B5+C5+D5"]];
summary.getRange("H5:H9").fillDown();
summary.getRange("I5").formulas = [["=H5-E5"]];
summary.getRange("I5:I9").fillDown();
summary.getRange("J5:J9").values = rows.map((r) => [r.validation_status]);
summary.getRange("A5:J9").format = { font: { name: "Arial", size: 10, color: "#222222" }, verticalAlignment: "center", borders: { preset: "insideHorizontal", style: "thin", color: "#D9E2F3" } };
summary.getRange("A5:A9").format.horizontalAlignment = "center";
summary.getRange("B5:I9").format.horizontalAlignment = "right";
summary.getRange("J5:J9").format.horizontalAlignment = "center";
summary.getRange("B5:E9").format.numberFormat = "#,##0.00;[Red]-#,##0.00";
summary.getRange("F5:I9").format.numberFormat = "#,##0.0000;[Red]-#,##0.0000";
summary.getRange("A5:A9").format.numberFormat = "0.00";
summary.getRange("A5:J9").conditionalFormats.add("Custom", { formula: "=$A5=0.5", format: { fill: "#E2F0D9", font: { bold: true, color: "#1F1F1F" } } });
summary.getRange("A11:J11").merge();
summary.getRange("A11").values = [["口径说明：正常购电费用为 0 时原计划购电费；购电调整费用为 1.5 倍上调结算费减 0.5 倍下调退款；三项之和为总购电费用。"]];
summary.getRange("A11").format = { font: { name: "Arial", size: 10, italic: true, color: "#595959" }, horizontalAlignment: "left", verticalAlignment: "center", wrapText: true };
summary.getRange("A12:J12").merge();
summary.getRange("A12").values = [["绿色行表示冻结正式主模型 α=0.50；本工作簿仅用于敏感性展示，不构成主模型晋级或替换。"]];
summary.getRange("A12").format = { font: { name: "Arial", size: 10, italic: true, color: "#595959" }, horizontalAlignment: "left", verticalAlignment: "center" };
summary.getRange("A1:J12").format.font = { name: "Arial", size: 10 };
summary.getRange("A1").format.font = { name: "Arial", size: 14, bold: true, color: "#17365D" };
summary.getRange("A1:J1").format.rowHeight = 26;
summary.getRange("A2:J2").format.rowHeight = 24;
summary.getRange("A4:J4").format.rowHeight = 32;
summary.getRange("A11:J11").format.rowHeight = 28;
summary.getRange("A12:J12").format.rowHeight = 20;
for (const [column, width] of [["A:A", 9], ["B:E", 18], ["F:G", 16], ["H:I", 17], ["J:J", 12]]) summary.getRange(column).format.columnWidth = width;
summary.freezePanes.freezeRows(4);

checks.getRange("A1:H1").merge();
checks.getRange("A1").values = [["Q3 五点敏感性复算与约束校验"]];
checks.getRange("A1").format = { font: { name: "Arial", size: 14, bold: true, color: "#17365D" }, horizontalAlignment: "left", verticalAlignment: "center" };
checks.getRange("A3:H3").values = [["α", "费用复算", "信息截止", "供需平衡", "SOC 连续", "功率上限", "充放互斥", "总体状态"]];
checks.getRange("A3:H3").format = { fill: "#1F4E78", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", borders: { preset: "outside", style: "thin", color: "#1F4E78" } };
const checkRows = rows.map((r) => {
  const item = validation.per_alpha[`alpha_${Number(r.alpha).toFixed(2)}`].checks;
  return [Number(r.alpha), item.pass_flags.cost_reconciliation ? "PASS" : "FAIL", item.pass_flags.information_cutoff ? "PASS" : "FAIL", item.pass_flags.actual_balance ? "PASS" : "FAIL", item.pass_flags.crossday_soc ? "PASS" : "FAIL", item.pass_flags.storage_power ? "PASS" : "FAIL", item.pass_flags.mutual_exclusion ? "PASS" : "FAIL", item.status];
});
checks.getRange("A4:H8").values = checkRows;
checks.getRange("A4:H8").format = { font: { name: "Arial", size: 10, color: "#222222" }, horizontalAlignment: "center", verticalAlignment: "center", borders: { preset: "insideHorizontal", style: "thin", color: "#D9E2F3" } };
checks.getRange("A4:A8").format.numberFormat = "0.00";
checks.getRange("A10:H10").merge();
checks.getRange("A10").values = [[`α=0.50 与冻结正式 Q3 逐项复现：${validation.alpha_0_5_reproduces_frozen_main.pass ? "PASS" : "FAIL"}；正式 Q3 保护文件哈希未变：${validation.formal_q3_files_unchanged ? "PASS" : "FAIL"}。`]];
checks.getRange("A10").format = { font: { name: "Arial", size: 10, italic: true, color: "#595959" }, horizontalAlignment: "left", verticalAlignment: "center" };
checks.getRange("A1:H10").format.font = { name: "Arial", size: 10 };
checks.getRange("A1").format.font = { name: "Arial", size: 14, bold: true, color: "#17365D" };
checks.getRange("A1:H1").format.rowHeight = 26;
checks.getRange("A3:H3").format.rowHeight = 24;
checks.getRange("A10:H10").format.rowHeight = 22;
checks.getRange("A:A").format.columnWidth = 10;
checks.getRange("B:H").format.columnWidth = 15;
checks.freezePanes.freezeRows(3);

workbook.recalculate();
const inspect = await workbook.inspect({ kind: "table,region", sheetId: "敏感性汇总", range: "A1:J12", maxChars: 6000, tableMaxRows: 12, tableMaxCols: 10 });
await fs.writeFile(inspectPath, JSON.stringify(inspect, null, 2), "utf8");
const preview = await workbook.render({ sheetName: "敏感性汇总", autoCrop: "all", scale: 1, format: "png" });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outPath);
console.log(JSON.stringify({ status: "PASS", workbook: outPath, preview: previewPath }));
