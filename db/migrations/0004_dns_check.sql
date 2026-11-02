-- 0004: confirm registry answers with DNS. A registry 'not found' turned out to be wrong for some
-- domain endings (the domain still resolved), and some 'registered' domains are suspended and no
-- longer resolve. The DNS answer for the domain's name servers settles it.

INSERT INTO sources (name, kind, terms_url, min_interval_seconds, enabled, notes) VALUES
  ('dnscheck', 'enrichment', 'https://developers.google.com/speed/public-dns/terms', 0.2, TRUE,
     'Google Public DNS over HTTPS: NS lookup per registered domain; NXDOMAIN = the domain no longer exists');

ALTER TABLE registrations
  ADD COLUMN dns_status     TEXT,         -- 'nxdomain', 'exists', 'error'
  ADD COLUMN dns_checked_at TIMESTAMPTZ;
