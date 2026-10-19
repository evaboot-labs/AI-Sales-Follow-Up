"""AI sales follow-up: find HubSpot contacts with no reply after N days, write a follow-up with Claude,
queue it in an Instantly campaign, and stop on a reply, a meeting, a deal, an unsubscribe or a customer.

    python3 follow_up.py --dry-run      # show who is due and the drafts, change nothing
    python3 follow_up.py                # queue the follow-ups in Instantly and update HubSpot
    python3 follow_up.py --sync         # only pull replies from Instantly into HubSpot
    python3 follow_up.py --setup        # create the 3 HubSpot contact properties once

Settings come from .env: HUBSPOT_TOKEN, ANTHROPIC_API_KEY, INSTANTLY_API_KEY, INSTANTLY_CAMPAIGN_ID,
and optionally FOLLOW_UP_AFTER_DAYS (3), MAX_FOLLOW_UPS (2), SENDER_NAME, CLAUDE_MODEL.
"""
import datetime as dt
import json
import os
import sys
import textwrap
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
for line in (HERE / ".env").read_text().splitlines() if (HERE / ".env").exists() else []:
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

AFTER_DAYS = int(os.environ.get("FOLLOW_UP_AFTER_DAYS", 3))
MAX_FOLLOW_UPS = int(os.environ.get("MAX_FOLLOW_UPS", 2))
SENDER = os.environ.get("SENDER_NAME", "Roy")
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
CAMPAIGN = os.environ.get("INSTANTLY_CAMPAIGN_ID", "")
GUIDE = (HERE / "FOLLOW_UP.md").read_text() if (HERE / "FOLLOW_UP.md").exists() else ""

PROPS = ["email", "firstname", "lastname", "jobtitle", "company", "industry", "city", "country",
         "lifecyclestage", "notes_last_contacted", "hs_sales_email_last_replied", "hs_latest_meeting_activity",
         "num_associated_deals", "hs_email_optout", "ai_followup_status", "ai_followup_count", "ai_followup_last_sent"]


def call(method, url, headers, body=None):
    req = urllib.request.Request(url, method=method, headers={**headers, "Content-Type": "application/json", "User-Agent": "ai-sales-follow-up/1.0"},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {url} -> {e.code}: {e.read().decode()[:300]}")


def hubspot(method, path, body=None):
    return call(method, "https://api.hubapi.com" + path, {"Authorization": "Bearer " + os.environ["HUBSPOT_TOKEN"]}, body)


def instantly(method, path, body=None):
    return call(method, "https://api.instantly.ai/api/v2" + path,
                {"Authorization": "Bearer " + os.environ["INSTANTLY_API_KEY"]}, body)


def ts(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def candidates():
    """Contacts last contacted more than AFTER_DAYS ago that are not stopped or finished."""
    cutoff = int((dt.datetime.now(dt.UTC) - dt.timedelta(days=AFTER_DAYS)).timestamp() * 1000)
    body = {"filterGroups": [{"filters": [
        {"propertyName": "notes_last_contacted", "operator": "LT", "value": cutoff},
        {"propertyName": "ai_followup_status", "operator": "NOT_IN",
         "values": ["replied", "meeting", "deal", "unsubscribed", "customer", "finished"]},
    ]}], "properties": PROPS, "limit": 100,
        "sorts": [{"propertyName": "notes_last_contacted", "direction": "ASCENDING"}]}
    return hubspot("POST", "/crm/v3/objects/contacts/search", body)["results"]


def stop_reason(p):
    """The stop rules. None means: send the next follow-up."""
    last = ts(p.get("notes_last_contacted"))
    if ts(p.get("hs_sales_email_last_replied")) and ts(p["hs_sales_email_last_replied"]) >= last:
        return "replied"
    if p.get("hs_latest_meeting_activity"):
        return "meeting"
    if int(p.get("num_associated_deals") or 0) > 0:
        return "deal"
    if p.get("hs_email_optout") == "true":
        return "unsubscribed"
    if p.get("lifecyclestage") in ("opportunity", "customer", "evangelist"):
        return "customer"
    if int(p.get("ai_followup_count") or 0) >= MAX_FOLLOW_UPS:
        return "finished"
    return None


def last_email(contact_id):
    """Subject and text of the last email we sent, so the follow-up refers to it."""
    ids = hubspot("GET", f"/crm/v4/objects/contacts/{contact_id}/associations/emails")["results"]
    if not ids:
        return {}
    try:
        batch = hubspot("POST", "/crm/v3/objects/emails/batch/read", {
        "inputs": [{"id": str(i["toObjectId"])} for i in ids],
            "properties": ["hs_email_subject", "hs_email_text", "hs_email_direction", "hs_timestamp"]})["results"]
    except SystemExit as e:
        print(f"  (cannot read the previous email: add the sales-email-read scope) {str(e)[:60]}")
        return {}
    sent = [e["properties"] for e in batch if e["properties"].get("hs_email_direction") == "EMAIL"]
    return max(sent, key=lambda e: e["hs_timestamp"]) if sent else {}


def draft(p, previous, number):
    lead = "\n".join(f"{k}: {p.get(k) or 'unknown'}" for k in ("firstname", "jobtitle", "company", "industry", "city", "country"))
    prompt = (f"{GUIDE}\n\nWrite follow-up number {number} from {SENDER}.\n\nLead:\n{lead}\n\n"
              f"Previous email subject: {previous.get('hs_email_subject', 'unknown')}\n"
              f"Previous email:\n{(previous.get('hs_email_text') or '')[:1500]}\n\n"
              'Answer with JSON only: {"subject": "...", "body": "..."}')
    r = call("POST", "https://api.anthropic.com/v1/messages",
             {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
             {"model": MODEL, "max_tokens": 2000, "messages": [{"role": "user", "content": prompt}]})
    text = next(b["text"] for b in r["content"] if b["type"] == "text").strip().removeprefix("```json").removesuffix("```").strip()
    return json.loads(text)


def queue(p, mail):
    instantly("POST", "/leads", {
        "campaign": CAMPAIGN, "email": p["email"], "first_name": p.get("firstname") or "",
        "last_name": p.get("lastname") or "", "company_name": p.get("company") or "",
        "personalization": mail["body"], "custom_variables": {"followup_subject": mail["subject"]},
        "skip_if_in_campaign": False})


def log_email(contact_id, mail):
    """Log the follow-up on the contact: it shows in the timeline and moves Last Contacted forward,
    so the contact is not due again until AFTER_DAYS later."""
    hubspot("POST", "/crm/v3/objects/emails", {"properties": {
        "hs_timestamp": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "hs_email_direction": "EMAIL",
        "hs_email_status": "SENT", "hs_email_subject": mail["subject"], "hs_email_text": mail["body"]},
        "associations": [{"to": {"id": contact_id},
                          "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 198}]}]})


def update(contact_id, props):
    hubspot("PATCH", f"/crm/v3/objects/contacts/{contact_id}", {"properties": props})


def sync_replies():
    """Instantly stops the sequence on a reply; copy that reply into HubSpot so the CRM agrees."""
    leads = instantly("POST", "/leads/list", {"campaign": CAMPAIGN, "limit": 100}).get("items", [])
    replied = [l["email"] for l in leads if (l.get("email_reply_count") or 0) > 0]
    for email in replied:
        found = hubspot("POST", "/crm/v3/objects/contacts/search", {"filterGroups": [{"filters": [
            {"propertyName": "email", "operator": "EQ", "value": email}]}], "properties": ["ai_followup_status"]})["results"]
        for c in found:
            if c["properties"].get("ai_followup_status") != "replied":
                update(c["id"], {"ai_followup_status": "replied"})
                print(f"  replied in Instantly -> stopped in HubSpot: {email}")
    return replied


PROPERTIES = [
    {"name": "ai_followup_status", "label": "AI follow-up status", "type": "enumeration", "fieldType": "select",
     "groupName": "contactinformation", "options": [{"label": l, "value": v} for v, l in [
         ("active", "Active"), ("replied", "Replied"), ("meeting", "Meeting booked"), ("deal", "Deal open"),
         ("unsubscribed", "Unsubscribed"), ("customer", "Customer"), ("finished", "Finished")]]},
    {"name": "ai_followup_count", "label": "AI follow-ups sent", "type": "number", "fieldType": "number",
     "groupName": "contactinformation"},
    {"name": "ai_followup_last_sent", "label": "AI follow-up last sent", "type": "datetime", "fieldType": "date",
     "groupName": "contactinformation"},
]


def setup():
    """Create the three contact properties once. Existing ones are left as they are."""
    existing = {p["name"] for p in hubspot("GET", "/crm/v3/properties/contacts")["results"]}
    for p in PROPERTIES:
        if p["name"] in existing:
            print(f"  exists   {p['label']}")
        else:
            hubspot("POST", "/crm/v3/properties/contacts", p)
            print(f"  created  {p['label']}")


def main():
    if "--setup" in sys.argv:
        setup()
        return
    dry = "--dry-run" in sys.argv
    if not dry and not CAMPAIGN:
        raise SystemExit("Set INSTANTLY_CAMPAIGN_ID in .env")
    if "--sync" in sys.argv:
        sync_replies()
        return
    if not dry:
        sync_replies()
    due, stopped = [], []
    for c in candidates():
        p = c["properties"]
        reason = stop_reason(p)
        (stopped if reason else due).append((c["id"], p, reason))
    print(f"{len(due)} due, {len(stopped)} stopped (no reply after {AFTER_DAYS} days, max {MAX_FOLLOW_UPS} follow-ups)\n")
    for cid, p, reason in stopped:
        print(f"  STOP  {p['firstname']} {p['lastname']}, {p.get('company')}: {reason}")
        if not dry:
            update(cid, {"ai_followup_status": reason})
    for cid, p, _ in due:
        number = int(p.get("ai_followup_count") or 0) + 1
        mail = draft(p, last_email(cid), number)
        print(f"\n  SEND  {p['firstname']} {p['lastname']}, {p.get('company')}  (follow-up {number})")
        print(f"        Subject: {mail['subject']}")
        for para in mail["body"].split("\n"):
            print(textwrap.fill(para, 66, initial_indent=" " * 8, subsequent_indent=" " * 8) if para else "")
        if not dry:
            queue(p, mail)
            log_email(cid, mail)
            update(cid, {"ai_followup_status": "active", "ai_followup_count": number,
                         "ai_followup_last_sent": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")})
    if dry:
        print("\nDry run: nothing was sent or changed.")


if __name__ == "__main__":
    main()
