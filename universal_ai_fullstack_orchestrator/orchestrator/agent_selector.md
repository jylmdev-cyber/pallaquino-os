# Agent selector

Filter out deprecated agents, agents lacking required capability, or agents whose
`risk_limit` is below task risk. Score: domain 35, capability 30, technology 15,
required-skill coverage 10, review/write suitability 10, then subtract context
cost. Tie-break by priority and ID. Return score and rationale; do not select every
agent merely because a request is ambiguous.
