"""Render the final state as a Markdown verification report."""

from __future__ import annotations

from sv_llm.schemas import Finding, Report, Threat, ValidationResult
from sv_llm.state import VerificationState

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def build_report(state: VerificationState) -> Report:
    validation = state.get("validation")
    return Report(
        design_name=state.get("design_name", "unknown"),
        iterations=int(state.get("iteration", 0)),
        threats=[Threat.model_validate(t) for t in state.get("threats", [])],
        findings=sorted(
            (Finding.model_validate(f) for f in state.get("findings", [])),
            key=lambda f: _SEVERITY_ORDER.get(f.severity.value, 9),
        ),
        validation=ValidationResult.model_validate(validation) if validation else None,
        trace=list(state.get("trace", [])),
    )


def render_markdown(report: Report) -> str:
    verdicts = {v.finding_id: v for v in (report.validation.verdicts if report.validation else [])}
    checks: dict[str, list] = {}
    if report.validation:
        for check in report.validation.checks:
            checks.setdefault(check.finding_id, []).append(check)

    confirmed = sum(1 for v in verdicts.values() if v.status == "confirmed")
    lines = [
        f"# SV-LLM security verification report: `{report.design_name}`",
        "",
        f"- Detection iterations: {report.iterations}",
        f"- Threats modelled: {len(report.threats)}",
        f"- Findings: {len(report.findings)} ({confirmed} confirmed by the validation agent)",
        "",
        "## Threat model",
        "",
        "| ID | Title | Category | Asset | Entry point |",
        "|---|---|---|---|---|",
    ]
    for t in report.threats:
        lines.append(f"| {t.id} | {t.title} | {t.category} | {t.asset} | {t.entry_point} |")

    lines += ["", "## Findings", ""]
    if not report.findings:
        lines.append("No findings were reported.")
    for f in report.findings:
        verdict = verdicts.get(f.id)
        status = verdict.status if verdict else "unvalidated"
        lines += [
            f"### {f.id} - {f.title}",
            "",
            f"- Severity: **{f.severity.value}** | Status: **{status}**"
            + (f" | {f.cwe}" if f.cwe else "")
            + (f" | realises {f.threat_id}" if f.threat_id else ""),
            f"- Location: `{f.module}` / `{f.location}`",
            "",
            f.description,
            "",
            f"**Recommendation.** {f.recommendation}",
        ]
        if verdict:
            lines += ["", f"**Validator rationale.** {verdict.rationale}"]
        for check in checks.get(f.id, []):
            lines += [
                "",
                f"**Assertion `{check.name}`.** {check.description}",
                "",
                "```systemverilog",
                check.sva.strip(),
                "```",
            ]
        lines.append("")

    if report.validation and report.validation.revision_notes:
        lines += ["## Validator notes", "", report.validation.revision_notes, ""]

    lines += ["## Agent trace", ""]
    lines += [f"{i + 1}. {step}" for i, step in enumerate(report.trace)]
    lines.append("")
    return "\n".join(lines)
