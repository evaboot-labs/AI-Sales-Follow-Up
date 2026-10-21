"""Build the n8n template JSON for this workflow. Run: python3 n8n/build_workflow.py"""
import json
import uuid
from pathlib import Path

HERE = Path(__file__).parent
GUIDE = (HERE.parent / "FOLLOW_UP.md").read_text()
HUBSPOT_CRED = {"hubspotAppToken": {"id": "", "name": "HubSpot service key"}}
ANTHROPIC_CRED = {"anthropicApi": {"id": "", "name": "Anthropic"}}
INSTANTLY_CRED = {"httpHeaderAuth": {"id": "", "name": "Instantly API key"}}


def node(name, type_, version, position, parameters, **extra):
    return {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, "follow-up/" + name)), "name": name, "type": type_,
            "typeVersion": version, "position": position, "parameters": parameters, **extra}


def sticky(name, position, width, height, content, color=7):
    return node(name, "n8n-nodes-base.stickyNote", 1, position,
                {"color": color, "width": width, "height": height, "content": content})


def http(name, position, method, url, cred, body=None, headers=None, **extra):
    if cred == "instantly":
        params = {"method": method, "url": url, "authentication": "genericCredentialType",
                  "genericAuthType": "httpHeaderAuth", "options": {}}
        creds = INSTANTLY_CRED
    else:
        params = {"method": method, "url": url, "authentication": "predefinedCredentialType",
                  "nodeCredentialType": cred, "options": {}}
        creds = HUBSPOT_CRED if cred == "hubspotAppToken" else ANTHROPIC_CRED
    if headers:
        params.update({"sendHeaders": True, "headerParameters": {"parameters": [
            {"name": k, "value": v} for k, v in headers.items()]}})
    if body is not None:
        params.update({"sendBody": True, "specifyBody": "json", "jsonBody": body})
    return node(name, "n8n-nodes-base.httpRequest", 4.2, position, params, credentials=creds, **extra)


def code(name, position, js, each=True, **extra):
    return node(name, "n8n-nodes-base.code", 2, position,
                {"mode": "runOnceForEachItem" if each else "runOnceForAllItems", "jsCode": js}, **extra)


S = "$('Your settings').first().json"

REPLIED = """// Leads that replied in Instantly. Instantly already stopped their sequence; HubSpot must agree.
const leads = $input.first().json.items || [];
return leads.filter(l => (l.email_reply_count || 0) > 0).map(l => ({ json: { email: l.email } }));"""

SEARCH_BODY = """={{ JSON.stringify({
  filterGroups: [{ filters: [
    { propertyName: 'notes_last_contacted', operator: 'LT', value: Date.now() - %s.followUpAfterDays * 86400000 },
    { propertyName: 'ai_followup_status', operator: 'NOT_IN', values: ['replied', 'meeting', 'deal', 'unsubscribed', 'customer', 'finished'] }
  ] }],
  properties: ['email', 'firstname', 'lastname', 'jobtitle', 'company', 'industry', 'city', 'country', 'lifecyclestage',
    'notes_last_contacted', 'hs_sales_email_last_replied', 'hs_latest_meeting_activity', 'num_associated_deals',
    'hs_email_optout', 'ai_followup_count'],
  sorts: [{ propertyName: 'notes_last_contacted', direction: 'ASCENDING' }],
  limit: 100
}) }}""" % S

STOP_RULES = """// The stop rules. An empty reason means: send the next follow-up.
const p = $json.properties;
const settings = $('Your settings').first().json;
const last = new Date(p.notes_last_contacted);
let reason = '';
if (p.hs_sales_email_last_replied && new Date(p.hs_sales_email_last_replied) >= last) reason = 'replied';
else if (p.hs_latest_meeting_activity) reason = 'meeting';
else if (Number(p.num_associated_deals || 0) > 0) reason = 'deal';
else if (p.hs_email_optout === 'true') reason = 'unsubscribed';
else if (['opportunity', 'customer', 'evangelist'].includes(p.lifecyclestage)) reason = 'customer';
else if (Number(p.ai_followup_count || 0) >= settings.maxFollowUps) reason = 'finished';
return { id: $json.id, reason, number: Number(p.ai_followup_count || 0) + 1, contact: p };"""

PREVIOUS = """// The last email we sent, so the follow-up can refer to it.
const sent = ($json.results || []).map(e => e.properties).filter(e => e.hs_email_direction === 'EMAIL');
sent.sort((a, b) => (a.hs_timestamp < b.hs_timestamp ? 1 : -1));
const lead = $('Check stop rules').item.json;
const c = lead.contact;
const settings = $('Your settings').first().json;
const prompt = `${settings.followUpGuide}

Write follow-up number ${lead.number} from ${settings.senderName}.

Lead:
First name: ${c.firstname || 'unknown'}
Job title: ${c.jobtitle || 'unknown'}
Company: ${c.company || 'unknown'}
Industry: ${c.industry || 'unknown'}
Location: ${[c.city, c.country].filter(Boolean).join(', ') || 'unknown'}

Previous email subject: ${sent[0]?.hs_email_subject || 'unknown'}
Previous email:
${(sent[0]?.hs_email_text || '').slice(0, 1500)}

Answer with JSON only: {"subject": "...", "body": "..."}`;
return { id: lead.id, number: lead.number, contact: c, prompt };"""

CLAUDE_BODY = """={{ JSON.stringify({
  model: 'claude-sonnet-5-5',
  max_tokens: 2000,
  messages: [{ role: 'user', content: $json.prompt }]
}) }}"""

READ_DRAFT = """// Claude answers with JSON: a subject and a body.
const text = $json.content.find(b => b.type === 'text').text.trim().replace(/^```json|```$/g, '').trim();
const mail = JSON.parse(text);
const lead = $('Previous email').item.json;
return { id: lead.id, number: lead.number, contact: lead.contact, subject: mail.subject, body: mail.body };"""

INSTANTLY_BODY = """={{ JSON.stringify({
  campaign: %s.instantlyCampaignId,
  email: $json.contact.email,
  first_name: $json.contact.firstname || '',
  last_name: $json.contact.lastname || '',
  company_name: $json.contact.company || '',
  personalization: $json.body,
  custom_variables: { followup_subject: $json.subject },
  skip_if_in_campaign: false
}) }}""" % S

D = "$('Read the draft').item.json"
LOG_BODY = """={{ JSON.stringify({
  properties: { hs_timestamp: new Date().toISOString(), hs_email_direction: 'EMAIL', hs_email_status: 'SENT',
    hs_email_subject: %s.subject, hs_email_text: %s.body },
  associations: [{ to: { id: %s.id }, types: [{ associationCategory: 'HUBSPOT_DEFINED', associationTypeId: 198 }] }]
}) }}""" % (D, D, D)

UPDATE_BODY = """={{ JSON.stringify({ properties: {
  ai_followup_status: 'active', ai_followup_count: %s.number, ai_followup_last_sent: new Date().toISOString()
} }) }}""" % D

OVERVIEW = """## AI sales follow-up with stop rules (HubSpot, Claude, Instantly)

**Who it's for:** sales teams that send a first email and lose deals because nobody follows up, or follow up after the lead already replied.

**What it does:** every weekday at 9am, the workflow finds HubSpot contacts last contacted more than 3 days ago. It checks five stop rules (reply, meeting, open deal, unsubscribe, customer) and a maximum of 2 follow-ups. For each contact still due, Claude writes a short follow-up that refers to the previous email, Instantly sends it, and the email is logged on the contact. Replies in Instantly are copied back to HubSpot first, so a lead who answered is never chased.

### How to set up
1. In HubSpot, create a service key with the scopes `crm.objects.contacts.read`, `crm.objects.contacts.write`, `crm.schemas.contacts.read`, `crm.schemas.contacts.write`, `sales-email-read`, and create the 3 contact properties from the GitHub repo (or run `python3 follow_up.py --setup`).
2. In Instantly, create a campaign with one step: subject `{{followup_subject}}`, body `{{personalization}}`. Turn on **Stop sending emails on reply** and **Stop campaign for company on reply**.
3. Add credentials: **HubSpot Service Key**, **Anthropic**, and **Header Auth** for Instantly (name `Authorization`, value `Bearer YOUR_KEY`).
4. Fill in **Your settings**, click **Execute workflow** to test, then publish.

### Requirements
HubSpot (the free plan works), an Anthropic API key, an Instantly account with a connected mailbox.

### How to customize
Edit the writing rules in **Your settings** (followUpGuide). Change the stop rules in **Check stop rules**. The same workflow as a Python script with agent instructions: github.com/evaboot-labs/ai-sales-follow-up"""

nodes = [
    sticky("Template overview", [-860, -420], 560, 1060, OVERVIEW),
    sticky("Step 1", [-260, -420], 900, 380,
           "### 1. Copy replies from Instantly\nInstantly stops a sequence as soon as the lead replies. This branch marks those leads **Replied** in HubSpot, so the search below skips them."),
    sticky("Step 2", [-260, 0], 1340, 640,
           "### 2. Find who is due and apply the stop rules\nContacts last contacted more than **followUpAfterDays** ago. A reply, a meeting, an open deal, an unsubscribe, a customer stage or the follow-up limit stops the contact and records the reason."),
    sticky("Step 3", [1120, 0], 1500, 640,
           "### 3. Write, send and log\nClaude writes the follow-up from the lead and the previous email. Instantly sends it inside your schedule. The email is logged on the HubSpot contact, which moves **Last Contacted** forward."),
    node("Every weekday at 9am", "n8n-nodes-base.scheduleTrigger", 1.2, [-220, 120],
         {"rule": {"interval": [{"field": "cronExpression", "expression": "0 9 * * 1-5"}]}}),
    node("Test run", "n8n-nodes-base.manualTrigger", 1, [-220, 320], {}),
    node("Your settings", "n8n-nodes-base.set", 3.4, [0, 220], {
        "mode": "manual",
        "assignments": {"assignments": [
            {"id": "days", "name": "followUpAfterDays", "type": "number", "value": 3},
            {"id": "max", "name": "maxFollowUps", "type": "number", "value": 2},
            {"id": "camp", "name": "instantlyCampaignId", "type": "string", "value": "YOUR_INSTANTLY_CAMPAIGN_ID"},
            {"id": "sender", "name": "senderName", "type": "string", "value": "Roy"},
            {"id": "guide", "name": "followUpGuide", "type": "string", "value": GUIDE},
        ]}, "options": {}}, executeOnce=True),
    http("Get campaign leads", [220, -220], "POST", "https://api.instantly.ai/api/v2/leads/list", "instantly",
         "={{ JSON.stringify({ campaign: %s.instantlyCampaignId, limit: 100 }) }}" % S),
    code("Leads who replied", [420, -220], REPLIED, each=False),
    http("Mark replied in HubSpot", [620, -220], "PATCH",
         "=https://api.hubapi.com/crm/v3/objects/contacts/{{ encodeURIComponent($json.email) }}?idProperty=email",
         "hubspotAppToken", "={{ JSON.stringify({ properties: { ai_followup_status: 'replied' } }) }}",
         onError="continueRegularOutput"),
    http("Find contacts to follow up", [220, 220], "POST",
         "https://api.hubapi.com/crm/v3/objects/contacts/search", "hubspotAppToken", SEARCH_BODY),
    node("One contact per item", "n8n-nodes-base.splitOut", 1, [420, 220], {"fieldToSplitOut": "results", "options": {}}),
    code("Check stop rules", [620, 220], STOP_RULES),
    node("Stopped?", "n8n-nodes-base.if", 2.2, [820, 220], {
        "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                       "conditions": [{"id": "stop", "leftValue": "={{ $json.reason }}", "rightValue": "",
                                       "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}],
                       "combinator": "and"}, "options": {}}),
    http("Record the stop reason", [1020, 100], "PATCH",
         "=https://api.hubapi.com/crm/v3/objects/contacts/{{ $json.id }}", "hubspotAppToken",
         "={{ JSON.stringify({ properties: { ai_followup_status: $json.reason } }) }}"),
    http("Get emails", [1020, 380], "GET",
         "=https://api.hubapi.com/crm/v4/objects/contacts/{{ $json.id }}/associations/emails", "hubspotAppToken"),
    http("Read emails", [1200, 380], "POST", "https://api.hubapi.com/crm/v3/objects/emails/batch/read", "hubspotAppToken",
         "={{ JSON.stringify({ inputs: ($json.results || []).map(r => ({ id: String(r.toObjectId) })), "
         "properties: ['hs_email_subject', 'hs_email_text', 'hs_email_direction', 'hs_timestamp'] }) }}",
         onError="continueRegularOutput", alwaysOutputData=True),
    code("Previous email", [1380, 380], PREVIOUS),
    http("Write the follow-up", [1560, 380], "POST", "https://api.anthropic.com/v1/messages", "anthropicApi",
         CLAUDE_BODY, headers={"anthropic-version": "2023-06-01"}),
    code("Read the draft", [1740, 380], READ_DRAFT),
    http("Send with Instantly", [1920, 380], "POST", "https://api.instantly.ai/api/v2/leads", "instantly", INSTANTLY_BODY),
    http("Log the email in HubSpot", [2100, 380], "POST", "https://api.hubapi.com/crm/v3/objects/emails",
         "hubspotAppToken", LOG_BODY),
    http("Update the contact", [2280, 380], "PATCH",
         "=https://api.hubapi.com/crm/v3/objects/contacts/{{ $('Read the draft').item.json.id }}", "hubspotAppToken",
         UPDATE_BODY),
]


def link(a, b, out=0):
    connections.setdefault(a, {"main": []})
    while len(connections[a]["main"]) <= out:
        connections[a]["main"].append([])
    connections[a]["main"][out].append({"node": b, "type": "main", "index": 0})


connections = {}
for trigger in ("Every weekday at 9am", "Test run"):
    link(trigger, "Your settings")
link("Your settings", "Get campaign leads")      # top branch runs first
link("Your settings", "Find contacts to follow up")
for a, b in [("Get campaign leads", "Leads who replied"), ("Leads who replied", "Mark replied in HubSpot"),
             ("Find contacts to follow up", "One contact per item"), ("One contact per item", "Check stop rules"),
             ("Check stop rules", "Stopped?"), ("Get emails", "Read emails"), ("Read emails", "Previous email"),
             ("Previous email", "Write the follow-up"), ("Write the follow-up", "Read the draft"),
             ("Read the draft", "Send with Instantly"), ("Send with Instantly", "Log the email in HubSpot"),
             ("Log the email in HubSpot", "Update the contact")]:
    link(a, b)
link("Stopped?", "Record the stop reason", 0)
link("Stopped?", "Get emails", 1)

workflow = {"name": "AI sales follow-up with stop rules (HubSpot, Claude, Instantly)", "nodes": nodes,
            "connections": connections, "settings": {"executionOrder": "v1"}}
out = HERE / "hubspot-ai-sales-follow-up.json"
out.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n")
print(f"Wrote {out} ({len(nodes)} nodes)")
