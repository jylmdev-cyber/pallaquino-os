# Capability detection protocol

Run `scripts/detect_capabilities.py` at session start. Each capability is `true`,
`false` or `null` (not detectable), with evidence. Detection is observational and
does not grant authorization. When shell or a runtime is absent, adapt the plan
and label gates unexecuted; never simulate success. Provider declarations may
inform probing but runtime evidence wins. Re-detect after provider/environment
handoff.
