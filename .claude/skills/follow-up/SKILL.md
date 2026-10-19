---
name: follow-up
description: Send AI-written follow-ups to HubSpot contacts who did not reply, through Instantly, with stop rules for replies, meetings, deals, unsubscribes and customers. Use when the user asks to follow up with their leads or contacts.
---

1. Check that `.env` has `HUBSPOT_TOKEN`, `ANTHROPIC_API_KEY`, `INSTANTLY_API_KEY` and `INSTANTLY_CAMPAIGN_ID`. If one is missing, tell the user how to get it from README.md and stop.
2. Read `FOLLOW_UP.md`. If it still holds the example offer (Evaboot), ask the user what they sell and how they write, and rewrite the file first.
3. Run `python3 follow_up.py --dry-run` and show who is due, who is stopped and why, and each draft.
4. Ask the user if the drafts look right. If not, sharpen `FOLLOW_UP.md` and repeat step 3.
5. When the user agrees, run `python3 follow_up.py`.
6. Report how many follow-ups were queued and how many contacts were stopped, by reason.
