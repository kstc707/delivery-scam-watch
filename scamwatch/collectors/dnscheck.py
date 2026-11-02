"""Confirm whether registered domains still exist, using DNS.

For each domain in `registrations`, ask Google Public DNS (DNS over HTTPS) for its name servers:
  NXDOMAIN (status 3)  the domain does not exist any more (deleted, expired or taken down)
  status 0             it exists and is delegated
  anything else        could not tell (stored as 'error' and retried later)
This corrects the registry (RDAP) answer, which proved unreliable for some endings, and catches
domains a registry still lists but has suspended so they no longer resolve.
"""

from __future__ import annotations

import psycopg

from ..http import Fetcher
from ..runlog import CollectorRun

DOH = "https://dns.google/resolve"


def classify(payload: dict) -> str:
    status = payload.get("Status")
    return "nxdomain" if status == 3 else "exists" if status == 0 else "error"


def collect_dnscheck(conn: psycopg.Connection, fetcher: Fetcher, limit: int = 500) -> None:
    with CollectorRun(conn, "dnscheck") as run:
        rows = conn.execute(
            """SELECT registered_domain FROM registrations
               WHERE dns_checked_at IS NULL OR dns_status = 'error' OR dns_checked_at < now() - interval '1 day'
               ORDER BY dns_checked_at NULLS FIRST LIMIT %s""",
            (limit,),
        ).fetchall()
        for (domain,) in rows:
            run.seen += 1
            try:
                status = classify(fetcher.get(DOH, params={"name": domain, "type": "NS"}).json())
            except Exception:  # noqa: BLE001
                status = "error"
            conn.execute(
                "UPDATE registrations SET dns_status = %s, dns_checked_at = now() WHERE registered_domain = %s",
                (status, domain),
            )
            run.new += status != "error"
        conn.commit()
