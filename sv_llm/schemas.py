"""Typed contracts exchanged between agents.

Every agent returns one of these models as JSON. Keeping the contracts explicit lets the
supervisor reason about state without parsing free text, and lets tests assert on structure.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Severity(StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class Threat(BaseModel):
    id: str = Field(description="Short identifier such as T1, T2.")
    title: str
    category: str = Field(
        description="STRIDE category or hardware-specific class, e.g. information disclosure, "
        "privilege escalation, tampering, denial of service."
    )
    asset: str = Field(description="The protected asset, e.g. 'AES key register bank'.")
    entry_point: str = Field(description="Interface or signal an attacker would use.")
    description: str
    spec_refs: list[str] = Field(default_factory=list, description="Spec sections cited.")


class ThreatList(BaseModel):
    threats: list[Threat]


class Finding(BaseModel):
    id: str = Field(description="Short identifier such as F1, F2.")
    threat_id: str | None = Field(default=None, description="Threat this finding realises.")
    title: str
    severity: Severity
    module: str
    location: str = Field(description="Signal, register or line reference in the RTL.")
    description: str
    cwe: str | None = Field(default=None, description="Hardware CWE identifier, e.g. CWE-1244.")
    recommendation: str


class FindingList(BaseModel):
    findings: list[Finding]


class AssertionCheck(BaseModel):
    finding_id: str
    name: str
    sva: str = Field(description="A SystemVerilog assertion that would catch the issue.")
    description: str


class ValidationVerdict(BaseModel):
    finding_id: str
    status: Literal["confirmed", "rejected", "needs_review"]
    rationale: str


class ValidationResult(BaseModel):
    checks: list[AssertionCheck] = Field(default_factory=list)
    verdicts: list[ValidationVerdict] = Field(default_factory=list)
    needs_revision: bool = Field(
        default=False,
        description="True when the validator wants the detection agent to re-analyse the RTL.",
    )
    revision_notes: str = ""


class Report(BaseModel):
    design_name: str
    iterations: int
    threats: list[Threat]
    findings: list[Finding]
    validation: ValidationResult | None
    trace: list[str]
