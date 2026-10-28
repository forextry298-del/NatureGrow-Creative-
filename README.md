# NatureGrow Creative

A mobile-first Flask account platform styled to match the supplied NatureGrow registration and login references. The login page uses the supplied farm photograph as its wide hero image.

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python app.py
```
Open `http://127.0.0.1:5000`.

## Deploy
The included `Procfile` and `render.yaml` are configured for Render. For a persistent database, attach a disk mounted at `/var/data` and set `DATABASE_PATH=/var/data/naturegrow.db`. Set a unique `SECRET_KEY` in the hosting environment.

## Included
- Registration with full name, username, phone, email, password, and farm location/interest
- Login with email or username and password
- Password hashing, duplicate account checks, session login/logout
- Responsive mobile-first pages and password visibility toggles
- Login hero using `static/images/farm.jpg`

This initial build covers the account screens shown in the references. It does not yet include farm investments, payments, payouts, or earnings functionality.


## Mobile layout
The authentication screens use compact mobile-first sizing. The viewport disables user pinch-zoom on the site as requested; users can still change browser-level accessibility settings.
# NatureGrow-Creative-
