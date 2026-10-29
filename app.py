import os,sqlite3,secrets
from datetime import datetime,date
from functools import wraps
from flask import Flask,render_template,request,redirect,url_for,session,flash
from werkzeug.security import generate_password_hash,check_password_hash
app=Flask(__name__); app.secret_key=os.environ.get("SECRET_KEY","change-me-before-deployment")
DB=os.environ.get("DATABASE_PATH","naturegrow.db")
P=[{"id":1,"name":"Plot-1","price":45000,"daily":9000,"image":"farm1.jpg"},{"id":2,"name":"Plot-2","price":60000,"daily":12000,"image":"farm2.jpg"},{"id":3,"name":"Plot-3","price":100000,"daily":20000,"image":"farm3.jpg"},{"id":4,"name":"Plot-4","price":250000,"daily":31000,"image":"farm1.jpg"},{"id":5,"name":"Plot-5","price":500000,"daily":55000,"image":"farm2.jpg"},{"id":6,"name":"Plot-6","price":1000000,"daily":160000,"image":"farm3.jpg"},{"id":7,"name":"Plot-7","price":2000000,"daily":220000,"image":"farm1.jpg"},{"id":8,"name":"Plot-8","price":5000000,"daily":434200,"image":"farm2.jpg"}]
def con(): 
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
with con() as c:
 c.executescript("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,phone TEXT,password TEXT,invite TEXT UNIQUE,referrer INTEGER,balance INTEGER DEFAULT 0,created TEXT);
 CREATE TABLE IF NOT EXISTS tx(id INTEGER PRIMARY KEY,user_id INTEGER,kind TEXT,amount INTEGER,note TEXT,status TEXT,created TEXT);
 CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY,user_id INTEGER,product TEXT,price INTEGER,daily INTEGER,created TEXT);
 CREATE TABLE IF NOT EXISTS checkins(user_id INTEGER,day TEXT,UNIQUE(user_id,day));
 CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY,user_id INTEGER,kind TEXT,amount INTEGER,phone TEXT,name TEXT,status TEXT,created TEXT);
 CREATE TABLE IF NOT EXISTS announcements(id INTEGER PRIMARY KEY,title TEXT NOT NULL,body TEXT NOT NULL,created TEXT NOT NULL);""")
def user():
 if "uid" not in session:return None
 with con() as c:return c.execute("SELECT * FROM users WHERE id=?",(session["uid"],)).fetchone()
def need(f):
 @wraps(f)
 def w(*a,**k):
  if not user():return redirect(url_for("login"))
  return f(*a,**k)
 return w
def money(x):return "UGX "+format(int(x),",")
@app.context_processor
def globals():return {"active_user":user(),"money":money,"products":P}
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
def product_list():return render_template("products.html")
@app.route("/invest/<int:pid>",methods=["POST"])
@need
def invest(pid):
 u=user();p=next((x for x in P if x["id"]==pid),None)
 if not p: return redirect(url_for("product_list"))
 if u["balance"]<p["price"]:flash("Insufficient balance. Please deposit and wait for payment verification.","error");return redirect(url_for("product_list"))
 now=datetime.now().isoformat()
 with con() as c:
  c.execute("UPDATE users SET balance=balance-? WHERE id=?",(p["price"],u["id"]));c.execute("INSERT INTO projects(user_id,product,price,daily,created) VALUES(?,?,?,?,?)",(u["id"],p["name"],p["price"],p["daily"],now));c.execute("INSERT INTO tx(user_id,kind,amount,note,status,created) VALUES(?,?,?,?,?,?)",(u["id"],"Investment",-p["price"],p["name"],"Completed",now))
 flash("Product purchased successfully.");return redirect(url_for("projects"))
@app.route("/projects")
@need
def projects():
 with con() as c:rows=c.execute("SELECT * FROM projects WHERE user_id=? ORDER BY id DESC",(user()["id"],)).fetchall()
 return render_template("projects.html",rows=rows)
@app.route("/team")
@need
def team():
 u=user()
 with con() as c:refs=c.execute("SELECT username,created FROM users WHERE referrer=?",(u["id"],)).fetchall()
 return render_template("team.html",refs=refs,invite=request.url_root.rstrip("/")+"/register?invite="+u["invite"])
@app.route("/deposit",methods=["GET","POST"])
@need
def deposit():
 if request.method=="POST":
  try:a=int(request.form.get("amount","0"))
  except:a=0
  ph=request.form.get("phone","").strip()
  if a<5000 or not ph:flash("Enter at least UGX 5,000 and a phone number.","error")
  else:
   with con() as c:c.execute("INSERT INTO requests(user_id,kind,amount,phone,status,created) VALUES(?,?,?,?,?,?)",(user()["id"],"Deposit",a,ph,"Pending",datetime.now().isoformat()))
   flash("Deposit request submitted. Your balance will update after payment verification.");return redirect(url_for("history"))
 return render_template("deposit.html")
@app.route("/withdraw",methods=["GET","POST"])
@need
def withdraw():
 u=user()
 if request.method=="POST":
  try:a=int(request.form.get("amount","0"))
  except:a=0
  ph=request.form.get("phone","").strip();name=request.form.get("name","").strip()
  if not name or not ph or a<5000 or a%1000:flash("Enter name, phone and amount of at least UGX 5,000 in multiples of 1,000.","error")
  elif a>u["balance"]:flash("Insufficient available balance.","error")
  else:
   with con() as c:
    pending=c.execute("SELECT COALESCE(SUM(amount),0) n FROM requests WHERE user_id=? AND kind='Withdrawal' AND status='Pending'",(u["id"],)).fetchone()["n"]
    if a > u["balance"]-pending:
     flash("Your amount exceeds the available balance after pending withdrawals.","error")
     return redirect(url_for("withdraw"))
    c.execute("INSERT INTO requests(user_id,kind,amount,phone,name,status,created) VALUES(?,?,?,?,?,?,?)",(u["id"],"Withdrawal",a,ph,name,"Pending",datetime.now().isoformat()))
   flash("Withdrawal request submitted and is pending processing.");return redirect(url_for("history"))
 return render_template("withdraw.html",u=u)
@app.route("/checkin",methods=["GET","POST"])
@need
def checkin():
 today=date.today().isoformat();u=user()
 with con() as c:
  claimed=c.execute("SELECT 1 FROM checkins WHERE user_id=? AND day=?",(u["id"],today)).fetchone() is not None
  if request.method=="POST" and not claimed:
   now=datetime.now().isoformat();c.execute("INSERT INTO checkins VALUES(?,?)",(u["id"],today));c.execute("UPDATE users SET balance=balance+1000 WHERE id=?",(u["id"],));c.execute("INSERT INTO tx(user_id,kind,amount,note,status,created) VALUES(?,?,?,?,?,?)",(u["id"],"Bonus",1000,"Daily check-in reward","Completed",now));claimed=True;flash("UGX 1,000 check-in reward added.")
 return render_template("checkin.html",claimed=claimed)
@app.route("/history")
@need
def history():
 with con() as c:rows=c.execute("SELECT * FROM tx WHERE user_id=? ORDER BY id DESC",(user()["id"],)).fetchall();reqs=c.execute("SELECT * FROM requests WHERE user_id=? ORDER BY id DESC",(user()["id"],)).fetchall()
 return render_template("history.html",rows=rows,reqs=reqs)
@app.route("/announcements")
@need
def announcements():
 with con() as c: rows=c.execute("SELECT title,body,created FROM announcements ORDER BY id DESC").fetchall()
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
 harvest=sum(int(r["daily"])*60 for r in rows)
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
if __name__=="__main__":app.run(debug=True)
