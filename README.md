# NatureGrow Creative
Mobile-first Flask demo inspired by the screenshots. Includes registration/login, dashboard, product cards, demo purchases, referral/team page, demo deposit/withdrawal requests, daily check-in, transaction history, support and password settings.

Run: `pip install -r requirements.txt` then `python app.py`; open `http://127.0.0.1:5000`.

Render build command: `pip install -r requirements.txt`; start command: `gunicorn app:app`; leave Root Directory blank if these files are in repository root.

Important: this is a demo only. Deposits do not process payments or credit balances; withdrawals are simulated; income numbers are illustrative and not guaranteed. Do not collect real payments or market returns as guaranteed.


## Image update
The homepage hero and product cards use the supplied NatureGrow farming/solar-team image, cropped into local assets under `static/images/`. The app remains a demo: deposits are requests only, withdrawals are not paid out, and product figures are illustrative rather than guaranteed returns.
