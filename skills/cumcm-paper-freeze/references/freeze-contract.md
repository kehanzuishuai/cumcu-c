# 冻结计划契约

本契约只列待冻结文件和审核元数据；详细跨 Skill 状态见 `../../_shared/cumcm/interfaces.md`。所有路径相对 `PROJECT_ROOT`。

```json
{
  "schema_version": 1,
  "paper_ready_manifest": "handoff/paper_ready_manifest.json",
  "figure_manifest": "figure_manifest.json",
  "paper": "paper/final_paper.pdf",
  "source": "paper/paper.tex",
  "problem_files": ["problem/C题.pdf", "problem/附件1.xlsx"],
  "code": ["code"],
  "results": ["results"],
  "figures": ["figures"],
  "support": ["support", "support.zip"],
  "ai_declarations": ["support/AI 工具使用详情.pdf"],
  "additional_files": [],
  "required_files": [
    {"path": "results/result1.xlsx", "sheets": ["Sheet1"], "rows": {"Sheet1": 20}, "columns": {"Sheet1": 8}}
  ],
  "blockers": [],
  "audit_fields": {
    "ai_used": true,
    "has_support_materials": true,
    "uses_programs": true,
    "support_dir": "support",
    "support_archive": "support.zip",
    "forbidden_terms": [],
    "identity_terms": {},
    "terminology_groups": [],
    "latex": {"source": "paper/paper.tex", "engine": "xelatex", "timeout_seconds": 180, "args": []},
    "reproducibility": {}
  }
}
```

`code/results/figures/support/ai_declarations/additional_files` 的每项可为文件或目录；目录递归展开。脚本还会自动纳入两个上游 manifest 所引用的 final、合同、Brief、数据和图形输出；普通图脚本必需，流程图则必须纳入可编辑 `.pptx` 源文件，生成脚本仅在实际使用时纳入。重复路径只冻结一次。

`required_files` 保留审核所需的工作表、行列等约束，并由冻结脚本写入实际 SHA-256。`audit_fields` 只接受审核已有的可选字段，不能覆盖 `frozen`、`blockers`、论文路径、规范或上游来源。

`audit_fields.ai_used/has_support_materials/uses_programs` 必须显式为 `true/false`。最终 PDF 与论文源文件必须是两个不同文件，源文件限 `.tex/.docx/.md/.qmd/.typ/.odt`。`results`、`figures` 必须非空；`uses_programs: true` 时 `code` 必须非空；`has_support_materials` 必须与 `support` 是否非空一致。`ai_used: true` 时还必须满足 `has_support_materials: true`，并在 `ai_declarations` 中列出最终的 `AI 工具使用详情.pdf`；该详情在底稿和版面稳定后、执行冻结前补齐，不要求提前占用论文正文篇幅。若仍有 `blockers`、上游状态不正确、文件在项目根之外、hash 过期或目标目录已经存在，冻结失败且不生成正式包。
