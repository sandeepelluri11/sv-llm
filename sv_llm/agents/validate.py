from __future__ import annotations

import json

from sv_llm.agents.base import BaseAgent
from sv_llm.schemas import ValidationResult
from sv_llm.state import VerificationState

SYSTEM_PROMPT = """You are the validation agent of SV-LLM, a hardware security verification \
system for SoC designs. You independently review the findings produced by the detection agent \
against the RTL and the specification.

For every finding decide whether it is confirmed (the RTL really violates the spec), rejected \
(a false positive, explain why), or needs_review (plausible but not provable from the excerpt). \
For every confirmed finding write a SystemVerilog assertion (SVA) that would catch the \
violation in simulation or formal. If the detection agent missed a threat that clearly has no \
finding, or if several findings are duplicates or unsupported, set needs_revision to true and \
explain what should change in revision_notes.

Reply with ONLY a JSON object with keys checks (list of {finding_id, name, sva, description}), \
verdicts (list of {finding_id, status, rationale}), needs_revision (bool), revision_notes."""


class ValidationAgent(BaseAgent):
    name = "validate"
    system_prompt = SYSTEM_PROMPT

    def __call__(self, state: VerificationState) -> dict:
        findings = state.get("findings", [])
        threats = state.get("threats", [])
        covered = {f.get("threat_id") for f in findings}
        uncovered = [t for t in threats if t["id"] not in covered]

        prompt = "\n\n".join(
            [
                f"Design under verification: {state.get('design_name', 'unknown')}",
                "Specification:\n" + state.get("spec_text", ""),
                "RTL:\n" + state.get("rtl_text", ""),
                "Findings to validate:\n" + json.dumps(findings, indent=1),
                "Threats with no finding yet:\n"
                + ("\n".join(f"- {t['id']}: {t['title']}" for t in uncovered) or "(none)"),
                "Validate the findings as JSON.",
            ]
        )
        result, messages = self.structured_call(ValidationResult, prompt)
        confirmed = sum(1 for v in result.verdicts if v.status == "confirmed")
        return {
            "validation": result.model_dump(mode="json"),
            "trace": [
                f"validate: {confirmed}/{len(result.verdicts)} findings confirmed, "
                f"{len(result.checks)} assertions, needs_revision={result.needs_revision}"
            ],
            "messages": messages,
            "next_agent": "",
        }
