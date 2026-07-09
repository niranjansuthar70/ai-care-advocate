from __future__ import annotations

from pcp_agent.state import NextAction, PCPCaseState


def contact_patient(state: PCPCaseState, action: NextAction) -> dict:
    draft = _build_message(state, action)
    return {
        "patient_informed": True,
        "patient_message_draft": draft,
    }


def _build_message(state: PCPCaseState, action: NextAction) -> str:
    patient = state["patient_id"].replace("-", " ").title()
    equipment = state["equipment"]
    code = state["billing_code"]
    pcp = state["pcp_name"]

    if action == NextAction.DONE:
        return (
            f"Hello {patient}, this is Maya from care coordination. "
            f"Good news — {pcp} has signed the written order for your {equipment} "
            f"(billing code {code}). We are moving forward with Medicare Part B coordination."
        )

    if action == NextAction.REJECTED:
        return (
            f"Hello {patient}, this is Maya from care coordination. "
            f"We found a billing code issue on your DME order from {pcp}. "
            f"Our team is working with the office to correct it before submission to Medicare."
        )

    if action == NextAction.GIVE_UP:
        return (
            f"Hello {patient}, this is Maya from care coordination. "
            f"After multiple follow-up attempts we have not been able to obtain a signed "
            f"written order for your {equipment} from {pcp}. "
            f"A care advocate will call you to discuss next steps."
        )

    raise ValueError(f"contact_patient does not apply to action: {action}")
