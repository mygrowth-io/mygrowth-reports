# My Growth — client reports

Static LinkedIn outbound reports for My Growth clients, published with GitHub Pages
and refreshed daily from lemlist (read-only).

- `clients.json` — one entry per client page: title, lemlist campaign name prefix, qualified-lead target.
- `scripts/build.py` — builds `<client>/index.html` from lemlist exports kept in `data/` (never committed).

Pages are encrypted with a per-client password; the decrypted page shows prospect names and the first lines of their replies, with a picker to switch campaigns.
`clients.json` may list `campaign_ids` to add campaigns whose name does not start with the prefix.
- `scripts/refresh.sh` — runs the build, then encrypts each page with its client password (StatiCrypt), so only ciphertext is ever committed.
