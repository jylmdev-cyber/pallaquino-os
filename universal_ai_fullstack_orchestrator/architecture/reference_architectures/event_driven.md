# Reference architecture: Event Driven

Each event has an owning domain, versioned schema and delivery semantics. Use transactional outbox where database change and publication must agree; consumers are idempotent and replayable.

This is a decision aid, not a mandatory blueprint. Select it only after repository,
domain, risk and capability analysis; record material deviations as ADRs.
