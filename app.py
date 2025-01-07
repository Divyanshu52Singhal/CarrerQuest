from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv(dotenv_path="process.env")
app = Flask(__name__)
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
app.config["SECRET_KEY"] = "password"

mongo = PyMongo(app)
bcrypt = Bcrypt(app)

# Home route
@app.route("/")
def landing():
    return render_template("landing.html")

# Admin Login
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

# Student Login
@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = mongo.db.students.find_one({"email": email})
        if user and bcrypt.check_password_hash(user["password"], password):
            session["user"] = email
            return redirect(url_for("student_dashboard"))
        return render_template("student_login.html", error="Invalid Student credentials")
    return render_template("student_login.html")

# Admin Dashboard
@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    roadmaps = list(mongo.db.roadmaps.find())
    students = list(mongo.db.students.find())
    return render_template("admin_dashboard.html", roadmaps=roadmaps, students=students)

# Add Roadmap (Admin)
@app.route("/admin/add_roadmap", methods=["GET", "POST"])
def admin_add_roadmap():
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        roadmap = {
            "roadmap_id": os.urandom(8).hex(),
            "title": request.form["title"],
            "description": request.form["description"],
            "total_no_of_modules": int(request.form["total_no_of_modules"]),
            "course_ids": request.form["course_ids"].split(","),
            "subscribed_user_ids": [],
            "completion_percentage": 0
        }
        mongo.db.roadmaps.insert_one(roadmap)
        return redirect(url_for("admin_dashboard"))
    return render_template("add_roadmap.html")

# Add Course (Admin)
@app.route("/admin/add_course", methods=["GET", "POST"])
def admin_add_course():
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        roadmap_id = request.form["roadmap_id"]
        course = {
            "course_id": os.urandom(8).hex(),
            "name": request.form["name"],
            "chapters": [{"title": chapter, "completed": False} for chapter in request.form["chapters"].split(",")],
            "completion_percentage": 0
        }
        mongo.db.courses.insert_one(course)
        # Assign course to roadmap
        mongo.db.roadmaps.update_one(
            {"roadmap_id": roadmap_id},
            {"$addToSet": {"course_ids": course["course_id"]}}
        )
        return redirect(url_for("admin_dashboard"))
    roadmaps = list(mongo.db.roadmaps.find())  # Fetch roadmaps for selection
    return render_template("add_course.html", roadmaps=roadmaps)
# Student Dashboard
@app.route("/student/dashboard")
def student_dashboard():
    if "user" not in session:
        return redirect(url_for("student_login"))

    user_email = session["user"]
    subscribed_roadmaps = list(
        mongo.db.roadmaps.find({"subscribed_user_ids": user_email})
    )
    unsubscribed_roadmaps = list(
        mongo.db.roadmaps.find({"subscribed_user_ids": {"$ne": user_email}})
    )
    return render_template(
        "student_dashboard.html",
        user=session["user"],
        subscribed_roadmaps=subscribed_roadmaps,
        unsubscribed_roadmaps=unsubscribed_roadmaps,
    )

# Subscribe to Roadmap (Student)
@app.route("/student/subscribe/<roadmap_id>", methods=["GET", "POST"])
def subscribe_roadmap(roadmap_id):
    if "user" not in session:
        return redirect(url_for("student_login"))
    if request.method == "POST":
        mongo.db.roadmaps.update_one(
            {"roadmap_id": roadmap_id},
            {"$addToSet": {"subscribed_user_ids": session["user"]}}
        )
        return redirect(url_for("student_dashboard"))
    roadmap = mongo.db.roadmaps.find_one({"roadmap_id": roadmap_id})
    return render_template("subscribe_roadmap.html", roadmap=roadmap)

@app.route("/student/roadmap/<roadmap_id>")
def view_roadmap(roadmap_id):
    if "user" not in session:
        return redirect(url_for("student_login"))
    
    roadmap = mongo.db.roadmaps.find_one({"roadmap_id": roadmap_id})
    if not roadmap:
        return redirect(url_for("student_dashboard"))
    
    # Fetch all courses in the roadmap
    courses = list(
        mongo.db.courses.find({"course_id": {"$in": roadmap.get("course_ids", [])}})
    )
    
    message = request.args.get("message")  # Retrieve optional message

    return render_template("view_roadmap.html", roadmap=roadmap, courses=courses, message=message)

@app.route("/student/update_chapter_status", methods=["POST"])
def update_chapter_status():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    course_id = request.form["course_id"]
    chapter_title = request.form["chapter_title"]
    completed = request.form["completed"] == "true"
    roadmap_id = request.form["roadmap_id"]

    # Find the course and update the specific chapter's status
    course = mongo.db.courses.find_one({"course_id": course_id})
    if not course:
        return jsonify({"error": "Course not found"}), 404

    for chapter in course["chapters"]:
        if chapter["title"] == chapter_title:
            chapter["completed"] = completed

    # Recalculate course completion percentage
    completion_percentage = (
        sum(1 for c in course["chapters"] if c["completed"]) / len(course["chapters"])
    ) * 100

    # Update in the database
    result = mongo.db.courses.update_one(
        {"course_id": course_id},
        {"$set": {"chapters": course["chapters"], "completion_percentage": completion_percentage}}
    )
    # print(f"Update result: {result.modified_count} document(s) updated.")

    status_message = f"Chapter '{chapter_title}' marked as {'Complete' if completed else 'Incomplete'}."
    return redirect(url_for("view_roadmap", roadmap_id=roadmap_id, message=status_message))

# Mark Chapter Completion (Student)
@app.route("/student/mark_chapter", methods=["POST"])
def mark_chapter():
    if "user" not in session:
        return redirect(url_for("student_login"))
    course_id = request.form["course_id"]
    chapter_title = request.form["chapter_title"]
    course = mongo.db.courses.find_one({"course_id": course_id})
    for chapter in course["chapters"]:
        if chapter["title"] == chapter_title:
            chapter["completed"] = True
    completion_percentage = (sum(1 for c in course["chapters"] if c["completed"]) / len(course["chapters"])) * 100
    mongo.db.courses.update_one(
        {"course_id": course_id},
        {"$set": {"chapters": course["chapters"], "completion_percentage": completion_percentage}}
    )
    return jsonify({"success": True})

@app.route("/student/signup", methods=["GET", "POST"])
def student_signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
        
        # Check if the student already exists
        if mongo.db.students.find_one({"email": email}):
            return render_template("student_signup.html", error="Email already registered")

        # Insert new student into the database
        student = {
            "email": email,
            "password": hashed_password
        }
        mongo.db.students.insert_one(student)
        return redirect(url_for("student_login"))
    
    return render_template("student_signup.html")
# Logout
@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("admin", None)
    return redirect(url_for("landing"))

if __name__ == "__main__":
    app.run(debug=True)
