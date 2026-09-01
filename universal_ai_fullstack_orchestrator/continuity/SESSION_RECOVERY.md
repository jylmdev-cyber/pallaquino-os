# Session recovery

Recover in order from repository map, Git HEAD/status/diff, migrations, test and
gate evidence, pipeline state, newest checksum-valid checkpoint, handoff and logs.
Prefer confirmed facts. Label every artifact-derived conclusion `RECONSTRUCTED`
with confidence, and never infer that a test passed from code or prose. Fall back
to the previous valid checkpoint when the newest one is corrupt.

