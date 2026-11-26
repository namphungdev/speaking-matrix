# speaking-matrix — Business Context Index

> Curated business knowledge, committed to git and searched via
> np-code-search. np-init creates this index and the domain skeletons ONCE —
> re-init never regenerates anything under `business/`.

## Domains

- [Lessons](lessons.md) — lesson catalogue, lesson status and progress
- [Flashcard Practice](flashcard-practice.md) — the 3-step flashcard flow over a lesson's sentences
- [Speaking Assessment](speaking-assessment.md) — recording the learner and scoring pronunciation
- [Identity & Access](identity-and-access.md) — user accounts and JWT authentication

## How entries work

- Add entries with `/np:np-context` or the `context_add_entry` tool
  (`kind=business`, `domain=<file stem>`); `BC-*` ids are minted automatically.
- Each entry is an anchored H2 section in its domain file:
  `## <Title> {#BC-YYYYMMDD-xxxx}` followed by a
  `<!-- np:entry id=... status=active updated=... source=... -->` metadata
  comment, then the body. The anchor makes entries citable from plans and
  reviews.
- Superseding flips `status=superseded` and truncates the body to one line —
  entries are never deleted.
