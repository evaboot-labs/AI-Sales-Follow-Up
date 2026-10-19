# Agent instructions

This repo sends AI-written follow-ups to HubSpot contacts who did not reply, through Instantly, and stops on a reply, a meeting, a deal, an unsubscribe or a customer. When the user asks to follow up with their leads or contacts:

1. Check that `.env` has `HUBSPOT_TOKEN`, `ANTHROPIC_API_KEY`, `INSTANTLY_API_KEY` and `INSTANTLY_CAMPAIGN_ID`. If one is missing, tell the user how to get it from README.md and stop.
2. Read `FOLLOW_UP.md`. If it still holds the example offer (Evaboot), ask the user what they sell and how they write, and rewrite the file first.
3. Run `python3 follow_up.py --dry-run` and show the user who is due, who is stopped and why, and each draft.
4. Point out drafts that invent facts, repeat the first email or ask for too much. Fix `FOLLOW_UP.md` and repeat step 3 if needed.
5. When the user agrees, run `python3 follow_up.py`.
6. Report how many follow-ups were queued in Instantly and how many contacts were stopped, by reason.

Never send without the user's yes after a dry run. Never change the stop rules to send to someone who replied, booked a meeting, has an open deal or unsubscribed.
