from flask import Flask, render_template, request, redirect, url_for, session
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from dotenv import *
import os
load_dotenv()

app = Flask(__name__)
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
app.config["SECRET_KEY"] = "password"

mongo = PyMongo(app)
bcrypt = Bcrypt(app)

# Landing Page
@app.route("/")
def landing():
    return render_template("landing.html")


# Login
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        admin = mongo.db.admins.find_one({"email": email})
        if admin and bcrypt.check_password_hash(admin["password"], password):
            session["admin"] = email
            return redirect(url_for("admin_dashboard"))
        return render_template("admin_login.html", error="Invalid Admin credentials")
    return render_template("admin_login.html")

@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = mongo.db.students.find_one({"email": email})
        if user and bcrypt.check_password_hash(user["password"], password):
            session["user"] = email
            return redirect(url_for("features"))
        return render_template("student_login.html", error="Invalid Student credentials")
    return render_template("student_login.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    students = list(mongo.db.students.find())
    return render_template("admin_dashboard.html", admin=session["admin"], students=students)

# Signup
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = bcrypt.generate_password_hash(request.form["password"]).decode("utf-8")
        mongo.db.students.insert_one({"email": email, "password": password, "tracks": []})
        return redirect(url_for("student_login"))
    return render_template("signup.html")

# Features Page
@app.route("/features")
def features():
    if "user" in session:
        return render_template("features.html", user=session["user"])
    return redirect(url_for("student_login"))  # Redirect to student login if not logged in


# Logout
@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("admin", None)
    return redirect(url_for("landing"))


@app.route("/admin/add_track", methods=["GET", "POST"])
def admin_add_track():
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    
    if request.method == "POST":
        roadmap = request.form["roadmap"]
        courses = request.form["courses"].split(",")
        mongo.db.tracks.insert_one({"roadmap": roadmap, "courses": courses})
        return redirect(url_for("admin_dashboard"))
    
    return render_template("admin_add_track.html")

@app.route("/add_track", methods=["GET", "POST"])
def add_track():
    if "user" not in session:
        return redirect(url_for("student_login"))
    
    if request.method == "POST":
        roadmap = request.form["roadmap"]
        courses = request.form["courses"].split(",")
        
        # Update the logged-in student's document with the new track
        mongo.db.students.update_one(
            {"email": session["user"]},  # Match the logged-in student's email
            {"$push": {"tracks": {"roadmap": roadmap, "courses": courses}}}  # Append to tracks array
        )
        
        return redirect(url_for("view_tracks"))
    
    return render_template("add_track.html")

@app.route("/tracks", methods=["GET", "POST"])
def view_tracks():
    if "user" not in session:
        return redirect(url_for("student_login"))
    
    # Fetch all tracks defined by admin
    tracks = list(mongo.db.tracks.find())
    
    if request.method == "POST":
        selected_roadmap = request.form["roadmap"]
        selected_track = mongo.db.tracks.find_one({"roadmap": selected_roadmap})
        
        # Add the selected track to the logged-in student's document
        mongo.db.students.update_one(
            {"email": session["user"]},
            {"$push": {"tracks": selected_track}}
        )
        return redirect(url_for("view_tracks"))
    
    return render_template("view_tracks.html", tracks=tracks)
if __name__ == "__main__":
    app.run(debug=True)
    