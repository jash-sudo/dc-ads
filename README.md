# DC Ads

Paid DemocracyCraft community advertising site.

## Plans
- Basic: DC$100 / 5 minutes
- Featured: DC$250 / 10 minutes
- Premium: DC$600 / 30 minutes

## Run
```powershell
python -m pip install -r requirements.txt
python server.py
```
Then open http://localhost:8081

The Treasury API token stays in `.env` and is never sent to the browser.

IMPORTANT: the supplied Treasury API docs expose account transaction history, but do not document a dedicated payment-intent endpoint. The starter verifier checks the receiving account's transaction history for the unique payment reference and price. Confirm the exact transaction JSON in DemocracyCraft Swagger before production and tighten recipient/sender validation if needed.
