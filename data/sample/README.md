# Synthetic bank corpus

This corpus is fictional and contains no customer, employee, or company data. It
exists to exercise retrieval quality, authorization boundaries, recursive research,
and prompt-injection controls.

`manifest.json` is the ingestion authority. Each document declares a stable ID,
version, tenant, department, type, access level, creation date, and source URI.
The source files cover policies, architecture, payment and non-payment incidents,
runbooks, product specifications, meeting notes, exact error codes, semantic
paraphrases, restricted material, and an explicitly malicious retrieved-text fixture.

`evaluation.json` records initial relevance expectations. It is not used as training
data and does not automatically become ground truth; changes require review.

The checked-in `data/index/bm25.json` parameters are fitted to the exact chunks from
this corpus version. Any material corpus or chunking change requires regeneration,
re-ingestion, and retrieval-evaluation comparison.
