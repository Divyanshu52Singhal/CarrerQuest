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
    # Fetch all roadmaps
    roadmaps = list(mongo.db.roadmaps.find())
    roadmap_titles = {roadmap["roadmap_id"]: roadmap["title"] for roadmap in roadmaps}

    # Fetch all courses for each roadmap
    for roadmap in roadmaps:
        course_ids = roadmap.get("course_ids", [])
        roadmap["courses"] = list(mongo.db.courses.find({"course_id": {"$in": course_ids}}))

    # Get the selected roadmap filter (if any)
    selected_roadmap_id = request.args.get("roadmap_id", "")

    # Fetch all students and calculate completion rates
    students = list(mongo.db.students.find())
    filtered_students = []
    for student in students:
        student_progress = student.get("progress", {})
        total_chapters = 0
        completed_chapters = 0

        for roadmap_id, roadmap_courses in student_progress.items():
            for course_id, course_progress in roadmap_courses.items():
                total_chapters += len(course_progress)
                completed_chapters += sum(1 for chapter_completed in course_progress.values() if chapter_completed)

        student["completion_rate"] = (
            (completed_chapters / total_chapters) * 100 if total_chapters > 0 else 0
        )

        # Apply roadmap filter (if any)
        if not selected_roadmap_id or selected_roadmap_id in student.get("subscribed_roadmaps", []):
            filtered_students.append(student)

    return render_template(
        "admin_dashboard.html",
        roadmaps=roadmaps,
        students=students,
        filtered_students=filtered_students,
        roadmap_titles=roadmap_titles,
    )
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
    roadmap = mongo.db.roadmaps.find_one({"roadmap_id": roadmap_id})
    if not roadmap:
        return redirect(url_for("student_dashboard", message="Roadmap not found"))
    if request.method == "POST":
        # Add roadmap to the user's subscribed list
        mongo.db.students.update_one(
            {"email": session["user"]},
            {"$addToSet": {"subscribed_roadmaps": roadmap_id}}
        )

        # Add user to the roadmap's subscriber list
        mongo.db.roadmaps.update_one(
            {"roadmap_id": roadmap_id},
            {"$addToSet": {"subscribed_user_ids": session["user"]}}
        )

        # Initialize progress for the student for this roadmap
        # Fetch the list of course IDs in this roadmap
        course_ids = roadmap.get("course_ids", [])
        progress_template = {
            course_id: {} for course_id in course_ids
        }

        mongo.db.students.update_one(
            {"email": session["user"]},
            {"$set": {f"progress.{roadmap_id}": progress_template}}
        )

        # Redirect to dashboard with a success message
        return redirect(url_for("student_dashboard", message="Successfully subscribed to the roadmap"))

    return render_template("subscribe_roadmap.html", roadmap=roadmap)
@app.route("/student/roadmap/<roadmap_id>")
def view_roadmap(roadmap_id):
    if "user" not in session:
        return redirect(url_for("student_login"))
    
    roadmap = mongo.db.roadmaps.find_one({"roadmap_id": roadmap_id})
    if not roadmap:
        return redirect(url_for("student_dashboard"))
    
    courses = list(
        mongo.db.courses.find({"course_id": {"$in": roadmap.get("course_ids", [])}})
    )
    # Fetch user progress for this roadmap
    user_email = session["user"]
    user = mongo.db.students.find_one({"email": user_email})
    if not user:
        return redirect(url_for("student_dashboard"))
    progress = user.get("progress", {}).get(roadmap_id, {})
    # Inject completion status into each course/chapter
    for course in courses:
        course_id = course["course_id"]
        for chapter in course["chapters"]:
            chapter["completed"] = progress.get(course_id, {}).get(chapter["title"], False)
    
    message = request.args.get("message")
    return render_template("view_roadmap.html", roadmap=roadmap, courses=courses, message=message)

@app.route("/student/update_chapter_status", methods=["POST"])
def update_chapter_status():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    roadmap_id = request.form["roadmap_id"]
    course_id = request.form["course_id"]
    chapter_title = request.form["chapter_title"]
    completed = request.form["completed"] == "true"

    user_email = session["user"]
    # Fetch the user document
    student = mongo.db.students.find_one({"email": user_email})
    if not student:
        return jsonify({"error": "User not found"}), 404

    # Initialize progress if not exists
    if "progress" not in student:
        student["progress"] = {}

    if roadmap_id not in student["progress"]:
        return jsonify({"error": f"No progress initialized for roadmap: {roadmap_id}"}), 400

    if course_id not in student["progress"][roadmap_id]:
        return jsonify({"error": f"No progress initialized for course: {course_id}"}), 400

    # Update the chapter status in the progress
    student["progress"][roadmap_id][course_id][chapter_title] = completed

    # Save the updated progress back to the database
    mongo.db.students.update_one(
        {"email": user_email},
        {"$set": {f"progress.{roadmap_id}.{course_id}": student["progress"][roadmap_id][course_id]}}
    )

    # Calculate completion percentage for this course
    course = mongo.db.courses.find_one({"course_id": course_id}, {"chapters": 1})
    if not course:
        return jsonify({"error": "Course not found"}), 404

    total_chapters = len(course["chapters"])
    completed_chapters = sum(
        1 for chapter in course["chapters"]
        if student["progress"][roadmap_id][course_id].get(chapter["title"], False)
    )
    completion_percentage = (completed_chapters / total_chapters) * 100

    # Send response back
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
