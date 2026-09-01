# Reference architecture: Mobile Backend

The mobile client is an untrusted intermittently connected replica. Backend contracts are versioned; local operations have identity, conflict and retry rules; tokens and sensitive data use platform storage.

This is a decision aid, not a mandatory blueprint. Select it only after repository,
domain, risk and capability analysis; record material deviations as ADRs.
