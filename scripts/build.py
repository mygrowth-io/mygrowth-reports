#!/usr/bin/env python3
"""Build the static client report pages from lemlist exports.

Usage: python3 scripts/build.py <data_dir> <repo_dir> <out_dir>

<data_dir> holds, for one refresh (never committed):
  campaigns.json          answer of lemlist get_campaigns
  stats_<campaignId>.json answer of lemlist get_campaigns_stats for that campaign
  inbox_<campaignId>.json answer of lemlist get_inbox_conversations
                          (listId teamConversations, campaignFilter in [id])

<repo_dir>/clients.json lists each client page:
  {"auditor-alpha": {"title": "...", "campaign_prefix": "Auditor Alpha", "target": 6}}
Each client gets <out_dir>/<slug>.html (plaintext, never committed: refresh.sh
encrypts it into <repo_dir>/<slug>/index.html). A picker switches between campaigns.
clients.json may also list "campaign_ids" to add campaigns whose name lacks the prefix.
"""
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def esc(s):
    return html.escape(str(s if s is not None else ""))


def pct(a, b):
    return f"{a / b * 100:.1f}%" if b else "—"


def short_name(full):
    parts = (full or "").replace(",", " ").split()
    if not parts:
        return "Prospect"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[1][0].upper()}."


def preview(text):
    """lemlist gives the first ~100 characters of the reply; tidy blank lines, mark cuts."""
    t = "\n".join(line.strip() for line in (text or "").splitlines() if line.strip())
    if not t:
        return "—"
    return t + "…" if len(text or "") >= 99 else t


def fmt_dt(iso):
    if not iso:
        return "—"
    d = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(PARIS)
    return d.strftime("%-d %b %Y")


def campaign_block(camp, stats, inbox, target):
    c = (stats.get("campaigns") or [{}])[0]
    L = c.get("leadMetrics", {}) or {}
    C = c.get("channelMetrics", {}) or {}
    steps = c.get("steps", []) or []
    invited = sum(s.get("invited", 0) or 0 for s in steps if s.get("taskType") == "linkedinInvite")
    accepted = C.get("linkedinInvitationAccepted", 0) or 0
    replied = L.get("answered", 0) or 0
    interested = L.get("interested", 0) or 0
    leads = L.get("total", 0) or 0
    queued = max(0, leads - invited)

    # messages by step
    sends = [s for s in steps if s.get("taskType") == "linkedinSend"]
    order = sorted({s.get("sequenceStep") for s in sends})
    msg_rows = []
    for i, st in enumerate(order):
        g = [s for s in sends if s.get("sequenceStep") == st]
        sent = sum(s.get("sent", 0) or 0 for s in g)
        opened = sum(s.get("opened", 0) or 0 for s in g)
        rep = sum(s.get("replied", 0) or 0 for s in g)
        msg_rows.append((f"Message {i + 1}", sent, opened, rep, pct(rep, sent)))

    funnel = [
        ("Leads in campaign", leads),
        ("Invitations sent", invited),
        ("Connections accepted", accepted),
        ("Replied", replied),
        ("Qualified leads", interested),
    ]
    fmax = max([n for _, n in funnel] + [1])

    progress = min(100, interested / target * 100) if target else 0

    out = []
    out.append(f'<section class="camp" data-camp="{esc(camp.get("id"))}">')
    out.append('<div class="grid">')
    target_html = f' <small>/ {target}</small>' if target else ""
    out.append(
        f'<div class="card"><h3>Qualified leads</h3><div class="big">{interested}{target_html}</div>'
        f'<div class="bar"><div style="width:{progress:.0f}%"></div></div></div>'
    )
    out.append(
        f'<div class="card"><h3>Acceptance rate</h3><div class="big">{pct(accepted, invited)}</div>'
        f'<p class="note">{accepted:,} of {invited:,} invitations</p></div>'
    )
    out.append(
        f'<div class="card"><h3>Reply rate</h3><div class="big">{pct(replied, accepted)}</div>'
        f'<p class="note">{replied:,} replies from {accepted:,} connections</p></div>'
    )
    out.append(
        f'<div class="card"><h3>Still to invite</h3><div class="big">{queued:,}</div>'
        f'<p class="note">Leads not yet sent a connection request</p></div>'
    )
    out.append("</div>")

    out.append('<div class="grid wide">')
    out.append('<div class="card"><h3>Pilot funnel</h3><div class="funnel">')
    for i, (label, n) in enumerate(funnel):
        prev = funnel[i - 1][1] if i else None
        share = f'<em>{pct(n, prev)}</em>' if i and prev else ""
        cls = "fbar muted" if i == 0 else "fbar"
        out.append(
            f'<div class="frow"><div>{esc(label)}</div><div class="ftrack">'
            f'<div class="{cls}" style="width:{n / fmax * 100:.1f}%"></div></div>'
            f'<div class="fval">{n:,}{share}</div></div>'
        )
    out.append("</div></div>")

    out.append('<div class="card"><h3>Results by message</h3><div class="tw"><table>')
    out.append('<thead><tr><th>Message</th><th class="num">Sent</th><th class="num">Seen</th>'
               '<th class="num">Replies</th><th class="num">Reply rate</th></tr></thead><tbody>')
    if msg_rows:
        for m, s, o, r, rr in msg_rows:
            out.append(f'<tr><td>{esc(m)}</td><td class="num">{s:,}</td><td class="num">{o:,}</td>'
                       f'<td class="num">{r:,}</td><td class="num">{rr}</td></tr>')
    else:
        out.append('<tr><td colspan="5" class="muted-t">No messages sent yet.</td></tr>')
    out.append("</tbody></table></div></div>")
    out.append("</div>")

    convs = inbox.get("conversations", []) or []
    convs = sorted(convs, key=lambda c: c.get("lastRepliedAt") or "", reverse=True)
    out.append('<div class="card"><h3>Conversations</h3><div class="tw"><table>')
    out.append('<thead><tr><th>Prospect</th><th>Their reply</th><th>Last activity</th></tr></thead><tbody>')
    if convs:
        for cv in convs:
            out.append(f'<tr><td class="nm">{esc(cv.get("contactName") or "Prospect")}</td>'
                       f'<td class="preview">{esc(preview(cv.get("lastRepliedMessagePreview")))}</td>'
                       f'<td class="nm">{esc(fmt_dt(cv.get("lastActivityAt")))}</td></tr>')
    else:
        out.append('<tr><td colspan="3" class="muted-t">No replies yet.</td></tr>')
    out.append("</tbody></table></div></div>")
    out.append("</section>")
    return "\n".join(out)


JS = """<script>
(function () {
  var sel = document.getElementById('camp-select');
  var secs = document.querySelectorAll('section.camp');
  function show(id) { secs.forEach(function (s) { s.hidden = s.getAttribute('data-camp') !== id; }); }
  if (!sel) return;
  var want = location.hash.slice(1);
  if (want && sel.querySelector('option[value="' + want + '"]')) sel.value = want;
  show(sel.value);
  sel.addEventListener('change', function () { show(sel.value); history.replaceState(null, '', '#' + sel.value); });
})();
</script>"""

CSS = """
:root{--bg:#f7f6f2;--panel:#fff;--fg:#1f1e1c;--muted:#6b6a65;--line:#e4e2db;--accent:#2f6fde;--grey:#c9c6bd;--track:#eceae4}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#171716;--panel:#22211f;--fg:#ecebe6;--muted:#a19f98;--line:#363531;--accent:#6c9cf0;--grey:#55534d;--track:#2e2d2a}}
:root[data-theme="dark"]{--bg:#171716;--panel:#22211f;--fg:#ecebe6;--muted:#a19f98;--line:#363531;--accent:#6c9cf0;--grey:#55534d;--track:#2e2d2a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:"Inter",system-ui,-apple-system,"Segoe UI",sans-serif;font-size:15px;line-height:1.45}
.wrap{max-width:1100px;margin:0 auto;padding:32px 16px 48px;display:flex;flex-direction:column;gap:24px}
.eyebrow{color:var(--muted);font-size:13px;margin:0 0 4px}
h1{font-family:Georgia,"Times New Roman",serif;font-weight:400;font-size:32px;margin:0}
.updated{color:var(--muted);font-size:13px;margin:6px 0 0}
.camp{display:flex;flex-direction:column;gap:16px}
.camp[hidden]{display:none}
.pick{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:14px;color:var(--muted);font-size:13px}
.pick select{font:inherit;font-size:15px;color:var(--fg);background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:6px 10px;max-width:100%}
.preview{white-space:pre-line;min-width:14rem}
.nm{white-space:nowrap;vertical-align:top}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,13rem),1fr));gap:12px}
.grid.wide{grid-template-columns:repeat(auto-fit,minmax(min(100%,22rem),1fr))}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px;display:flex;flex-direction:column;gap:8px;min-width:0}
.card h3{font-size:15px;font-weight:600;margin:0}
.big{font-family:Georgia,"Times New Roman",serif;font-size:32px;line-height:1.1;font-variant-numeric:tabular-nums}
.big small{font-family:inherit;font-size:15px;color:var(--muted)}
.note{color:var(--muted);font-size:13px;margin:0}
.bar{height:8px;border-radius:4px;background:var(--track);overflow:hidden}
.bar>div{height:100%;background:var(--accent);border-radius:4px}
.funnel{display:flex;flex-direction:column;gap:10px}
.frow{display:grid;grid-template-columns:minmax(7rem,11rem) 1fr auto;gap:10px;align-items:center;font-size:13px}
.ftrack{height:22px}
.fbar{height:100%;min-width:2px;border-radius:4px;background:var(--accent)}
.fbar.muted{background:var(--grey)}
.fval{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.fval em{font-style:normal;color:var(--muted);margin-left:6px}
.tw{overflow:auto}
table{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}
th{text-align:left;font-weight:600;color:var(--muted);padding:6px 8px;border-bottom:1px solid var(--line)}
td{padding:8px;border-bottom:1px solid var(--line)}
.num{text-align:right}
.muted-t{color:var(--muted)}
footer{color:var(--muted);font-size:12px}
@media (max-width:30rem){.frow{grid-template-columns:1fr auto}.ftrack{grid-column:1/-1;grid-row:2}}
"""


def build(data_dir, repo_dir, out_dir):
    data_dir, repo_dir, out_dir = Path(data_dir), Path(repo_dir), Path(out_dir)
    clients = load(repo_dir / "clients.json")
    campaigns = load(data_dir / "campaigns.json").get("campaigns", [])
    now = datetime.now(timezone.utc).astimezone(PARIS)
    for slug, cfg in clients.items():
        if slug.startswith("_"):
            continue
        prefix = cfg.get("campaign_prefix", "")
        extra = set(cfg.get("campaign_ids", []))
        mine = [c for c in campaigns if (prefix and (c.get("name") or "").startswith(prefix)) or c.get("id") in extra]
        blocks, options = [], []
        for camp in mine:
            sp = data_dir / f"stats_{camp['id']}.json"
            ip = data_dir / f"inbox_{camp['id']}.json"
            if not sp.exists():
                continue
            blocks.append(campaign_block(camp, load(sp), load(ip) if ip.exists() else {}, cfg.get("target")))
            label = camp.get("name") or camp["id"]
            if camp.get("status") and camp.get("status") != "running":
                label += f" ({camp['status']})"
            options.append(f'<option value="{esc(camp["id"])}">{esc(label)}</option>')
        picker = ""
        if options:
            picker = ('<label class="pick">Campaign <select id="camp-select">' + "".join(options) + '</select></label>')
        if not blocks:
            blocks.append('<p class="note">No campaign data yet.</p>')
        page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{esc(cfg.get('title', slug))}</title>
<style>{CSS}</style></head>
<body><main class="wrap">
<header><p class="eyebrow">My Growth · LinkedIn outbound report</p>
<h1>{esc(cfg.get('title', slug))}</h1>
<p class="updated">Updated {now.strftime('%-d %b %Y, %H:%M')} (Paris time) · refreshed daily</p>
{picker}</header>
{chr(10).join(blocks)}
<footer>Source: lemlist, LinkedIn channel. Report prepared by My Growth.</footer>
</main>
{JS}</body></html>
"""
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{slug}.html"
        out.write_text(page, encoding="utf-8")
        print(f"built {out} ({len(mine)} campaign(s))")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2], sys.argv[3])
