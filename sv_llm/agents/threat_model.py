from __future__ import annotations

from sv_llm.agents.base import BaseAgent
from sv_llm.retrieval.store import format_context
from sv_llm.schemas import ThreatList
from sv_llm.state import VerificationState

SYSTEM_PROMPT = """You are the threat-modeling agent of SV-LLM, a hardware security verification \
system for SoC designs. You read the security specification of a design and enumerate the \
threats that matter for its protected assets.

Work asset-first: identify every security asset the spec names (keys, lock bits, privileged \
registers, boot state, debug ports), then for each asset list how an attacker could reach it \
through the module interfaces. Use STRIDE categories or hardware-specific classes such as \
privilege escalation, information disclosure, tampering, or denial of service. Cite the spec \
sections you relied on.

Reply with ONLY a JSON object of the form {"threats": [Threat, ...]} where Threat has the keys \
id, title, category, asset, entry_point, description, spec_refs."""


class ThreatModelAgent(BaseAgent):
    name = "threat_model"
    system_prompt = SYSTEM_PROMPT

    def __call__(self, state: VerificationState) -> dict:
        spec = state.get("spec_text", "")
        query = f"security assets, access control, lock, key, privileged, debug {spec[:400]}"
        retrieved = format_context(self.retrieve(query, kind="spec"))
        context = "\n\n".join(retrieved) if retrieved else spec

        prompt_parts = [
            f"Design under verification: {state.get('design_name', 'unknown')}",
            "Security specification excerpts:\n" + context,
        ]
        examples = self.few_shot_block(spec)
        if examples:
            prompt_parts.append(examples)
        prompt_parts.append("Enumerate the threats for this design as JSON.")

        result, messages = self.structured_call(ThreatList, "\n\n".join(prompt_parts))
        threats = [t.model_dump() for t in result.threats]
        return {
            "threats": threats,
            "context": retrieved,
            "trace": [f"threat_model: identified {len(threats)} threats"],
            "messages": messages,
            "next_agent": "",
        }
