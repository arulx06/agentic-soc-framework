import type { OrchestrationDecisionV1 } from "../../api/contracts";

/** A selected route exists only when the terminal backend contract says so. */
export function authoritativeRoute(decision: OrchestrationDecisionV1): string | null {
  return decision.outcome === "DECIDED" && decision.selected_route_id
    ? decision.selected_route_id
    : null;
}
