# Technical debt

- The wheel does not package framework data; non-editable installs rely on root discovery (ADR-0004). Packaging data is required before PyPI publication.
- The release ZIP is committed to Git; attaching it only to GitHub Releases would keep the repository small.
- The repository analyzer provides conservative API/database detection; ecosystem-specific analyzers can extend it without changing the map schema.
- Numeric performance budgets remain product-specific by design and must be filled during product planning.
- Three fitness rules (domain_no_infrastructure, frontend_no_database, module_boundaries) have no analyzer.
