# Checkpoint protocol

After each stable milestone, capture timestamp, task, confirmed stage, Git HEAD/diff summary, locks, tests/evidence, assumptions, open questions and checksum. Write atomically. Recovery chooses the newest valid checkpoint and labels artifact-derived inference RECONSTRUCTED.
