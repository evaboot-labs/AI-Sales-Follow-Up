# Run it in n8n

[`n8n/hubspot-ai-sales-follow-up.json`](../n8n/hubspot-ai-sales-follow-up.json) is the same workflow
for n8n. Import it, add three credentials (**HubSpot Service Key**, **Anthropic**, and **Header
Auth** for Instantly: name `Authorization`, value `Bearer YOUR_KEY`), fill in **Your settings**
and publish. It runs every weekday at 9am.

To schedule the Python script instead, run `python3 follow_up.py` every weekday from cron or any scheduler.

Back to the [README](../README.md).
