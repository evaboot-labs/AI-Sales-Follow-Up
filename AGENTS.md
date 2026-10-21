# Agent instructions

This repo sends AI-written follow-ups to HubSpot contacts who did not reply: Claude writes each email, Instantly sends it, and the run stops on a reply, a meeting, a deal, an unsubscribe or a customer. When the user asks to follow up with their leads or contacts:

1. Follow the skill in `skills/follow-up/SKILL.md` step by step.
2. Check that `.env` has `HUBSPOT_TOKEN`, `ANTHROPIC_API_KEY`, `INSTANTLY_API_KEY` and `INSTANTLY_CAMPAIGN_ID`. If one is missing, tell the user how to get it from `docs/setup.md` and stop.
3. On the first run, check the three HubSpot properties exist; if not, ask the user and run `python3 follow_up.py --setup`.
4. Read `FOLLOW_UP.md`. If it still holds the example offer (Evaboot), ask the user what they sell and how they write, and rewrite the file first.
5. Run `python3 follow_up.py --dry-run` and show the user who is due, who is stopped and why, and each draft.
6. Point out drafts that invent facts, repeat the first email or ask for too much. Fix `FOLLOW_UP.md` and repeat step 5 if needed.
7. When the user agrees, run `python3 follow_up.py`. Tell the user first that the live run writes each email again, so the sent text can differ from the dry-run draft.
8. Report how many follow-ups were queued in Instantly and how many contacts were stopped, by reason.

For n8n or a daily schedule, see `docs/n8n.md`.

Confirm with the user before every call that saves, sends or changes anything: never send without the user's yes after a dry run. Never change the stop rules to send to someone who replied, booked a meeting, has an open deal or unsubscribed. Never ask for or handle an API key in the chat: the user writes the keys into `.env`. Never commit `.env`.
