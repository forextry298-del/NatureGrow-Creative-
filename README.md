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


## Profile and appearance updates
- The Profile tab now opens a Mine-style account page with the farm-photo banner, masked phone number, account ID, spendable balance, growth balance, active plot count, total harvest value, and My Products shortcut.
- Settings includes Change Password and a Light/Dark Theme switch.
- The theme switch applies the botanical green-and-cream look across the full site and saves the choice in browser storage, so it stays selected when navigating between pages. Tap the switch again to return to the dark charcoal theme.
- The profile banner uses `static/images/profile-farm-banner.jpg`; product cards continue using the supplied farm images.


## Popup navigation
Internal page links and same-site forms open inside a modal overlay without a full browser page refresh. The overlay has a close button and Escape support. Network requests still occur for server-backed actions, but the current page stays in place while the popup updates. External community links continue to open normally.
