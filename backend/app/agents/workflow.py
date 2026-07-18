import hashlib
import json
import time
from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy import func, select

from app.agents.groq_client import structured_groq_call
from app.agents.schemas import CitizenSafetyOutput, ScamAnalysisOutput, SupervisorOutput, TriageOutput
from app.agents.state import (
    AgentRunRef,
    GeoSummary,
    IncidentState,
    RelationshipState,
    SignalState,
    TriageResult,
)
from app.common.config import get_settings
from app.db.models import AgentRun, GeoAggregate, Incident, Indicator
from app.db.session import SessionLocal
from app.policy.engine import decide_risk

settings = get_settings()
AGENT_VERSION = "adris-agents-v1.0.0"
PROMPT_VERSIONS = {
    "SUPERVISOR": "supervisor-v1",
    "TRIAGE": "triage-v1",
    "FORENSICS": "forensics-v1",
    "SCAM_ANALYSIS": "scam-analysis-v1",
    "GRAPH": "graph-intelligence-v1",
    "GEO": "geospatial-v1",
    "EVIDENCE": "evidence-v1",
    "CITIZEN_SAFETY": "citizen-safety-v1",
}
TOOL_VERSIONS = {
    "entity_extraction": "deterministic-extractors-v1.0.0",
    "graph_query": "allowlisted-graph-query-v1",
    "geo_query": "h3-aggregate-query-v1",
    "risk_policy": "adris-risk-policy-v1.0.0",
}
ALLOWED_LLM_SIGNALS = {
    "FAKE_AUTHORITY_CLAIM": "AUTHORITY_IMPERSONATION",
    "DIGITAL_ARREST_CLAIM": "AUTHORITY_IMPERSONATION",
    "URGENCY_PRESSURE": "URGENCY",
    "THREAT_OR_INTIMIDATION": "THREAT_COERCION",
    "SECRECY_OR_ISOLATION": "ISOLATION",
    "VERIFICATION_TRANSFER_REQUEST": "PAYMENT_COERCION",
    "CREDENTIAL_REQUEST": "CREDENTIAL_THEFT",
    "REMOTE_ACCESS_REQUEST": "DEVICE_CONTROL",
}
BLOCKED_CITIZEN_PHRASES = ("completely safe", "confirmed criminal", "definitely legitimate", "definitely a scammer")


def _coerce(state: IncidentState | dict[str, Any]) -> IncidentState:
    return state if isinstance(state, IncidentState) else IncidentState.model_validate(state)


def _hash_input(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _start_run(state: IncidentState, agent_name: str, model_provider: str = "DETERMINISTIC") -> tuple[AgentRun, float]:
    with SessionLocal() as db:
        incident = db.get(Incident, state.incident_id)
        run = AgentRun(
            incident_id=state.incident_id,
            agent_name=agent_name,
            status="STARTED",
            model_provider=model_provider,
            model_name=settings.groq_model if model_provider == "GROQ" else None,
            model_version=settings.groq_model if model_provider == "GROQ" else "rules-v1",
            prompt_version=PROMPT_VERSIONS[agent_name],
            agent_version=AGENT_VERSION,
            tool_versions=TOOL_VERSIONS,
            input_hash=_hash_input(
                {
                    "artifact_references": state.artifact_references,
                    "text_hashes": [_hash_input(text) for text in state.extracted_text],
                    "indicator_hashes": [item.normalized_value_hash for item in state.indicators],
                }
            ),
            correlation_id=incident.correlation_id if incident else None,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        db.expunge(run)
    return run, time.perf_counter()


def _finish_run(
    run: AgentRun,
    started: float,
    *,
    status: str,
    output: dict[str, Any],
    error_code: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    model_name: str | None = None,
) -> AgentRunRef:
    with SessionLocal() as db:
        stored = db.get(AgentRun, run.id)
        if stored is None:
            raise RuntimeError("AGENT_RUN_NOT_FOUND")
        stored.status = status
        stored.structured_output = output
        stored.error_code = error_code
        stored.completed_at = datetime.now(UTC)
        stored.latency_ms = int((time.perf_counter() - started) * 1000)
        stored.input_tokens = input_tokens
        stored.output_tokens = output_tokens
        if model_name:
            stored.model_name = model_name
            stored.model_version = model_name
        db.commit()
    return AgentRunRef(run_id=str(run.id), agent_name=run.agent_name, status=status)


def _skip(state: IncidentState, name: str) -> dict[str, Any]:
    run, started = _start_run(state, name)
    ref = _finish_run(run, started, status="SKIPPED", output={"reason": "Not selected by supervisor"})
    return {"agent_runs": [*state.agent_runs, ref]}


def supervisor_node(raw_state: IncidentState | dict[str, Any]) -> dict[str, Any]:
    state = _coerce(raw_state)
    run, started = _start_run(state, "SUPERVISOR")
    selected = ["TRIAGE", "FORENSICS", "SCAM_ANALYSIS", "GRAPH", "EVIDENCE", "CITIZEN_SAFETY"]
    missing: list[str] = []
    with SessionLocal() as db:
        incident = db.get(Incident, state.incident_id)
        if incident and incident.coarse_h3_cell:
            selected.append("GEO")
        else:
            missing.append("COARSE_LOCATION_NOT_PROVIDED")
    output = SupervisorOutput(selected_agents=selected, missing_information=missing)
    ref = _finish_run(run, started, status="COMPLETED", output=output.model_dump(mode="json"))
    return {
        "selected_agents": output.selected_agents,
        "unavailable_sources": [*state.unavailable_sources, *missing],
        "agent_runs": [*state.agent_runs, ref],
    }


def triage_node(raw_state: IncidentState | dict[str, Any]) -> dict[str, Any]:
    state = _coerce(raw_state)
    if "TRIAGE" not in state.selected_agents:
        return _skip(state, "TRIAGE")
    run, started = _start_run(state, "TRIAGE", "GROQ")
    deterministic_codes = {signal.code for signal in state.scam_signals}
    fallback = TriageOutput(
        priority="P1_ACTIVE_THREAT" if {"LEGAL_THREAT", "DIGITAL_ARREST_CLAIM"} & deterministic_codes else "P3_STANDARD",
        suspected_type="DIGITAL_ARREST" if "DIGITAL_ARREST_CLAIM" in deterministic_codes else "UNCLEAR",
        payment_requested=bool({"PAYMENT_URGENCY", "SAFE_ACCOUNT_TRANSFER"} & deterministic_codes),
        active_threat="LEGAL_THREAT" in deterministic_codes,
        isolation_language_detected="SECRECY_ISOLATION" in deterministic_codes,
        immediate_guidance_required=bool(deterministic_codes),
        confidence=0.72 if deterministic_codes else 0.35,
    )
    unavailable = list(state.unavailable_sources)
    try:
        evidence = "\n".join(f"[extracted_text:{index}] {text}" for index, text in enumerate(state.extracted_text))
        result = structured_groq_call(
            output_model=TriageOutput,
            system_prompt=(
                "You are the ADRIS Triage Agent. Identify only suspected scam category, immediate payment danger, active threats, "
                "isolation language, and review priority. Do not decide the final risk band and do not accuse any person."
            ),
            evidence=evidence,
            max_tokens=500,
        )
        output = result.output
        assert isinstance(output, TriageOutput)
        ref = _finish_run(
            run,
            started,
            status="COMPLETED",
            output=output.model_dump(mode="json"),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            model_name=result.model,
        )
    except Exception as exc:
        output = fallback
        unavailable.append("GROQ_TRIAGE_UNAVAILABLE")
        ref = _finish_run(
            run,
            started,
            status="DEGRADED",
            output=output.model_dump(mode="json"),
            error_code=type(exc).__name__,
        )
    return {
        "triage_result": TriageResult.model_validate(output.model_dump()),
        "unavailable_sources": list(dict.fromkeys(unavailable)),
        "agent_runs": [*state.agent_runs, ref],
    }


def forensics_node(raw_state: IncidentState | dict[str, Any]) -> dict[str, Any]:
    state = _coerce(raw_state)
    if "FORENSICS" not in state.selected_agents:
        return _skip(state, "FORENSICS")
    run, started = _start_run(state, "FORENSICS")
    total_chars = sum(len(text.strip()) for text in state.extracted_text)
    unavailable = list(state.unavailable_sources)
    if total_chars >= 8:
        quality = "PASSED"
    elif state.indicators:
        quality = "PARTIAL"
        unavailable.append("LIMITED_EXTRACTED_TEXT")
    elif state.artifact_references:
        quality = "LOW_QUALITY"
        unavailable.append("ARTIFACT_EXTRACTION_EMPTY")
    else:
        quality = "UNSUPPORTED"
        unavailable.append("NO_SUPPORTED_INPUT")
    output = {"input_quality": quality, "unavailable_sources": list(dict.fromkeys(unavailable))}
    ref = _finish_run(run, started, status="COMPLETED", output=output)
    return {"input_quality": quality, "unavailable_sources": output["unavailable_sources"], "agent_runs": [*state.agent_runs, ref]}


def scam_analysis_node(raw_state: IncidentState | dict[str, Any]) -> dict[str, Any]:
    state = _coerce(raw_state)
    if "SCAM_ANALYSIS" not in state.selected_agents:
        return _skip(state, "SCAM_ANALYSIS")
    use_groq = not any(source.startswith("GROQ_") for source in state.unavailable_sources)
    run, started = _start_run(state, "SCAM_ANALYSIS", "GROQ" if use_groq else "DETERMINISTIC")
    signals = list(state.scam_signals)
    disagreement = False
    unavailable = list(state.unavailable_sources)
    if use_groq:
        try:
            valid_refs = {signal.evidence_reference for signal in signals}
            valid_refs.update(f"extracted_text:{index}" for index in range(len(state.extracted_text)))
            evidence = "\n".join(f"[extracted_text:{index}] {text}" for index, text in enumerate(state.extracted_text))
            result = structured_groq_call(
                output_model=ScamAnalysisOutput,
                system_prompt=(
                    "You are the ADRIS Scam Analysis Agent. Detect only government impersonation, fake digital-arrest claims, "
                    "urgency, threats, secrecy, isolation, payment coercion, credential requests, and remote-access requests. "
                    f"Use only these signal codes and their meanings: {json.dumps(ALLOWED_LLM_SIGNALS)}. "
                    f"Every factual signal must cite one of these evidence references: {sorted(valid_refs)}."
                ),
                evidence=evidence,
                max_tokens=900,
            )
            output = result.output
            assert isinstance(output, ScamAnalysisOutput)
            existing = {(item.code, item.evidence_reference) for item in signals}
            for candidate in output.signals:
                expected_family = ALLOWED_LLM_SIGNALS.get(candidate.code)
                if expected_family is None or candidate.family != expected_family or candidate.evidence_reference not in valid_refs:
                    continue
                if (candidate.code, candidate.evidence_reference) in existing:
                    continue
                signals.append(
                    SignalState(
                        **candidate.model_dump(),
                        source="GROQ_STRUCTURED",
                        agent_run_id=str(run.id),
                    )
                )
            disagreement = output.disagreement_with_triage
            ref = _finish_run(
                run,
                started,
                status="COMPLETED",
                output={"accepted_signal_count": len(signals), "agent_disagreement": disagreement},
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                model_name=result.model,
            )
        except Exception as exc:
            unavailable.append("GROQ_SCAM_ANALYSIS_UNAVAILABLE")
            ref = _finish_run(
                run,
                started,
                status="DEGRADED",
                output={"deterministic_signal_count": len(signals)},
                error_code=type(exc).__name__,
            )
    else:
        ref = _finish_run(run, started, status="DEGRADED", output={"deterministic_signal_count": len(signals)}, error_code="GROQ_SKIPPED_AFTER_FAILURE")
    return {
        "scam_signals": signals,
        "agent_disagreement": disagreement,
        "unavailable_sources": list(dict.fromkeys(unavailable)),
        "agent_runs": [*state.agent_runs, ref],
    }


def graph_node(raw_state: IncidentState | dict[str, Any]) -> dict[str, Any]:
    state = _coerce(raw_state)
    if "GRAPH" not in state.selected_agents:
        return _skip(state, "GRAPH")
    run, started = _start_run(state, "GRAPH")
    matches: list[RelationshipState] = []
    with SessionLocal() as db:
        for indicator in state.indicators[:50]:
            related = db.execute(
                select(Indicator.incident_id, func.count(Indicator.id))
                .where(
                    Indicator.indicator_type == indicator.indicator_type,
                    Indicator.normalized_value_hash == indicator.normalized_value_hash,
                    Indicator.incident_id != state.incident_id,
                    Indicator.status == "ACTIVE",
                )
                .group_by(Indicator.incident_id)
                .limit(20)
            ).all()
            for incident_id, count in related:
                matches.append(
                    RelationshipState(
                        source_id=f"incident:{state.incident_id}",
                        target_id=f"incident:{incident_id}",
                        relationship_type=f"SHARED_{indicator.indicator_type}",
                        explanation=f"Incidents contain the same governed {indicator.indicator_type.lower()} indicator.",
                        occurrence_count=int(count) + 1,
                    )
                )
    ref = _finish_run(run, started, status="COMPLETED", output={"match_count": len(matches)})
    return {"graph_matches": matches, "agent_runs": [*state.agent_runs, ref]}


def geo_node(raw_state: IncidentState | dict[str, Any]) -> dict[str, Any]:
    state = _coerce(raw_state)
    if "GEO" not in state.selected_agents:
        return _skip(state, "GEO")
    run, started = _start_run(state, "GEO")
    with SessionLocal() as db:
        incident = db.get(Incident, state.incident_id)
        aggregate = None
        if incident and incident.coarse_h3_cell:
            aggregate = db.scalar(
                select(GeoAggregate)
                .where(GeoAggregate.h3_cell == incident.coarse_h3_cell, GeoAggregate.status == "CURRENT")
                .order_by(GeoAggregate.period_end.desc())
            )
        summary = GeoSummary(
            h3_cell=incident.coarse_h3_cell if incident else None,
            incident_count=aggregate.incident_count if aggregate and not aggregate.suppressed else 0,
            trend_ratio=aggregate.trend_ratio if aggregate and not aggregate.suppressed else None,
            suppressed=aggregate.suppressed if aggregate else True,
        )
    ref = _finish_run(run, started, status="COMPLETED", output=summary.model_dump(mode="json"))
    return {"geographic_summary": summary, "agent_runs": [*state.agent_runs, ref]}


def evidence_node(raw_state: IncidentState | dict[str, Any]) -> dict[str, Any]:
    state = _coerce(raw_state)
    if "EVIDENCE" not in state.selected_agents:
        return _skip(state, "EVIDENCE")
    run, started = _start_run(state, "EVIDENCE")
    chronology = [
        {"event": "INCIDENT_RECEIVED", "reference": f"incident:{state.incident_id}"},
        *({"event": "ARTIFACT_PRESERVED", "reference": ref} for ref in state.artifact_references),
        *({"event": "SIGNAL_RECORDED", "reference": signal.evidence_reference} for signal in state.scam_signals),
    ]
    draft = {
        "schema_version": "evidence-manifest-v1",
        "incident_id": state.incident_id,
        "chronology": chronology,
        "limitations": [
            "The package records ADRIS processing and provenance but does not guarantee legal admissibility.",
            "Unavailable sources are recorded and are not treated as negative matches.",
        ],
    }
    ref = _finish_run(run, started, status="COMPLETED", output={"chronology_entries": len(chronology)})
    return {"evidence_manifest_draft": draft, "agent_runs": [*state.agent_runs, ref]}


def policy_node(raw_state: IncidentState | dict[str, Any]) -> dict[str, Any]:
    state = _coerce(raw_state)
    decision = decide_risk(
        signals=state.scam_signals,
        input_quality=state.input_quality,
        unavailable_sources=state.unavailable_sources,
        agent_disagreement=state.agent_disagreement,
    )
    return {
        "final_risk_band": decision.risk_band,
        "policy_reason_codes": decision.reason_codes,
        "policy_coverage": decision.coverage,
        "proposed_explanation": decision.explanation,
        "safety_actions": decision.safety_actions,
        "unavailable_sources": decision.missing_sources,
    }


def citizen_safety_node(raw_state: IncidentState | dict[str, Any]) -> dict[str, Any]:
    state = _coerce(raw_state)
    if "CITIZEN_SAFETY" not in state.selected_agents:
        return _skip(state, "CITIZEN_SAFETY")
    use_groq = not any(source.startswith("GROQ_") for source in state.unavailable_sources)
    run, started = _start_run(state, "CITIZEN_SAFETY", "GROQ" if use_groq else "DETERMINISTIC")
    explanation = state.proposed_explanation or "Use official channels to verify this request."
    unavailable = list(state.unavailable_sources)
    if use_groq:
        try:
            result = structured_groq_call(
                output_model=CitizenSafetyOutput,
                system_prompt=(
                    "You are the ADRIS Citizen Safety Agent. Explain the supplied structured outcome plainly and non-accusatorily. "
                    "Never say an interaction is completely safe, declare anyone guilty, guarantee legitimacy, or replace the fixed actions."
                ),
                evidence=json.dumps(
                    {
                        "risk_band": state.final_risk_band,
                        "reason_codes": state.policy_reason_codes,
                        "coverage": state.policy_coverage,
                        "fixed_policy_explanation": explanation,
                    }
                ),
                max_tokens=500,
            )
            output = result.output
            assert isinstance(output, CitizenSafetyOutput)
            if not any(phrase in output.explanation.lower() for phrase in BLOCKED_CITIZEN_PHRASES):
                explanation = output.explanation
            ref = _finish_run(
                run,
                started,
                status="COMPLETED",
                output={"explanation": explanation, "template_actions_retained": True},
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                model_name=result.model,
            )
        except Exception as exc:
            unavailable.append("GROQ_CITIZEN_SAFETY_UNAVAILABLE")
            ref = _finish_run(run, started, status="DEGRADED", output={"fixed_template_used": True}, error_code=type(exc).__name__)
    else:
        ref = _finish_run(run, started, status="DEGRADED", output={"fixed_template_used": True}, error_code="GROQ_SKIPPED_AFTER_FAILURE")
    return {
        "proposed_explanation": explanation,
        "unavailable_sources": list(dict.fromkeys(unavailable)),
        "agent_runs": [*state.agent_runs, ref],
    }


def build_workflow():
    builder = StateGraph(IncidentState)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("triage", triage_node)
    builder.add_node("forensics", forensics_node)
    builder.add_node("scam_analysis", scam_analysis_node)
    builder.add_node("graph", graph_node)
    builder.add_node("geo", geo_node)
    builder.add_node("evidence", evidence_node)
    builder.add_node("policy", policy_node)
    builder.add_node("citizen_safety", citizen_safety_node)
    builder.add_edge(START, "supervisor")
    builder.add_edge("supervisor", "triage")
    builder.add_edge("triage", "forensics")
    builder.add_edge("forensics", "scam_analysis")
    builder.add_edge("scam_analysis", "graph")
    builder.add_edge("graph", "geo")
    builder.add_edge("geo", "evidence")
    builder.add_edge("evidence", "policy")
    builder.add_edge("policy", "citizen_safety")
    builder.add_edge("citizen_safety", END)
    return builder.compile()


WORKFLOW = build_workflow()


def run_incident_workflow(initial_state: IncidentState) -> IncidentState:
    result = WORKFLOW.invoke(initial_state.model_dump(mode="json"), config={"recursion_limit": settings.agent_max_steps})
    return IncidentState.model_validate(result)
