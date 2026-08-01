"""Nodes: critic, revise_itinerary, finalize_response (self-reflection loop).

The critic returns a structured evaluation (spec section 14). When it fails, the
revise node feeds the critique back into a regeneration pass. Revisions are
capped by settings.max_revisions so the loop always terminates.
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from common.config import settings
from common.logging_utils import get_logger, log_event
from common.schemas import CritiqueResult
from remote_agent_1.nodes.common import structured, text, trace
from remote_agent_1.nodes.itinerary import _format_context, _request_brief
from remote_agent_1.state import TravelState

logger = get_logger("agent1.critic")

CRITIC_SYSTEM = """\
You are a strict reviewer of travel itineraries. Evaluate the ITINERARY against
the REQUEST and the BUDGET VERDICT, then return the structured result.

Check each of these:
1. Does it answer what the traveller actually asked for?
2. Does the estimated total respect the stated budget? (Trust the BUDGET
   VERDICT — it was computed arithmetically, not estimated.)
3. Do the activities match the stated interests, and avoid what they dislike?
4. Is each day geographically coherent (no far-apart activities on one day)?
5. Are there unrealistic assumptions (impossible travel times, wrong season)?
6. Are uncertainties and estimate-vs-live-data caveats disclosed?
7. Is the pace consistent with what the traveller asked for?
8. Is the plan grounded in the provided context rather than invented?

Scoring:
- preference_match is 0.0 to 1.0.
- Put every concrete problem in `issues`, and an actionable fix for each in
  `recommendations`.
- Set relevant/budget_valid/feasible to false only for real problems, not for
  stylistic nitpicks. An itinerary with no budget stated has budget_valid=true.
"""


async def critic(state: TravelState) -> TravelState:
    """Evaluate the itinerary and record a structured critique."""
    if not state.get("preferences", {}).get("wants_itinerary", True):
        # Direct answers skip the itinerary critic.
        return {"critique": {"relevant": True, "budget_valid": True,
                             "feasible": True, "preference_match": 1.0,
                             "issues": [], "recommendations": [],
                             "skipped": "not an itinerary request"}}

    itinerary = state.get("itinerary", "")
    estimate = state.get("budget_estimate", {})
    budget_status = state.get("budget_status", "unknown")

    verdict_lines = [f"Computed total: ${estimate.get('total', 0):,.2f}"]
    if estimate.get("target_budget"):
        verdict_lines.append(f"Stated budget: ${estimate['target_budget']:,.2f}")
        verdict_lines.append(f"Difference: ${estimate.get('difference', 0):,.2f}")
    verdict_lines.append(f"Status: {budget_status.replace('_', ' ')}")

    result = await structured(CritiqueResult, [
        SystemMessage(content=CRITIC_SYSTEM),
        HumanMessage(content=(
            f"REQUEST:\n{_request_brief(state)}\n\n"
            f"BUDGET VERDICT:\n" + "\n".join(verdict_lines) + "\n\n"
            f"ITINERARY:\n{itinerary[:9000]}"
        )),
    ])

    if result is None:
        log_event(logger, "critic_failed")
        return {
            "critique": {"relevant": True, "budget_valid": budget_status != "over_budget",
                         "feasible": True, "preference_match": 0.7,
                         "issues": [], "recommendations": [],
                         "note": "critic unavailable"},
            "trace": trace(state, "Critic: unavailable, accepting itinerary"),
        }

    critique = result.model_dump()
    # The arithmetic verdict overrides the model's opinion on the budget.
    if budget_status == "over_budget":
        critique["budget_valid"] = False
        gap = state.get("budget_estimate", {}).get("difference", 0)
        message = (f"Estimated total exceeds the stated budget by "
                   f"${gap:,.2f} and must be optimised.")
        if message not in critique["issues"]:
            critique["issues"].insert(0, message)
    elif budget_status == "within_budget":
        critique["budget_valid"] = True

    passed = (critique["relevant"] and critique["budget_valid"]
              and critique["feasible"])
    log_event(logger, "critic_evaluated", passed=passed,
              preference_match=critique.get("preference_match"),
              issues=len(critique.get("issues", [])),
              iteration=state.get("iteration_count", 0))

    return {
        "critique": critique,
        "trace": trace(state, f"Critic: {'PASS' if passed else 'FAIL'} "
                              f"(preference match "
                              f"{critique.get('preference_match', 0):.0%}, "
                              f"{len(critique.get('issues', []))} issue(s))"),
    }


async def revise_itinerary(state: TravelState) -> TravelState:
    """Regenerate the itinerary addressing the critic's issues.

    When the problem is budget, this doubles as the budget-optimisation step:
    the prompt requires an explicit before/after savings summary (spec 13).
    """
    critique = state.get("critique", {})
    estimate = state.get("budget_estimate", {})
    budget = float(state.get("budget") or 0)
    iteration = state.get("iteration_count", 0) + 1

    issues = "\n".join(f"- {issue}" for issue in critique.get("issues", [])) or "- (none)"
    recs = "\n".join(f"- {rec}" for rec in critique.get("recommendations", [])) or "- (none)"

    optimisation_block = ""
    if state.get("budget_status") == "over_budget" and budget:
        original_total = estimate.get("total", 0)
        optimisation_block = f"""
BUDGET OPTIMISATION IS REQUIRED.
The current estimate is ${original_total:,.2f} against a target of ${budget:,.2f}
(over by ${estimate.get('difference', 0):,.2f}).

Reduce the total to at or below ${budget:,.2f} using these levers, in order of
preference: lower the hotel category or shift to a slightly less central area;
replace some paid activities with free alternatives; use public-transport passes
instead of taxis; rebalance dining toward markets and casual spots while keeping
one standout meal; and only if still needed, trim one day.

You MUST add this section immediately after the Estimated Budget table, using
the real numbers:

## Budget Optimisation
- Original Estimated Cost: ${original_total:,.2f}
- Target Budget: ${budget:,.2f}
- Difference: ${estimate.get('difference', 0):,.2f}
- Optimised Estimated Cost: $<new total>
- Savings: $<original minus new>

Then explain, in 3-5 bullets, exactly what you changed and what the traveller
gives up for each saving.
"""

    revised = await text([
        SystemMessage(content=(
            "You are revising a travel itinerary to fix reviewer findings. Keep "
            "everything that already works and keep the exact same section "
            "structure and markdown format. Fix only what the reviewer raised.\n"
            f"{optimisation_block}\n"
            "Stay grounded in the CONTEXT. Do not invent live availability or "
            "quote prices as live figures.\n\n"
            "CONTEXT:\n" + _format_context(state))),
        HumanMessage(content=(
            f"REQUEST:\n{_request_brief(state)}\n\n"
            f"REVIEWER ISSUES:\n{issues}\n\n"
            f"REVIEWER RECOMMENDATIONS:\n{recs}\n\n"
            f"CURRENT ITINERARY:\n{state.get('itinerary', '')[:9000]}"
        )),
    ], temperature=0.3)

    log_event(logger, "itinerary_revised", iteration=iteration,
              budget_status=state.get("budget_status"))
    return {
        "itinerary": revised,
        "iteration_count": iteration,
        "trace": trace(state, f"Revised itinerary (attempt {iteration} of "
                              f"{settings.max_revisions})"),
    }


def _sources_section(state: TravelState) -> str:
    lines: list[str] = []

    kb_sources = sorted({item.get("source") for item in state.get("retrieved_context", [])
                         if item.get("source")})
    if kb_sources:
        lines.append("**Destination guides:**")
        lines += [f"- {source}" for source in kb_sources]

    web = state.get("web_results", [])
    if web:
        lines.append("")
        lines.append("**Web search results:**")
        seen = set()
        for item in web:
            url = item.get("url")
            if url and url not in seen:
                seen.add(url)
                lines.append(f"- {item.get('title') or url} — {url}")

    policies = state.get("policy_context", [])
    if policies:
        lines.append("")
        lines.append("**Policy documents (illustrative samples):**")
        for policy in policies:
            lines.append(f"- {policy.get('policy_name')} "
                         f"(version {policy.get('version')}, "
                         f"effective {policy.get('effective_date')})")

    return "\n".join(lines)


async def finalize_response(state: TravelState) -> TravelState:
    """Assemble the final answer: itinerary + disclosures + sources."""
    itinerary = state.get("itinerary", "") or "No itinerary could be produced."
    parts = [itinerary]

    # Merge parse-time assumptions and any accumulated warnings.
    assumptions = state.get("assumptions", [])
    warnings = list(state.get("warnings", []))

    critique = state.get("critique", {})
    unresolved = critique.get("issues", []) if not (
        critique.get("relevant") and critique.get("budget_valid")
        and critique.get("feasible")
    ) else []

    if state.get("iteration_count", 0) >= settings.max_revisions and unresolved:
        warnings.append(
            f"The plan was revised {state['iteration_count']} times (the maximum) "
            "and some reviewer findings remain open — see below."
        )

    if assumptions:
        parts.append("## Additional Assumptions\n"
                     + "\n".join(f"- {a}" for a in assumptions))

    if warnings or unresolved:
        block = ["## System Notes and Open Issues"]
        block += [f"- {w}" for w in warnings]
        block += [f"- Unresolved reviewer finding: {issue}" for issue in unresolved]
        parts.append("\n".join(block))

    sources = _sources_section(state)
    if sources:
        parts.append("## Sources\n" + sources)

    parts.append(
        "---\n"
        "_Costs and availability here are planning estimates from sample travel "
        "data, not live prices — please confirm them before booking. Any policy "
        "details are illustrative samples rather than official airline, hotel, or "
        "government policy._"
    )

    final = "\n\n".join(part for part in parts if part and part.strip())
    log_event(logger, "response_finalized", chars=len(final),
              revisions=state.get("iteration_count", 0),
              web_used=state.get("web_used", False))

    return {
        "final_answer": final,
        "trace": trace(state, "Finalised response"),
    }
