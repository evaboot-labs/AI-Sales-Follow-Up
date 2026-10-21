---
name: follow-up
description: Send AI-written follow-ups to HubSpot contacts who did not reply, through Instantly, with stop rules for replies, meetings, deals, unsubscribes and customers. Use when the user asks to follow up with their leads or contacts.
---

1. Check that `.env` has `HUBSPOT_TOKEN`, `ANTHROPIC_API_KEY`, `INSTANTLY_API_KEY` and `INSTANTLY_CAMPAIGN_ID`. If one is missing, tell the user how to get it from `docs/setup.md` and stop. The user writes the keys into `.env` themselves; never ask for a key in the chat.
2. On the first run, check the three HubSpot properties exist; if not, ask the user and run `python3 follow_up.py --setup`.
3. Read `FOLLOW_UP.md`. If it still holds the example offer (Evaboot), ask the user what they sell and how they write, and rewrite the file first.
4. Run `python3 follow_up.py --dry-run` and show who is due, who is stopped and why, and each draft.
5. Ask the user if the drafts look right. If not, sharpen `FOLLOW_UP.md` and repeat step 4.
6. When the user agrees, run `python3 follow_up.py`. Tell the user first that the live run writes each email again, so the sent text can differ from the dry-run draft.
7. Report how many follow-ups were queued and how many contacts were stopped, by reason.

Never send without the user's yes after a dry run. Never change the stop rules to send to someone who replied, booked a meeting, has an open deal or unsubscribed. Never commit `.env`.
