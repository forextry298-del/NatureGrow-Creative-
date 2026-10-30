import os,sqlite3,secrets
from datetime import datetime,date
from functools import wraps
from flask import Flask,render_template,request,redirect,url_for,session,flash
from werkzeug.security import generate_password_hash,check_password_hash
app=Flask(__name__); app.secret_key=os.environ.get("SECRET_KEY","change-me-before-deployment")
DB=os.environ.get("DATABASE_PATH","naturegrow.db")
P=[{'id': 1, 'name': 'Plot-1', 'price': 45000, 'daily': 9000, 'image': 'farm1.jpg', 'days': 60}, {'id': 2, 'name': 'Plot-2', 'price': 60000, 'daily': 12000, 'image': 'farm2.jpg', 'days': 60}, {'id': 3, 'name': 'Plot-3', 'price': 100000, 'daily': 20000, 'image': 'farm3.jpg', 'days': 60}, {'id': 4, 'name': 'Plot-4', 'price': 250000, 'daily': 31000, 'image': 'farm1.jpg', 'days': 60}, {'id': 5, 'name': 'Plot-5', 'price': 500000, 'daily': 55000, 'image': 'farm2.jpg', 'days': 60}, {'id': 6, 'name': 'Plot-6', 'price': 1000000, 'daily': 160000, 'image': 'farm3.jpg', 'days': 60}, {'id': 7, 'name': 'Plot-7', 'price': 2000000, 'daily': 220000, 'image': 'farm1.jpg', 'days': 60, 'sold_out': True}, {'id': 8, 'name': 'Plot-8', 'price': 5000000, 'daily': 434200, 'image': 'farm2.jpg', 'days': 60}, {'id': 9, 'name': 'Farm 1', 'price': 25000, 'daily': 1700, 'image': 'farm_product_1.jpg', 'days': 30}, {'id': 10, 'name': 'Farm 2', 'price': 50000, 'daily': 7000, 'image': 'farm_product_2.jpg', 'days': 30}, {'id': 11, 'name': 'Farm 3', 'price': 100000, 'daily': 6000, 'image': 'farm_product_3.jpg', 'days': 60}, {'id': 12, 'name': 'Farm 4', 'price': 100000, 'daily': 12000, 'image': 'farm_product_4.jpg', 'days': 30}, {'id': 13, 'name': 'Farm 5', 'price': 150000, 'daily': 10000, 'image': 'farm_product_5.jpg', 'days': 60}, {'id': 14, 'name': 'Farm 6', 'price': 554000, 'daily': 24700, 'image': 'farm_product_6.jpg', 'days': 60}, {'id': 15, 'name': 'Farm 7', 'price': 350000, 'daily': 37000, 'image': 'farm_product_7.jpg', 'days': 30}, {'id': 16, 'name': 'Farm 8', 'price': 300000, 'daily': 32000, 'image': 'farm_product_8.jpg', 'days': 30}]
def con(): 
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
with con() as c:
 c.executescript("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,phone TEXT,password TEXT,invite TEXT UNIQUE,referrer INTEGER,balance INTEGER DEFAULT 0,created TEXT);
 CREATE TABLE IF NOT EXISTS tx(id INTEGER PRIMARY KEY,user_id INTEGER,kind TEXT,amount INTEGER,note TEXT,status TEXT,created TEXT);
 CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY,user_id INTEGER,product TEXT,price INTEGER,daily INTEGER,days INTEGER DEFAULT 60,created TEXT);
 CREATE TABLE IF NOT EXISTS checkins(user_id INTEGER,day TEXT,UNIQUE(user_id,day));
 CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY,user_id INTEGER,kind TEXT,amount INTEGER,phone TEXT,name TEXT,status TEXT,created TEXT);
 CREATE TABLE IF NOT EXISTS announcements(id INTEGER PRIMARY KEY,title TEXT NOT NULL,body TEXT NOT NULL,created TEXT NOT NULL);""")
# Safe migration for per-product validity days.
with con() as c:
 try:
  c.execute("ALTER TABLE projects ADD COLUMN days INTEGER DEFAULT 60")
 except sqlite3.OperationalError:
  pass

# Safe migrations for deposit payment details on existing databases.
with con() as c:
 for column, definition in [("network", "TEXT DEFAULT ''"), ("reference", "TEXT DEFAULT ''")]:
  try: c.execute(f"ALTER TABLE requests ADD COLUMN {column} {definition}")
  except sqlite3.OperationalError: pass

# Withdrawal fee and requested amount fields.
with con() as c:
 for column, definition in [
  ("requested_amount", "INTEGER DEFAULT 0"),
  ("fee", "INTEGER DEFAULT 0")
 ]:
  try:
   c.execute(f"ALTER TABLE requests ADD COLUMN {column} {definition}")
  except sqlite3.OperationalError:
   pass


# NATUREGROW_ADMIN_PANEL_V1: persistent admin product overrides
with con() as c:
 c.execute("CREATE TABLE IF NOT EXISTS admin_products (pid INTEGER PRIMARY KEY, name TEXT NOT NULL, price INTEGER NOT NULL, daily INTEGER NOT NULL, days INTEGER NOT NULL DEFAULT 60, image TEXT NOT NULL, sold_out INTEGER NOT NULL DEFAULT 0)")
 for _p in P:
  c.execute("INSERT OR IGNORE INTO admin_products(pid,name,price,daily,days,image,sold_out) VALUES(?,?,?,?,?,?,?)", (_p['id'],_p['name'],_p['price'],_p['daily'],_p.get('days',60),_p['image'],1 if _p.get('sold_out') else 0))
 _saved = c.execute("SELECT * FROM admin_products ORDER BY pid").fetchall()
 for _row in _saved:
  _p = next((x for x in P if x['id'] == _row['pid']), None)
  if _p:
   _p.update(name=_row['name'], price=_row['price'], daily=_row['daily'], days=_row['days'], image=_row['image'])
   if _row['sold_out']:
    _p['sold_out'] = True
   else:
    _p.pop('sold_out', None)

def process_due_earnings(uid):
 # Catch up full 24-hour earning periods, limited to each product's validity.
 # A unique project/day key prevents duplicate credits.
 now = datetime.now()
 with con() as c:
  c.execute("CREATE TABLE IF NOT EXISTS project_earnings (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, user_id INTEGER NOT NULL, day_no INTEGER NOT NULL, amount INTEGER NOT NULL, credited_at TEXT NOT NULL, UNIQUE(project_id, day_no))")
  cols = {r["name"] for r in c.execute("PRAGMA table_info(projects)").fetchall()}
  if "days" not in cols:
   c.execute("ALTER TABLE projects ADD COLUMN days INTEGER DEFAULT 60")
  rows = c.execute("SELECT * FROM projects WHERE user_id=? ORDER BY id", (uid,)).fetchall()
  for project in rows:
   try:
    start = datetime.fromisoformat(str(project["created"]).replace("Z", "+00:00"))
    if start.tzinfo is not None:
     start = start.replace(tzinfo=None)
    validity = max(1, int(project["days"] or 60))
    elapsed = max(0, int((now - start).total_seconds() // 86400))
    due = min(validity, elapsed)
    existing = c.execute("SELECT COUNT(*) n FROM project_earnings WHERE project_id=?", (project["id"],)).fetchone()["n"]
    for day_no in range(int(existing) + 1, due + 1):
     amount = max(0, int(project["daily"] or 0))
     cur = c.execute("INSERT OR IGNORE INTO project_earnings(project_id,user_id,day_no,amount,credited_at) VALUES(?,?,?,?,?)", (project["id"], uid, day_no, amount, now.isoformat()))
     if cur.rowcount:
      c.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, uid))
      c.execute("INSERT INTO tx(user_id,kind,amount,note,status,created) VALUES(?,?,?,?,?,?)", (uid, "Product Income", amount, str(project["product"]) + " daily income (day " + str(day_no) + ")", "Completed", now.isoformat()))
   except (ValueError, TypeError, KeyError):
    continue

def user():
 if "uid" not in session:return None
 uid = session["uid"]
 with con() as c:
  exists = c.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone()
 if not exists:return None
 process_due_earnings(uid)
 with con() as c:return c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
def need(f):
 @wraps(f)
 def w(*a,**k):
  if not user():return redirect(url_for("login"))
  return f(*a,**k)
 return w
def money(x):return "UGX "+format(int(x),",")
@app.context_processor
def globals():return {"active_user":user(),"money":money,"products":P}

ADMIN_PHONE = "0758878297"


def ng_credit_referral_commissions(c, deposit_id, depositor_id, deposit_amount, stamp):
    c.execute("""CREATE TABLE IF NOT EXISTS referral_commissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        deposit_request_id INTEGER NOT NULL,
        referrer_id INTEGER NOT NULL,
        level INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        created TEXT NOT NULL,
        UNIQUE(deposit_request_id, referrer_id, level)
    )""")
    current = int(depositor_id)
    visited = {current}
    for level, rate in enumerate((15, 3, 2), 1):
        row = c.execute("SELECT referrer FROM users WHERE id=?", (current,)).fetchone()
        if not row or row["referrer"] is None:
            break
        referrer = int(row["referrer"])
        if referrer in visited:
            break
        visited.add(referrer)
        current = referrer
        amount = int(deposit_amount) * rate // 100
        if amount <= 0:
            continue
        cur = c.execute("""INSERT OR IGNORE INTO referral_commissions
            (deposit_request_id,referrer_id,level,amount,created)
            VALUES(?,?,?,?,?)""", (deposit_id, referrer, level, amount, stamp))
        if cur.rowcount:
            c.execute("UPDATE users SET balance=COALESCE(balance,0)+? WHERE id=?", (amount, referrer))
            c.execute("""INSERT INTO tx(user_id,kind,amount,note,status,created)
                VALUES(?,?,?,?,?,?)""",
                (referrer, "Referral Commission", amount,
                 "Level %d commission from deposit #%d" % (level, deposit_id),
                 "Completed", stamp))

def ng_ensure_tables():
 with con() as c:
  c.execute("CREATE TABLE IF NOT EXISTS project_earnings (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, user_id INTEGER NOT NULL, day_no INTEGER NOT NULL, amount INTEGER NOT NULL, credited_at TEXT NOT NULL, UNIQUE(project_id,day_no))")
  c.execute("CREATE TABLE IF NOT EXISTS product_controls (product_id INTEGER PRIMARY KEY, locked INTEGER NOT NULL DEFAULT 0, income_enabled INTEGER NOT NULL DEFAULT 1)")
  c.execute("CREATE TABLE IF NOT EXISTS admin_balance_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_user_id INTEGER, target_user_id INTEGER, old_balance INTEGER, new_balance INTEGER, reason TEXT, created TEXT)")

def ng_is_admin():
 u = user()
 if not u: return False
 digits = "".join(ch for ch in str(u["phone"] or "") if ch.isdigit())
 return digits.endswith("758878297")

def ng_admin_required(f):
 @wraps(f)
 def wrapped(*args, **kwargs):
  if not user(): return redirect(url_for("login"))
  if not ng_is_admin():
   flash("Administrator access only.", "error")
   return redirect(url_for("dashboard"))
  return f(*args, **kwargs)
 return wrapped

def ng_process_due_earnings(uid=None):
 # Credits only after full 86,400-second intervals from each purchase timestamp.
 ng_ensure_tables()
 now = datetime.now()
 with con() as c:
  if uid is None:
   rows = c.execute("SELECT * FROM projects ORDER BY id").fetchall()
  else:
   rows = c.execute("SELECT * FROM projects WHERE user_id=? ORDER BY id", (uid,)).fetchall()
  for p in rows:
   try:
    start = datetime.fromisoformat(str(p["created"]).replace("Z","+00:00"))
    if start.tzinfo is not None: start = start.astimezone().replace(tzinfo=None)
    cols = {r["name"] for r in c.execute("PRAGMA table_info(projects)").fetchall()}
    days = max(1, int(p["days"] or 60)) if "days" in cols else 60
    due = min(days, max(0, int((now-start).total_seconds() // 86400)))
    item = next((x for x in P if x["name"] == p["product"]), None)
    if item:
     ctl = c.execute("SELECT income_enabled FROM product_controls WHERE product_id=?", (item["id"],)).fetchone()
     if ctl and not ctl["income_enabled"]: continue
    done = {int(r["day_no"]) for r in c.execute("SELECT day_no FROM project_earnings WHERE project_id=?", (p["id"],)).fetchall()}
    for day_no in range(1, due+1):
     if day_no in done: continue
     amount = max(0, int(p["daily"] or 0))
     stamp = now.isoformat(timespec="seconds")
     cur = c.execute("INSERT OR IGNORE INTO project_earnings(project_id,user_id,day_no,amount,credited_at) VALUES(?,?,?,?,?)", (p["id"],p["user_id"],day_no,amount,stamp))
     if cur.rowcount:
      c.execute("UPDATE users SET balance=COALESCE(balance,0)+? WHERE id=?", (amount,p["user_id"]))
      c.execute("INSERT INTO tx(user_id,kind,amount,note,status,created) VALUES(?,?,?,?,?,?)", (p["user_id"],"Product Income",amount,str(p["product"])+" daily income day "+str(day_no),"Completed",stamp))
   except (ValueError, TypeError, KeyError):
    continue

ng_ensure_tables()


def ng_product_locked(pid):
 ng_ensure_tables()
 with con() as c:
  r=c.execute("SELECT locked FROM product_controls WHERE product_id=?",(pid,)).fetchone()
 return bool(r and r["locked"])

@app.route("/")
def index():return redirect(url_for("dashboard") if user() else url_for("login"))
@app.route("/register",methods=["GET","POST"])
def register():
 if request.method=="POST":
  n=request.form.get("username","").strip(); ph=request.form.get("phone","").strip(); pw=request.form.get("password",""); cp=request.form.get("confirm_password",""); inv=request.form.get("invite","").strip().upper()
  if not n or not ph or len(pw)<6 or pw!=cp:flash("Check username, phone and matching passwords (minimum 6 characters).","error")
  else:
   try:
    with con() as c:
     r=c.execute("SELECT id FROM users WHERE invite=?",(inv,)).fetchone() if inv else None
     cur=c.execute("INSERT INTO users(username,phone,password,invite,referrer,created) VALUES(?,?,?,?,?,?)",(n,ph,generate_password_hash(pw),secrets.token_hex(4).upper(),r["id"] if r else None,datetime.now().isoformat()))
     uid=cur.lastrowid;c.execute("INSERT INTO tx(user_id,kind,amount,note,status,created) VALUES(?,?,?,?,?,?)",(uid,"Account",0,"Account created","Completed",datetime.now().isoformat()))
    session["uid"]=uid;return redirect(url_for("dashboard"))
   except sqlite3.IntegrityError:flash("Username already exists.","error")
 return render_template("auth.html",mode="register")
@app.route("/login",methods=["GET","POST"])
def login():
 if request.method=="POST":
  with con() as c:u=c.execute("SELECT * FROM users WHERE username=?",(request.form.get("username","").strip(),)).fetchone()
  if u and check_password_hash(u["password"],request.form.get("password","")):session.clear();session["uid"]=u["id"];return redirect(url_for("dashboard"))
  flash("Incorrect username or password.","error")
 return render_template("auth.html",mode="login")
@app.route("/logout")
def logout():session.clear();return redirect(url_for("login"))
@app.route("/dashboard")
@need
def dashboard():
 u=user()
 with con() as c:active=c.execute("SELECT COUNT(*) n FROM projects WHERE user_id=?",(u["id"],)).fetchone()["n"]
 return render_template("dashboard.html",u=u,active=active)
@app.route("/products")
@need
def product_list():
 ng_ensure_tables()
 with con() as c: controls={r["product_id"]:r for r in c.execute("SELECT * FROM product_controls").fetchall()}
 for item in P:
  item["locked"]=bool(controls.get(item["id"]) and controls[item["id"]]["locked"])
  item["income_enabled"]=bool(controls.get(item["id"],{"income_enabled":1})["income_enabled"])
 return render_template("products.html")
@app.route("/invest/<int:pid>",methods=["POST"])
@need
def invest(pid):
 u=user();p=next((x for x in P if x["id"]==pid),None)
 if not p: return redirect(url_for("product_list"))
 if ng_product_locked(pid):
  flash("This product is currently locked.", "error")
  return redirect(url_for("product_list"))
 if p.get("sold_out", False):
  flash("Plot-7 is sold out and cannot be purchased.", "error")
  return redirect(url_for("product_list"))
 if u["balance"]<p["price"]:flash("Insufficient balance. Please deposit and wait for payment verification.","error");return redirect(url_for("product_list"))
 now=datetime.now().isoformat()
 with con() as c:
  c.execute("UPDATE users SET balance=balance-? WHERE id=?",(p["price"],u["id"]));c.execute("INSERT INTO projects(user_id,product,price,daily,days,created) VALUES(?,?,?,?,?,?)",(u["id"],p["name"],p["price"],p["daily"],p["days"],now));c.execute("INSERT INTO tx(user_id,kind,amount,note,status,created) VALUES(?,?,?,?,?,?)",(u["id"],"Investment",-p["price"],p["name"],"Completed",now))
 flash("Product purchased successfully.");return redirect(url_for("projects"))
@app.route("/projects")
@need
def projects():
 u = user()
 with con() as c:
  rows = c.execute("SELECT p.*, (SELECT COUNT(*) FROM project_earnings e WHERE e.project_id=p.id) AS credited_days FROM projects p WHERE p.user_id=? ORDER BY p.id DESC", (u["id"],)).fetchall()
 product_by_name = {p["name"]: p for p in P}
 return render_template("projects.html", rows=rows, product_by_name=product_by_name)
@app.route("/team")
@need
def team():
 u=user()
 with con() as c:
  refs=c.execute("SELECT username,created FROM users WHERE referrer=?",(u["id"],)).fetchall()
  earnings=c.execute("""SELECT COALESCE(SUM(amount),0) total FROM tx
      WHERE user_id=? AND lower(kind)='referral commission'
      AND lower(status)='completed'""",(u["id"],)).fetchone()["total"]
 return render_template("team.html",refs=refs,earnings=int(earnings or 0),invite=request.url_root.rstrip("/")+"/register?invite="+u["invite"])
@app.route("/deposit",methods=["GET","POST"])
@need
def deposit():
 if request.method == "POST":
  stage=request.form.get("stage", "continue")
  try: amount=int(request.form.get("amount", "0"))
  except: amount=0
  phone=request.form.get("phone", "").strip()
  network=request.form.get("network", "").strip()
  if amount < 5000 or not phone or network not in ("MTN", "Airtel"):
   flash("Enter an amount of at least UGX 5,000, your mobile money number, and select MTN or Airtel.", "error")
   return render_template("deposit.html", amount=amount if amount >= 5000 else "", phone=phone, network=network)
  if stage == "continue":
   return render_template("deposit.html", payment_stage=True, amount=amount, phone=phone, network=network)
  if stage == "confirm":
   reference=request.form.get("reference", "").strip()
   with con() as c:
    c.execute("INSERT INTO requests(user_id,kind,amount,phone,status,created,network,reference) VALUES(?,?,?,?,?,?,?,?)", (user()["id"], "Deposit", amount, phone, "Pending", datetime.now().isoformat(), network, reference))
   flash("Deposit request submitted. It stays pending until the payment is verified; your balance has not been credited yet.")
   return redirect(url_for("history"))
 return render_template("deposit.html", payment_stage=False)
@app.route("/withdraw",methods=["GET","POST"])
@need
def withdraw():
 u=user()
 if request.method=="POST":
  try:a=int(request.form.get("amount","0"))
  except (ValueError, TypeError):a=0
  ph=request.form.get("phone","").strip()
  name=request.form.get("name","").strip()
  if not name or not ph or a<5000 or a%1000:
   flash("Enter your name, phone and an amount of at least UGX 5,000 in multiples of UGX 1,000.","error")
  else:
   fee=a//10
   payout=a-fee
   now=datetime.now().isoformat()
   with con() as c:
    # Deduct the full request atomically; concurrent requests cannot overspend.
    result=c.execute(
     "UPDATE users SET balance=balance-? WHERE id=? AND balance>=?",
     (a,u["id"],a)
    )
    if result.rowcount != 1:
     flash("Insufficient available balance.","error")
     return redirect(url_for("withdraw"))

    # amount is the net payout; requested_amount and fee preserve the full breakdown.
    c.execute("""INSERT INTO requests
     (user_id,kind,amount,phone,name,status,created,requested_amount,fee)
     VALUES(?,?,?,?,?,?,?,?,?)""",
     (u["id"],"Withdrawal",payout,ph,name,"Pending",now,a,fee))

    c.execute("""INSERT INTO tx
     (user_id,kind,amount,note,status,created)
     VALUES(?,?,?,?,?,?)""",
     (u["id"],"Withdrawal",-a,
      f"Request UGX {a:,}; fee UGX {fee:,}; payout UGX {payout:,}",
      "Pending",now))

   flash(f"Withdrawal submitted. UGX {a:,} deducted; fee UGX {fee:,}; payout UGX {payout:,} pending processing.")
   return redirect(url_for("history"))
 return render_template("withdraw.html",u=u)

@app.route("/checkin", methods=["GET", "POST"])
@need
def checkin():
    from datetime import timedelta

    u = user()
    now = datetime.now().astimezone()

    with con() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS checkin_claims (
                user_id INTEGER PRIMARY KEY,
                claimed_at TEXT NOT NULL
            )
        """)

    def get_claim(c):
        row = c.execute(
            "SELECT claimed_at FROM checkin_claims WHERE user_id=?",
            (u["id"],)
        ).fetchone()
        if not row:
            return None
        last = datetime.fromisoformat(row["claimed_at"])
        if last.tzinfo is None:
            last = last.astimezone()
        return last

    def remaining(last, current):
        if last is None:
            return 0
        return max(0, int((last + timedelta(hours=24) - current).total_seconds()))

    if request.method == "POST":
        with con() as c:
            c.execute("BEGIN IMMEDIATE")

            active = c.execute(
                "SELECT 1 FROM projects WHERE user_id=? LIMIT 1",
                (u["id"],)
            ).fetchone()

            last = get_claim(c)
            seconds_left = remaining(last, now)

            if not active:
                flash(
                    "You're not eligible for rewards. Please have an active product first.",
                    "error"
                )
            elif seconds_left > 0:
                flash("Your next reward is available after the 24-hour timer ends.", "error")
            else:
                stamp = now.isoformat()
                c.execute("""
                    INSERT INTO checkin_claims(user_id, claimed_at)
                    VALUES(?, ?)
                    ON CONFLICT(user_id)
                    DO UPDATE SET claimed_at=excluded.claimed_at
                """, (u["id"], stamp))

                c.execute(
                    "UPDATE users SET balance=balance+1000 WHERE id=?",
                    (u["id"],)
                )
                c.execute("""
                    INSERT INTO tx(user_id,kind,amount,note,status,created)
                    VALUES(?,?,?,?,?,?)
                """, (
                    u["id"], "Bonus", 1000,
                    "Daily Nature Bonus", "Completed", stamp
                ))
                flash("UGX 1,000 Daily Nature Bonus added to your balance.")

    with con() as c:
        active = c.execute(
            "SELECT 1 FROM projects WHERE user_id=? LIMIT 1",
            (u["id"],)
        ).fetchone() is not None
        last_claim = get_claim(c)

    seconds_left = remaining(last_claim, now)
    claimed = seconds_left > 0

    return render_template(
        "checkin.html",
        claimed=claimed,
        eligible=active,
        seconds_left=seconds_left,
        last_claim=last_claim,
        checked_label=last_claim.astimezone().strftime("%I:%M %p") if last_claim else ""
    )

@app.route("/history")
@need
def history():
 with con() as c:rows=c.execute("SELECT * FROM tx WHERE user_id=? ORDER BY id DESC",(user()["id"],)).fetchall();reqs=c.execute("SELECT * FROM requests WHERE user_id=? ORDER BY id DESC",(user()["id"],)).fetchall()
 return render_template("history.html",rows=rows,reqs=reqs)
@app.route("/announcements")
@need
def announcements():
 defaults = [
  ("🌱 Products — View Available Products", "Open Products to view available products, prices, advertised daily income and validity. Review the terms carefully before making a purchase."),
  ("💳 How to Deposit", "Open Deposit, enter your amount, select the available MTN or Airtel payment option, and follow the payment instructions displayed. Keep your transaction confirmation. Never share your mobile money PIN or verification code."),
  ("🌿 How to Check In Daily", "Open Daily Check-in if available, review the eligibility requirements, and follow the claim instructions. An active product may be required. Check the confirmation message after claiming."),
  ("👥 Invite Friends", "Open Referrals to find your invite link or code. Share it with friends and review the referral terms to understand eligibility and applicable rewards."),
  ("💸 How to Withdraw", "Open Withdraw, enter the requested details, and review the amount, fees and displayed requirements before submitting. Keep your transaction reference and contact support if your request remains pending."),
  ("📊 Understand Product Earnings", "Review each product's price, advertised daily income, validity and total displayed earnings before purchasing. Earnings are not guaranteed and depend on the platform's actual terms and performance."),
  ("🔐 Keep Your Account Secure", "Use a strong, unique password. Never share your password, mobile money PIN or verification code. Use only the official payment instructions shown on the platform."),
  ("🎧 Need Help? Contact Support", "Open Support and describe your issue clearly. Include a transaction reference when relevant, but never send your password or mobile money PIN."),
  ("📢 Check Announcements Regularly", "Visit this page for platform guidance and updates. Check the latest information before making transactions.")
 ]
 from datetime import datetime
 from zoneinfo import ZoneInfo
 now = datetime.now(ZoneInfo("Africa/Kampala")).strftime("%Y-%m-%d %H:%M:%S")
 with con() as c:
  for title, body in defaults:
   c.execute("INSERT INTO announcements (title,body,created) SELECT ?,?,? WHERE NOT EXISTS (SELECT 1 FROM announcements WHERE title=?)", (title,body,now,title))
  rows=c.execute("SELECT title,body,created FROM announcements ORDER BY id DESC").fetchall()
 return render_template("announcements.html",rows=rows)
@app.route("/support")
@need
def support():return render_template("support.html")
@app.route("/profile")
@need
def profile():
 u=user()
 with con() as c:
  rows=c.execute("SELECT * FROM projects WHERE user_id=? ORDER BY id DESC",(u["id"],)).fetchall()
 active=len(rows)
 harvest=sum(int(r["daily"])*int(r["days"] or 60) for r in rows)
 return render_template("profile.html",u=u,rows=rows,active=active,harvest=harvest)
@app.route("/settings",methods=["GET","POST"])
@need
def settings():
 if request.method=="POST":
  p=request.form.get("password","");q=request.form.get("confirm","")
  if len(p)<6 or p!=q:flash("Passwords must match and be at least 6 characters.","error")
  else:
   with con() as c:c.execute("UPDATE users SET password=? WHERE id=?",(generate_password_hash(p),user()["id"]))
   flash("Password updated.");return redirect(url_for("settings"))
 return render_template("settings.html")


# NATUREGROW_ADMIN_PANEL_V1: secure admin panel
import os as _admin_os
from werkzeug.utils import secure_filename as _admin_secure_filename
_ADMIN_PHONE = ''.join(ch for ch in _admin_os.environ.get('NATUREGROW_ADMIN_PHONE', '0758878297') if ch.isdigit())
def _admin_phone_matches(value):
 digits = ''.join(ch for ch in (value or '') if ch.isdigit())
 return digits == _ADMIN_PHONE or (digits.startswith('256') and ('0' + digits[3:]) == _ADMIN_PHONE) or (_ADMIN_PHONE.startswith('0') and digits == '256' + _ADMIN_PHONE[1:])
def _is_admin():
 u = user()
 return bool(u and _admin_phone_matches(u['phone']))
def admin_need(f):
 @wraps(f)
 def _wrapped(*args, **kwargs):
  if not user():
   return redirect(url_for('login'))
  if not _is_admin():
   flash('You are not authorized to access the admin panel.', 'error')
   return redirect(url_for('dashboard'))
  return f(*args, **kwargs)
 return _wrapped

@app.route('/admin', methods=['GET', 'POST'])
@admin_need
def admin_panel():
 if request.method == 'POST':
  action = request.form.get('action', '')
  now = datetime.now().isoformat()
  with con() as c:
   if action in ('approve_deposit', 'reject_deposit', 'approve_withdrawal', 'reject_withdrawal'):
    rid = request.form.get('request_id', type=int)
    r = c.execute('SELECT * FROM requests WHERE id=?', (rid,)).fetchone() if rid else None
    if not r:
     flash('Request not found.', 'error')
    elif str(r['status']).lower() not in ('pending', 'submitted', 'processing'):
     flash('This request has already been processed.', 'error')
    else:
     is_deposit = 'deposit' in action
     approve = action.startswith('approve')
     if is_deposit and approve:
      c.execute('UPDATE users SET balance=COALESCE(balance,0)+? WHERE id=?', (int(r['amount']), r['user_id']))
      c.execute('INSERT INTO tx(user_id,kind,amount,note,status,created) VALUES(?,?,?,?,?,?)', (r['user_id'], 'Deposit', int(r['amount']), 'Deposit request #' + str(r['id']) + ' approved', 'Completed', now))
      ng_credit_referral_commissions(c, r['id'], r['user_id'], int(r['amount']), now)
     if not is_deposit and approve:
      c.execute('INSERT INTO tx(user_id,kind,amount,note,status,created) VALUES(?,?,?,?,?,?)', (r['user_id'], 'Withdrawal', -int(r['amount']), 'Withdrawal request #' + str(r['id']) + ' approved', 'Completed', now))
     if not is_deposit and not approve:
      # Withdrawal amounts may have been deducted when requested; refund on rejection.
      refund = int(r['requested_amount'] or 0) if 'requested_amount' in r.keys() and int(r['requested_amount'] or 0) > 0 else int(r['amount'])
      c.execute('UPDATE users SET balance=COALESCE(balance,0)+? WHERE id=?', (refund, r['user_id']))
      c.execute('INSERT INTO tx(user_id,kind,amount,note,status,created) VALUES(?,?,?,?,?,?)', (r['user_id'], 'Withdrawal refund', refund, 'Rejected withdrawal request #' + str(r['id']), 'Completed', now))
     status = 'Approved' if approve else 'Rejected'
     c.execute('UPDATE requests SET status=? WHERE id=?', (status, r['id']))
     flash(('Deposit' if is_deposit else 'Withdrawal') + ' request ' + status.lower() + '.', 'success')
   elif action == 'edit_balance':
    uid = request.form.get('user_id', type=int); amount = request.form.get('balance', type=int)
    target = c.execute('SELECT id,balance FROM users WHERE id=?', (uid,)).fetchone() if uid else None
    if target and amount is not None and amount >= 0:
     delta = amount - int(target['balance'] or 0)
     c.execute('UPDATE users SET balance=? WHERE id=?', (amount, uid))
     c.execute('INSERT INTO tx(user_id,kind,amount,note,status,created) VALUES(?,?,?,?,?,?)', (uid, 'Admin balance adjustment', delta, 'Balance set by administrator', 'Completed', now))
     flash('User balance updated.', 'success')
    else: flash('Enter a valid user and non-negative balance.', 'error')
   elif action == 'change_password':
    uid = request.form.get('user_id', type=int); pw = request.form.get('new_password', '')
    target = c.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone() if uid else None
    if not target or len(pw) < 8:
     flash('Choose a user and a password of at least 8 characters.', 'error')
    else:
     hashed = generate_password_hash(pw)
     cols = {x['name'] for x in c.execute('PRAGMA table_info(users)').fetchall()}
     if 'password' in cols: c.execute('UPDATE users SET password=? WHERE id=?', (hashed, uid))
     if 'password_hash' in cols: c.execute('UPDATE users SET password_hash=? WHERE id=?', (hashed, uid))
     flash('Password changed securely.', 'success')
   elif action == 'publish_announcement':
    title = request.form.get('title', '').strip(); body = request.form.get('body', '').strip()
    if title and body:
     c.execute('INSERT INTO announcements(title,body,created) VALUES(?,?,?)', (title[:150], body[:5000], now))
     flash('Announcement published to the existing Announcements page.', 'success')
    else: flash('Enter both a title and message.', 'error')
   elif action == 'edit_product':
    pid = request.form.get('product_id', type=int)
    product = next((x for x in P if x['id'] == pid), None)
    name = request.form.get('name', '').strip()
    price = request.form.get('price', type=int); daily = request.form.get('daily', type=int); days = request.form.get('days', type=int)
    sold = 1 if request.form.get('sold_out') == '1' else 0
    if not product or not name or price is None or daily is None or days is None or price < 0 or daily < 0 or days < 1:
     flash('Check product name, price, daily income and validity.', 'error')
    else:
     image = product.get('image', 'farm1.jpg')
     upload = request.files.get('image')
     if upload and upload.filename:
      filename = _admin_secure_filename(upload.filename)
      ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
      if ext not in ('jpg', 'jpeg', 'png', 'webp'):
       flash('Product images must be JPG, JPEG, PNG or WEBP.', 'error')
       return redirect(url_for('admin_panel', tab='products'))
      filename = 'admin_product_' + str(pid) + '.' + ext
      folder = _admin_os.path.join(app.root_path, 'static', 'images')
      _admin_os.makedirs(folder, exist_ok=True)
      upload.save(_admin_os.path.join(folder, filename))
      image = filename
     product.update(name=name, price=price, daily=daily, days=days, image=image)
     if sold: product['sold_out'] = True
     else: product.pop('sold_out', None)
     c.execute('UPDATE admin_products SET name=?,price=?,daily=?,days=?,image=?,sold_out=? WHERE pid=?', (name,price,daily,days,image,sold,pid))
     flash('Product updated.', 'success')
   else:
    flash('Unknown admin action.', 'error')
  return redirect(url_for('admin_panel', tab=request.form.get('tab', 'overview')))

 tab = request.args.get('tab', 'overview')
 q = request.args.get('q', '').strip()
 with con() as c:
  counts = {
   'users': c.execute('SELECT COUNT(*) n FROM users').fetchone()['n'],
   'pending_deposits': c.execute("SELECT COUNT(*) n FROM requests WHERE lower(kind) LIKE '%deposit%' AND lower(status) IN ('pending','submitted','processing')").fetchone()['n'],
   'pending_withdrawals': c.execute("SELECT COUNT(*) n FROM requests WHERE lower(kind) LIKE '%withdraw%' AND lower(status) IN ('pending','submitted','processing')").fetchone()['n'],
   'products': len(P),
  }
  users = c.execute("SELECT u.*, (SELECT COUNT(*) FROM requests r WHERE r.user_id=u.id AND lower(r.kind) LIKE '%deposit%' AND lower(r.status) IN ('approved','completed')) AS deposited FROM users u WHERE (?='' OR u.username LIKE ? OR u.phone LIKE ? OR CAST(u.id AS TEXT)=?) ORDER BY u.id DESC LIMIT 250", (q, '%' + q + '%', '%' + q + '%', q)).fetchall()
  deposits = c.execute("SELECT r.*,u.username,u.phone FROM requests r LEFT JOIN users u ON u.id=r.user_id WHERE lower(r.kind) LIKE '%deposit%' ORDER BY r.id DESC LIMIT 200").fetchall()
  withdrawals = c.execute("SELECT r.*,u.username,u.phone FROM requests r LEFT JOIN users u ON u.id=r.user_id WHERE lower(r.kind) LIKE '%withdraw%' ORDER BY r.id DESC LIMIT 200").fetchall()
  teams = c.execute("SELECT u.id,u.username,u.phone,u.referrer,u.balance,u.created,(SELECT COUNT(*) FROM users v WHERE v.referrer=u.id) AS team_size FROM users u ORDER BY u.id DESC LIMIT 250").fetchall()
  announcements = c.execute('SELECT title,body,created FROM announcements ORDER BY id DESC LIMIT 50').fetchall()
  requests_user_col = {x['name'] for x in c.execute('PRAGMA table_info(users)').fetchall()}
  # Admin listing supports older databases with a different full-name column.
  product_rows = list(P)
 return render_template('admin.html', tab=tab, q=q, counts=counts, users=users, deposits=deposits, withdrawals=withdrawals, teams=teams, announcements=announcements, product_rows=product_rows)



@app.route("/admin")
@ng_admin_required
def ng_admin_panel():
 ng_process_due_earnings()
 with con() as c:
  users=c.execute("SELECT u.*, (SELECT COUNT(*) FROM users t WHERE t.referrer=u.id) team_count, CASE WHEN EXISTS(SELECT 1 FROM requests r WHERE r.user_id=u.id AND lower(r.kind)='deposit' AND lower(r.status) IN ('approved','completed')) THEN 1 ELSE 0 END has_deposit FROM users u ORDER BY u.id DESC LIMIT 300").fetchall()
  reqs=c.execute("SELECT r.*,u.username,u.phone account_phone FROM requests r LEFT JOIN users u ON u.id=r.user_id ORDER BY r.id DESC LIMIT 300").fetchall()
  controls={r["product_id"]:r for r in c.execute("SELECT * FROM product_controls").fetchall()}
 items=[]
 for p in P:
  q=dict(p); ctl=controls.get(p["id"]); q["locked"]=bool(ctl and ctl["locked"]); q["income_enabled"]=bool(ctl["income_enabled"]) if ctl else True; items.append(q)
 return render_template("admin.html",users=users,requests_rows=reqs,items=items)

@app.route("/admin/request/<int:rid>",methods=["POST"])
@ng_admin_required
def ng_admin_request(rid):
 action=request.form.get("action","").lower()
 if action not in ("approve","reject"):
  flash("Invalid action.","error"); return redirect(url_for("ng_admin_panel"))
 with con() as c:
  r=c.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone()
  if not r: flash("Request not found.","error"); return redirect(url_for("ng_admin_panel"))
  if str(r["status"] or "").lower() not in ("pending","waiting"):
   flash("Request already processed.","error"); return redirect(url_for("ng_admin_panel"))
  if action=="reject": c.execute("UPDATE requests SET status='Rejected' WHERE id=?",(rid,))
  elif str(r["kind"] or "").lower()=="deposit":
   c.execute("UPDATE requests SET status='Approved' WHERE id=?",(rid,))
   c.execute("UPDATE users SET balance=COALESCE(balance,0)+? WHERE id=?",(int(r["amount"] or 0),r["user_id"]))
   now=datetime.now().isoformat()
   c.execute("INSERT INTO tx(user_id,kind,amount,note,status,created) VALUES(?,?,?,?,?,?)",(r["user_id"],"Deposit",int(r["amount"] or 0),"Admin approved request #"+str(rid),"Completed",now))
   ng_credit_referral_commissions(c, r["id"], r["user_id"], int(r["amount"] or 0), now)
  elif str(r["kind"] or "").lower()=="withdraw":
   c.execute("UPDATE requests SET status='Approved' WHERE id=?",(rid,))
  else:
   flash("Unknown request kind.","error"); return redirect(url_for("ng_admin_panel"))
 flash("Request "+action+"ed.")
 return redirect(url_for("ng_admin_panel"))

@app.route("/admin/user/<int:uid>/balance",methods=["POST"])
@ng_admin_required
def ng_admin_balance(uid):
 try:
  value=int(request.form.get("balance",""))
  if value<0: raise ValueError()
 except ValueError:
  flash("Enter a non-negative whole-number balance.","error"); return redirect(url_for("ng_admin_panel"))
 now=datetime.now().isoformat(); reason=request.form.get("reason","Admin adjustment")[:200]
 with con() as c:
  r=c.execute("SELECT balance FROM users WHERE id=?",(uid,)).fetchone()
  if not r: flash("User not found.","error"); return redirect(url_for("ng_admin_panel"))
  old=int(r["balance"] or 0); c.execute("UPDATE users SET balance=? WHERE id=?",(value,uid))
  c.execute("INSERT INTO admin_balance_audit(admin_user_id,target_user_id,old_balance,new_balance,reason,created) VALUES(?,?,?,?,?,?)",(user()["id"],uid,old,value,reason,now))
  c.execute("INSERT INTO tx(user_id,kind,amount,note,status,created) VALUES(?,?,?,?,?,?)",(uid,"Admin Adjustment",value-old,reason,"Completed",now))
 flash("Balance updated."); return redirect(url_for("ng_admin_panel"))

@app.route("/admin/user/<int:uid>/password",methods=["POST"])
@ng_admin_required
def ng_admin_password(uid):
 password=request.form.get("password","")
 if len(password)<8: flash("Password must contain at least 8 characters.","error"); return redirect(url_for("ng_admin_panel"))
 with con() as c:
  cols={r["name"] for r in c.execute("PRAGMA table_info(users)").fetchall()}
  field="password_hash" if "password_hash" in cols and "password" not in cols else "password"
  c.execute("UPDATE users SET "+field+"=? WHERE id=?",(generate_password_hash(password),uid))
 flash("Password changed."); return redirect(url_for("ng_admin_panel"))

@app.route("/admin/product/<int:pid>",methods=["POST"])
@ng_admin_required
def ng_admin_product(pid):
 if not any(p["id"]==pid for p in P): flash("Product not found.","error"); return redirect(url_for("ng_admin_panel"))
 locked=1 if request.form.get("locked")=="1" else 0
 income=1 if request.form.get("income_enabled")=="1" else 0
 with con() as c:
  c.execute("INSERT INTO product_controls(product_id,locked,income_enabled) VALUES(?,?,?) ON CONFLICT(product_id) DO UPDATE SET locked=excluded.locked,income_enabled=excluded.income_enabled",(pid,locked,income))
 flash("Product settings saved."); return redirect(url_for("ng_admin_panel"))

@app.route("/internal/daily-earnings",methods=["GET"])
def ng_daily_earnings_job():
 ng_process_due_earnings()
 return "Daily earnings processed",200


def ng_ensure_deposit_pending_request():
 # This wrapper runs after the existing deposit view, so its normal validation and payment flow remain intact.
 original = app.view_functions.get("deposit")
 if original is None or getattr(original, "_ng_pending_wrapper", False): return
 @wraps(original)
 def wrapped(*args, **kwargs):
  before_uid = session.get("uid")
  response = original(*args, **kwargs)
  if request.method == "POST" and before_uid:
   try:
    amount = int(request.form.get("amount", "0"))
   except (TypeError, ValueError):
    amount = 0
   phone = (request.form.get("phone") or request.form.get("payment_phone") or request.form.get("number") or "").strip()
   network = (request.form.get("network") or "").strip()
   # Avoid creating requests for blank/invalid submissions.
   if amount >= 5000 and phone and network:
    with con() as c:
     recent = c.execute("SELECT id FROM requests WHERE user_id=? AND lower(kind)='deposit' AND amount=? AND phone=? AND lower(status) IN ('pending','waiting') ORDER BY id DESC LIMIT 1", (before_uid, amount, phone)).fetchone()
     if not recent:
      c.execute("INSERT INTO requests(user_id,kind,amount,phone,name,status,created,network,reference) VALUES(?,?,?,?,?,?,?,?,?)",
       (before_uid,"deposit",amount,phone,"","Pending",datetime.now().isoformat(),network,(request.form.get("reference") or "").strip()))
  return response
 wrapped._ng_pending_wrapper = True
 app.view_functions["deposit"] = wrapped

ng_ensure_deposit_pending_request()

if __name__=="__main__":app.run(debug=True)


@app.route("/admin/earnings-report")
@ng_admin_required
def ng_earnings_report():
 from datetime import datetime
 with con() as c:
  rows = c.execute("""
   SELECT p.*, u.username, u.balance,
          COALESCE((SELECT COUNT(*) FROM project_earnings e
                    WHERE e.project_id=p.id),0) AS credited_days,
          COALESCE((SELECT SUM(e.amount) FROM project_earnings e
                    WHERE e.project_id=p.id),0) AS credited_total
   FROM projects p
   LEFT JOIN users u ON u.id=p.user_id
   ORDER BY p.id DESC
  """).fetchall()

 report = []
 now = datetime.now()

 for p in rows:
  try:
   start = datetime.fromisoformat(str(p["created"]).replace("Z","+00:00"))
   if start.tzinfo:
    start = start.astimezone().replace(tzinfo=None)
   elapsed = max(0, int((now-start).total_seconds() // 86400))
   due = min(max(1,int(p["days"] or 60)), elapsed)
  except (ValueError, TypeError):
   elapsed, due = 0, 0

  credited = int(p["credited_days"] or 0)
  expected = due * int(p["daily"] or 0)
  actual = int(p["credited_total"] or 0)

  if credited >= due and actual >= expected:
   status = "CREDITED"
  elif due > credited:
   status = "DUE - NOT YET CREDITED"
  else:
   status = "CHECK RECORDS"

  report.append({
   "id":p["id"], "username":p["username"] or "Unknown",
   "product":p["product"], "created":p["created"],
   "daily":p["daily"], "due":due, "credited":credited,
   "expected":expected, "actual":actual,
   "balance":p["balance"] or 0, "status":status
  })

 return render_template("earnings_report.html", rows=report)
