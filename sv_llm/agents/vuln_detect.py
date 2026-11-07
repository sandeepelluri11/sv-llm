from __future__ import annotations

import json

from sv_llm.agents.base import BaseAgent
from sv_llm.retrieval.store import format_context
from sv_llm.schemas import FindingList
from sv_llm.state import VerificationState

SYSTEM_PROMPT = """You are the vulnerability-detection agent of SV-LLM, a hardware security \
verification system for SoC designs. Given the threat model and the RTL, find places where the \
implementation fails to enforce the specification.

Look for classic hardware weaknesses: lock or write-once registers that can be re-written, \
debug or test interfaces that bypass access checks, secrets readable through unprivileged \
address ranges, reset values that leave protections disabled, missing privilege checks on \
bus transactions, state machines with reachable unsafe states, and timing or arbitration \
logic an attacker can starve. Reference the RTL by module and signal, map each finding to a \
threat id when one applies, and attach a hardware CWE id when you are confident.

Reply with ONLY a JSON object of the form {"findings": [Finding, ...]} where Finding has the \
keys id, threat_id, title, severity (critical|high|medium|low|info), module, location, \
description, cwe, recommendation."""


class VulnerabilityAgent(BaseAgent):
    name = "vuln_detect"
    system_prompt = SYSTEM_PROMPT

    def __call__(self, state: VerificationState) -> dict:
        threats = state.get("threats", [])
        rtl = state.get("rtl_text", "")
        validation = state.get("validation") or {}
        revision_notes = validation.get("revision_notes", "") if validation else ""

        threat_summary = "\n".join(
            f"- {t['id']}: {t['title']} (asset: {t['asset']}, entry: {t['entry_point']})"
            for t in threats
        )
        query = " ".join(t["asset"] + " " + t["entry_point"] for t in threats) or rtl[:400]
        retrieved = format_context(self.retrieve(query, kind="rtl"))
        rtl_context = "\n\n".join(retrieved) if retrieved else rtl

        prompt_parts = [
            f"Design under verification: {state.get('design_name', 'unknown')}",
            "Threat model:\n" + (threat_summary or "(none provided)"),
            "RTL under analysis:\n" + rtl_context,
        ]
        if revision_notes:
            prompt_parts.append(
                "The validation agent reviewed your previous findings and asked for a "
                f"revision:\n{revision_notes}\n\nPrevious findings:\n"
                + json.dumps(state.get("findings", []), indent=1)
            )
        examples = self.few_shot_block(rtl + " " + threat_summary)
        if examples:
            prompt_parts.append(examples)
        prompt_parts.append("Report the vulnerabilities you can substantiate as JSON.")

        result, messages = self.structured_call(FindingList, "\n\n".join(prompt_parts))
        findings = [f.model_dump(mode="json") for f in result.findings]
        iteration = int(state.get("iteration", 0)) + 1
        return {
            "findings": findings,
            "validation": None,
            "iteration": iteration,
            "trace": [f"vuln_detect: iteration {iteration} produced {len(findings)} findings"],
            "messages": messages,
            "next_agent": "",
        }
