# Seed snapshot

`scamwatch_2026-11-02.sql.gz` is a `pg_dump` of the collection database on 2026-11-02 (schema and
data: 4,986 domains, 5,874 sightings, 1,162 scam texts, 481 registry lookups, 222 collector runs).

The scheduled workflow loads it once, into an empty hosted database, so first-seen dates and the
reviewed stream are not lost when collection moves from a laptop to the cloud. After that the
database only grows; this file is never loaded again.

Everything in it comes from the public sources listed in the main README. Links are stored raw for
analysis; the dashboard and outputs only ever show them defanged.
