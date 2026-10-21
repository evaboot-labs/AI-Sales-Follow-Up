# Set up and run the script

## What a run does

Follow up with every HubSpot contact who did not reply, with a short email written by AI
for that lead, and stop the moment they reply, book a meeting or become a deal.

Every weekday the workflow:

1. finds HubSpot contacts last contacted more than 3 days ago,
2. checks the stop rules: **reply, meeting, open deal, unsubscribe, customer**, and a maximum of 2 follow-ups,
3. asks Claude to write a follow-up that refers to your previous email, using the rules in [`FOLLOW_UP.md`](../FOLLOW_UP.md),
4. sends it through an Instantly campaign, inside your sending schedule,
5. logs the email on the HubSpot contact and records the result in three properties:

| Property | Example | Meaning |
|---|---|---|
| `ai_followup_status` | Replied | Active, Replied, Meeting booked, Deal open, Unsubscribed, Customer or Finished |
| `ai_followup_count` | 1 | Follow-ups sent so far |
| `ai_followup_last_sent` | 2026-10-19 | When the last one went out |

Replies are caught twice: Instantly stops the sequence on a reply, and the next run copies
that reply into HubSpot so the CRM agrees.

## How it works

```
HubSpot contacts ──> stop rules ──> due? ──> Claude writes ──> Instantly sends
      ▲                  │                                          │
      │                  └── stopped: reason saved in HubSpot       │
      └──────── email logged, Last Contacted moves ◀────────────────┘
      └──────── reply in Instantly ──> status Replied ◀─────────────┘
```

## Install

You need Python 3.9 or later. No packages to install.

1. **HubSpot service key.** In HubSpot, open **More > Development > Keys > Service Keys** and
   click **Create service key**. Add five scopes: `crm.objects.contacts.read`,
   `crm.objects.contacts.write`, `crm.schemas.contacts.read`, `crm.schemas.contacts.write`,
   `sales-email-read`. Click **Create**, then **Show** to copy the key (it starts with `pat-`).
2. **Anthropic key** at https://console.anthropic.com/settings/keys.
3. **Instantly.** Connect a sending mailbox, then create a campaign with **one step**:
   subject `{{followup_subject}}`, body `{{personalization}}`. In **Settings**, turn on
   **Stop sending emails on reply** and **Stop campaign for company on reply**. Create an
   API key under **Settings > Integrations > API Keys**. The campaign ID is in its URL.
4. **Env file:**
   ```bash
   cp .env.example .env
   ```
5. **Create the HubSpot properties** once:
   ```bash
   python3 follow_up.py --setup
   ```
6. **Your voice.** Replace the example in [`FOLLOW_UP.md`](../FOLLOW_UP.md) with your offer and rules.

Your first emails must be logged in HubSpot (HubSpot does this when you send from the CRM
or log an email). The workflow reads **Last Contacted** to know who is due.

## Run

See who is due, who is stopped and why, and the drafts. Nothing is sent:

```bash
python3 follow_up.py --dry-run
```

```
2 due, 4 stopped (no reply after 3 days, max 2 follow-ups)

  STOP  Daniel Test, Orbit HR Cloud (test): deal
  STOP  Marc Test, Brightpath Software (test): replied
  STOP  Sofia Test, Kestrel Analytics (test): meeting
  STOP  Emma Test, Lumen Recruiting (test): customer

  SEND  Nina Test, Halden Robotics (test)  (follow-up 1)
        Subject: lists for new reps
        Hi Nina,
        ...
```

Then send for real:

```bash
python3 follow_up.py
```

| Option | Does |
|---|---|
| `--dry-run` | Shows the stops and drafts, changes nothing |
| `--sync` | Only copies Instantly replies into HubSpot |
| `--setup` | Creates the three HubSpot contact properties |

Settings in `.env`: `FOLLOW_UP_AFTER_DAYS` (default 3), `MAX_FOLLOW_UPS` (default 2),
`SENDER_NAME`, `CLAUDE_MODEL`.

## Cost

One Claude call per follow-up, a few cents for a hundred emails. Instantly needs a connected
mailbox; HubSpot's free plan has the API.


Back to the [README](../README.md).
