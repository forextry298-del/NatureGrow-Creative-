# NatureGrow Creative

Mobile-first Flask/SQLite platform with registration and login, dashboard, compact product cards, referral/team page, deposit and withdrawal request records, daily check-in, transaction history, support, and password settings.

## Run locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Deployment

Use `gunicorn app:app`. Set a strong `SECRET_KEY` and configure `DATABASE_PATH` to a persistent location on your host. The included Render configuration uses `/var/data/naturegrow.db`.

## Payment and product requirements

Deposit requests are saved as **Pending** and do not credit a balance automatically. Withdrawal requests are saved as **Pending** and do not send money automatically. A verified MTN MoMo/Airtel Money integration and a secure administrator approval workflow are required before real payments can be processed. Product daily/total figures are locally configured display values; they are not proof of actual or guaranteed returns. Referral levels are displayed for layout, but automated commission settlement is not implemented.

The supplied NatureGrow farming/solar-team photo is used for the homepage and cropped product-card images. The bottom navigation uses responsive SVG icons and active-page styling.
