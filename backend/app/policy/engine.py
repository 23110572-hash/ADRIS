from dataclasses import dataclass
from typing import Any

from app.agents.state import SignalState

POLICY_VERSION = "adris-risk-policy-v1.0.0"
FIXED_SAFETY_ACTIONS = [
    "Do not transfer money or make a verification payment.",
    "Do not disclose OTPs, PINs, passwords, CVVs, or screen access.",
    "End the interaction if it is safe to do so.",
    "Contact 1930, your bank using its official number, or a trusted person.",
    "Preserve messages and payment details; do not alter original evidence.",
]


@dataclass(frozen=True)
class PolicyDecision:
    risk_band: str
    reason_codes: list[str]
    coverage: dict[str, Any]
    missing_sources: list[str]
    agent_disagreement: bool
    explanation: str
    safety_actions: list[str]


HIGH_SEVERITY_EXACT_CODES = {"AUTHORIZED_HIGH_SEVERITY_EXACT_MATCH"}


def decide_risk(
    *,
    signals: list[SignalState],
    input_quality: str,
    unavailable_sources: list[str],
    agent_disagreement: bool,
) -> PolicyDecision:
    active = [signal for signal in signals if signal.confidence >= 0.60]
    strong = [signal for signal in active if signal.strength == "STRONG" and signal.confidence >= 0.80]
    strong_families = sorted({signal.family for signal in strong})
    reason_codes = list(dict.fromkeys(signal.code for signal in sorted(active, key=lambda item: item.severity, reverse=True)))
    groq_failed = any(source.startswith("GROQ_") for source in unavailable_sources)
    workflow_failed = any(source.startswith("WORKFLOW_") for source in unavailable_sources)
    exact_authorized = any(signal.code in HIGH_SEVERITY_EXACT_CODES for signal in active)
    quality_passed = input_quality == "PASSED"

    if input_quality in {"LOW_QUALITY", "UNSUPPORTED"}:
        band = "UNABLE_TO_ASSESS"
        reason_codes = reason_codes or ["INPUT_QUALITY_INSUFFICIENT"]
    elif workflow_failed and not strong:
        band = "UNABLE_TO_ASSESS"
        reason_codes = reason_codes or ["ANALYSIS_WORKFLOW_FAILED"]
    elif exact_authorized and quality_passed and not agent_disagreement:
        band = "HIGH_RISK"
        reason_codes.insert(0, "AUTHORIZED_HIGH_SEVERITY_MATCH")
    elif len(strong_families) >= 2 and quality_passed and not agent_disagreement and not groq_failed:
        band = "HIGH_RISK"
    elif strong or input_quality == "PARTIAL" or unavailable_sources or agent_disagreement:
        band = "CAUTION"
        if agent_disagreement:
            reason_codes.append("AGENT_DISAGREEMENT")
        if groq_failed:
            reason_codes.append("AI_ANALYSIS_UNAVAILABLE")
        if input_quality == "PARTIAL":
            reason_codes.append("INCOMPLETE_EVIDENCE")
    elif quality_passed:
        band = "NO_STRONG_SIGNAL"
        reason_codes = ["NO_STRONG_SIGNAL_DETECTED"]
    else:
        band = "UNABLE_TO_ASSESS"
        reason_codes = ["INSUFFICIENT_COVERAGE"]

    reason_codes = list(dict.fromkeys(reason_codes))
    if band == "HIGH_RISK":
        explanation = "Multiple independent strong risk-signal families were detected in the submitted evidence."
    elif band == "CAUTION":
        explanation = "Suspicious signals or important coverage gaps were found. Pause and verify through official channels."
    elif band == "NO_STRONG_SIGNAL":
        explanation = "No strong risk signal was detected in the supported input. This does not prove the interaction is legitimate."
    else:
        explanation = "ADRIS could not assess the submission reliably. Treat unresolved requests cautiously and use official channels."

    return PolicyDecision(
        risk_band=band,
        reason_codes=reason_codes,
        coverage={
            "input_quality": input_quality,
            "active_signal_count": len(active),
            "strong_signal_families": strong_families,
            "deterministic_policy": True,
            "groq_available": not groq_failed,
        },
        missing_sources=list(dict.fromkeys(unavailable_sources)),
        agent_disagreement=agent_disagreement,
        explanation=explanation,
        safety_actions=FIXED_SAFETY_ACTIONS,
    )
