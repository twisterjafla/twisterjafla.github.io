import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
import datetime

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
#if not os.environ.get("API_KEY"):
    #raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    userID= db.execute("SELECT id FROM users WHERE username = ?",session["username"])[0]['id']
    list = db.execute("SELECT count, stockCode FROM stocks WHERE personID = ?", userID)
    TOTAL=0
    for item in list:
        item["value"] = (lookup(item["stockCode"])["price"]*item["count"])
        TOTAL+=item["value"]
        item["value"]=usd(item["value"])


    TOTAL += (int(db.execute("SELECT cash FROM users WHERE username = ?", session["username"])[0]["cash"]))
    return render_template("index.html", stocks = list, total = usd(TOTAL), cash = usd(db.execute("SELECT cash FROM users WHERE username = ?", session["username"])[0]["cash"]))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    global session
    if request.method=="POST":
        try:
            number=int(request.form.get("shares"))
        except:
            return apology("amount of stock requested is not an integer")

        STOCK=lookup(request.form.get("symbol"))
        print(STOCK)
        if number > 0 and STOCK :
            cash=db.execute("SELECT cash FROM users WHERE username = ? ", session["username"])
            print(cash)
            print(session["username"])
            print(STOCK['symbol'])
            if cash and STOCK["price"]*number < cash[0]["cash"]:

                userID= db.execute("SELECT id FROM users WHERE username = ?",session["username"])[0]['id']
                db.execute("UPDATE users SET cash = cash -  ? WHERE id = ?;", STOCK["price"]*number, userID )
                print(userID)
                try:
                    NewNumber= number+db.execute("SELECT count FROM stocks WHERE personID = ? AND stockCode = ?;", userID, STOCK["symbol"])[0]["count"]
                    print(NewNumber)
                    db.execute("UPDATE stocks SET count = ? WHERE personID = ? AND stockCode = ?;", NewNumber, userID, STOCK["symbol"])
                except:
                    db.execute("INSERT INTO stocks VALUES (?, ?, ?);", STOCK["symbol"], userID, number)

                addToHistory(STOCK["symbol"], number, "buy")
                return redirect("/")
            elif cash:
                return apology("not enough money")
            else:
                return apology("somthing went wrong")
        else:
            return apology("amount of stock requested is not an integer")
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    return render_template("history.html", history = db.execute("SELECT * FROM history WHERE id = (SELECT id FROM users WHERE username = ?);", session["username"]))


@app.route("/terms")

def terms():
    return render_template("terms.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    global session
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        print(rows)
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]
        print(session["username"])
        # Redirect user to home page

        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        STOCK = lookup(request.form.get("symbol"))
        if  not STOCK:
            return apology("invalid stock symbol")

        print("STOCK")
        STOCK['price']=usd(STOCK['price'])
        print(STOCK)
        return render_template("quoted.html", stock = STOCK)



    else:
        return render_template("quote.html")
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        confermation = request.form.get("confirmation")
        name = request.form.get("username")
        password = request.form.get("password")

        if confermation == password and password and name and not db.execute("SELECT * FROM users WHERE username = ?;", name) :
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", name, generate_password_hash(password, 'pbkdf2:sha256', 8))
            return redirect("/login")
        elif confermation == password:
            return apology("Questions were left unawnsered")
        else:
            return apology("passwords did not match ")
    else:
        return render_template("register.html")

    """Register user"""
    return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    global session
    userID= db.execute("SELECT id FROM users WHERE username = ?",session["username"])[0]['id']
    Stocklist=db.execute("SELECT stockCode FROM stocks WHERE personID = ?", userID)
    STOCKLIST=[]

    for item in Stocklist:
        STOCKLIST.append(item["stockCode"])

    if request.method == "POST":
        stock = request.form.get("symbol")
        try:
            numberToSell = int(request.form.get("shares"))
        except:
            return apology("amount of stock requested is not an integer")

        if stock in STOCKLIST and numberToSell > 0 and isinstance(numberToSell, float)==False:
            print(db.execute("SELECT count FROM stocks WHERE personID = ? and stockCode = ?", userID, stock))
            print(numberToSell)
            if numberToSell <= int(db.execute("SELECT count FROM stocks WHERE personID = ? and stockCode = ?", userID, stock)[0]["count"]):

                stockinfo = db.execute("SELECT count FROM stocks WHERE PERSONID = ? AND stockCode = ?;", userID, stock)
                db.execute("UPDATE stocks SET count = count - ? WHERE personID = ? AND stockCode = ?;", numberToSell, userID, stock)
                db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", numberToSell*lookup(stock)["price"], userID)
                addToHistory(stock, numberToSell, "sell")
            else:
                return apology("not enough stock to sell")
    else:
        print(STOCKLIST)
        return render_template("sell.html", stockList=STOCKLIST)

    return redirect("/")
@app.route("/addCash", methods=["POST"])
@login_required
def add():
    add = request.form.get("add")
    db.execute("UPDATE users SET cash = cash + ?;", add)
    addToHistory("", add, "add")
    return redirect("/")


def addToHistory(stock, count, type):
    time = datetime.datetime.now()
    userID= db.execute("SELECT id FROM users WHERE username = ?",session["username"])[0]['id']
    if type == "add":
        db.execute("INSERT INTO history VALUES(?, ?, ?, ?, ?, ?, ?, ?);", userID, "N/A", "N/A", (str(time.year) + "-" + str(time.month) + "-" +  str(time.day)), time.hour, time.minute, count, type)
    else:
        db.execute("INSERT INTO history VALUES(?, ?, ?, ?, ?, ?, ?, ?);", userID, stock, count,(str(time.year) + "-" + str(time.month) + "-" +  str(time.day)), time.hour, time.minute, lookup(stock)["price"]*count, type)
