from flask import Flask, render_template, request, redirect, url_for, session, jsonify,send_file
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from bson import ObjectId
import json
import os
from resume_generator import ResumeGenerator
from io import BytesIO

# Load environment variables
load_dotenv(dotenv_path=".env")
app = Flask(__name__)
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
app.config["SECRET_KEY"] = "password"
SESSION_TIMEOUT = timedelta(minutes=10)
mongo = PyMongo(app)
bcrypt = Bcrypt(app)


def check_session_timeout(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'last_activity' in session:
            last_activity = datetime.fromisoformat(session['last_activity'])
            if datetime.now() - last_activity > SESSION_TIMEOUT:
                # Clear session if timeout exceeded
                session.clear()
                return redirect(url_for('landing'))
        
        # Update last activity time
        session['last_activity'] = datetime.now().isoformat()
        return f(*args, **kwargs)
    return decorated_function

def convert_objectid_to_str(data):
    if isinstance(data, list):
        return [convert_objectid_to_str(item) for item in data]
    elif isinstance(data, dict):
        return {key: convert_objectid_to_str(value) for key, value in data.items()}
    elif isinstance(data, ObjectId):
        return str(data)
    else:
        return data
# Home route
@app.route("/")
def landing():
    if "user" in session or "admin" in session:
        return redirect(url_for("student_dashboard") if "user" in session else "admin_dashboard")
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
            session['last_activity'] = datetime.now().isoformat()
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
            session['last_activity'] = datetime.now().isoformat()
            return redirect(url_for("student_dashboard"))
        return render_template("student_login.html", error="Invalid Student credentials")
    return render_template("student_login.html")

# Admin Dashboard
@app.route("/admin/dashboard")
@check_session_timeout
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    roadmaps = list(mongo.db.roadmaps.find())
    for roadmap in roadmaps:
        course_ids = roadmap.get("course_ids", [])
        roadmap["courses"] = list(mongo.db.courses.find({"course_id": {"$in": course_ids}}))
    students = list(mongo.db.students.find())
    for student in students:
        student_progress = student.get("progress", {})
        competition_data = defaultdict(int)
        for roadmap_id, roadmap_courses in student_progress.items():
            total_chapters = 0
            completed_chapters = 0
            for course_id, course_progress in roadmap_courses.items():
                course = mongo.db.courses.find_one({"course_id": course_id})
                if course:
                    total_chapters += len(course.get("chapters", []))
                    completed_chapters += sum(1 for chapter, completed in course_progress.items() if completed)
            competition_data[roadmap_id] = (completed_chapters / total_chapters) * 100 if total_chapters > 0 else 0

        student["completion_rate"] = competition_data

    students_data = [
        {
            "email": student["email"],
            "subscribed_roadmaps": student.get("subscribed_roadmaps", []),
            "completion_rate": student["completion_rate"],
            "name": student.get("name", ""),
            "cgpa": student.get("cgpa", 0),
        }
        for student in students
    ]
    roadmaps = convert_objectid_to_str(roadmaps)
    students_data = convert_objectid_to_str(students_data)
    return render_template(
        "admin_dashboard.html",
        roadmaps=roadmaps,
        students_data=students_data,
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
            "subscribed_user_ids": [],
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
        chapters = []
        for title, link in zip(request.form.getlist("chapters[]"), request.form.getlist("links[]")):
            chapters.append({"title": title, "link": link, "completed": False})
        course = {
            "course_id": os.urandom(8).hex(),
            "name": request.form["name"],
            "chapters": chapters,
            "completion_percentage": 0
        }
        mongo.db.courses.insert_one(course)
        mongo.db.roadmaps.update_one(
            {"roadmap_id": roadmap_id},
            {"$addToSet": {"course_ids": course["course_id"]}}
        )
        return redirect(url_for("admin_dashboard"))
    roadmaps = list(mongo.db.roadmaps.find())
    return render_template("add_course.html", roadmaps=roadmaps)
# Delete Roadmap (Admin)
@app.route("/admin/delete_roadmap/<roadmap_id>", methods=["POST"])
def admin_delete_roadmap(roadmap_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    
    # Get the roadmap to find associated courses
    roadmap = mongo.db.roadmaps.find_one({"roadmap_id": roadmap_id})
    if not roadmap:
        return redirect(url_for("admin_dashboard"))
    
    # Get course_ids associated with this roadmap
    course_ids = roadmap.get("course_ids", [])
    
    # Delete all associated courses
    if course_ids:
        mongo.db.courses.delete_many({"course_id": {"$in": course_ids}})
    
    # Delete all associated quizzes
    mongo.db.quizzes.delete_many({"roadmap_id": roadmap_id})
    
    # Remove roadmap from student subscriptions and progress
    students = list(mongo.db.students.find({"subscribed_roadmaps": roadmap_id}))
    for student in students:
        # Remove from subscribed_roadmaps
        mongo.db.students.update_one(
            {"_id": student["_id"]},
            {"$pull": {"subscribed_roadmaps": roadmap_id}}
        )
        
        # Remove from progress if exists
        if "progress" in student and roadmap_id in student["progress"]:
            mongo.db.students.update_one(
                {"_id": student["_id"]},
                {"$unset": {f"progress.{roadmap_id}": ""}}
            )
        
        # Remove from quiz_results if exists
        if "quiz_results" in student and roadmap_id in student["quiz_results"]:
            mongo.db.students.update_one(
                {"_id": student["_id"]},
                {"$unset": {f"quiz_results.{roadmap_id}": ""}}
            )
    
    # Delete the roadmap
    mongo.db.roadmaps.delete_one({"roadmap_id": roadmap_id})
    
    return redirect(url_for("admin_dashboard"))

# Delete Course (Admin)
@app.route("/admin/delete_course/<roadmap_id>/<course_id>", methods=["POST"])
def admin_delete_course(roadmap_id, course_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    
    # Remove course from roadmap
    mongo.db.roadmaps.update_one(
        {"roadmap_id": roadmap_id},
        {"$pull": {"course_ids": course_id}}
    )
    
    # Delete all quizzes associated with this course
    mongo.db.quizzes.delete_many({"roadmap_id": roadmap_id, "course_id": course_id})
    
    # Remove course from student progress and quiz results
    students = list(mongo.db.students.find({f"progress.{roadmap_id}.{course_id}": {"$exists": True}}))
    for student in students:
        # Remove from progress if exists
        if "progress" in student and roadmap_id in student["progress"] and course_id in student["progress"][roadmap_id]:
            mongo.db.students.update_one(
                {"_id": student["_id"]},
                {"$unset": {f"progress.{roadmap_id}.{course_id}": ""}}
            )
        
        # Remove from quiz_results if exists
        if "quiz_results" in student and roadmap_id in student["quiz_results"] and course_id in student["quiz_results"][roadmap_id]:
            mongo.db.students.update_one(
                {"_id": student["_id"]},
                {"$unset": {f"quiz_results.{roadmap_id}.{course_id}": ""}}
            )
    
    # Delete the course
    mongo.db.courses.delete_one({"course_id": course_id})
    
    return redirect(url_for("admin_dashboard"))

# Edit Roadmap (Admin)
@app.route("/admin/edit_roadmap/<roadmap_id>", methods=["GET", "POST"])
def admin_edit_roadmap(roadmap_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    
    roadmap = mongo.db.roadmaps.find_one({"roadmap_id": roadmap_id})
    if not roadmap:
        return redirect(url_for("admin_dashboard"))
    
    if request.method == "POST":
        # Update roadmap information
        updated_roadmap = {
            "title": request.form["title"],
            "description": request.form["description"]
        }
        
        mongo.db.roadmaps.update_one(
            {"roadmap_id": roadmap_id},
            {"$set": updated_roadmap}
        )
        
        return redirect(url_for("admin_dashboard"))
    
    return render_template("edit_roadmap.html", roadmap=roadmap)

# Edit Course (Admin)
@app.route("/admin/edit_course/<roadmap_id>/<course_id>", methods=["GET", "POST"])
def admin_edit_course(roadmap_id, course_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    
    course = mongo.db.courses.find_one({"course_id": course_id})
    if not course:
        return redirect(url_for("admin_dashboard"))
    
    if request.method == "POST":
        # Process the updated chapters
        chapter_titles = request.form.getlist("chapters[]")
        reference_titles_by_chapter = {}
        reference_links_by_chapter = {}
        
        # Process reference data
        for key, value in request.form.items():
            if key.startswith('reference_titles['):
                chapter_idx = int(key.split('[')[1].split(']')[0])
                if chapter_idx not in reference_titles_by_chapter:
                    reference_titles_by_chapter[chapter_idx] = []
                reference_titles_by_chapter[chapter_idx].append(value)
            elif key.startswith('reference_links['):
                chapter_idx = int(key.split('[')[1].split(']')[0])
                if chapter_idx not in reference_links_by_chapter:
                    reference_links_by_chapter[chapter_idx] = []
                reference_links_by_chapter[chapter_idx].append(value)
        
        chapters = []
        for idx, title in enumerate(chapter_titles):
            # Find if this chapter existed before to preserve completion status
            existing_chapter = next((ch for ch in course.get("chapters", []) if ch["title"] == title), None)
            
            # Collect references for this chapter
            references = []
            if idx in reference_titles_by_chapter and idx in reference_links_by_chapter:
                for ref_title, ref_link in zip(reference_titles_by_chapter[idx], reference_links_by_chapter[idx]):
                    references.append({
                        "title": ref_title,
                        "link": ref_link
                    })
            
            new_chapter = {
                "title": title,
                "references": references,
                "completed": existing_chapter.get("completed", False) if existing_chapter else False
            }
            
            # For backward compatibility, also include the first link as 'link' field
            if references:
                new_chapter["link"] = references[0]["link"]
            
            chapters.append(new_chapter)
        
        # Update course information
        updated_course = {
            "name": request.form["name"],
            "chapters": chapters
        }
        
        mongo.db.courses.update_one(
            {"course_id": course_id},
            {"$set": updated_course}
        )
        
        # Handle student progress updates for changed/removed chapters
        students = list(mongo.db.students.find({f"progress.{roadmap_id}.{course_id}": {"$exists": True}}))
        for student in students:
            # Get current progress for this course
            course_progress = student.get("progress", {}).get(roadmap_id, {}).get(course_id, {})
            
            # Remove progress entries for chapters that no longer exist
            existing_chapter_titles = [ch["title"] for ch in chapters]
            for chapter_title in list(course_progress.keys()):
                if chapter_title not in existing_chapter_titles:
                    course_progress.pop(chapter_title, None)
            
            # Update the student's progress
            mongo.db.students.update_one(
                {"_id": student["_id"]},
                {"$set": {f"progress.{roadmap_id}.{course_id}": course_progress}}
            )
        
        return redirect(url_for("admin_dashboard"))
    
    roadmap = mongo.db.roadmaps.find_one({"roadmap_id": roadmap_id})
    return render_template("edit_course.html", course=course, roadmap=roadmap)
# Quiz Routes
@app.route("/student/quiz/<roadmap_id>/<course_id>/<chapter_title>", methods=["GET", "POST"])
def take_chapter_quiz(roadmap_id, course_id, chapter_title):
    if "user" not in session:
        return redirect(url_for("student_login"))
    
    user_email = session["user"]
    # print(session)
    student = mongo.db.students.find_one({"email": user_email})
    
    # Check if student is subscribed to this roadmap
    if roadmap_id not in student.get("subscribed_roadmaps", []):
        return redirect(url_for("student_dashboard", message="You are not subscribed to this roadmap"))
    
    # Fetch quiz for this chapter
    quiz = mongo.db.quizzes.find_one({
        "roadmap_id": roadmap_id,
        "course_id": course_id,
        "chapter_title": chapter_title
    })
    
    # If quiz doesn't exist yet
    if not quiz:
        return render_template("no_quiz.html", 
                              roadmap_id=roadmap_id, 
                              course_id=course_id, 
                              chapter_title=chapter_title)
    
    if request.method == "POST":
        # Calculate score
        score = 0
        total_questions = len(quiz.get("questions", []))
        timer_expired = request.form.get("timer_expired") == "true"
        time_taken = int(request.form.get("time_taken", 0))
        
        for i, question in enumerate(quiz.get("questions", [])):
            submitted_answer = request.form.get(f"answer_{i}")
            if submitted_answer == question.get("correct_answer"):
                score += 1
        
        percentage_score = (score / total_questions) * 100 if total_questions > 0 else 0
        
        # Parse time limit from the quiz (format: MM:SS)
        time_limit = quiz.get("time_limit", "1:00")
        minutes, seconds = map(int, time_limit.split(":"))
        total_seconds = minutes * 60 + seconds
        
        # Update student's quiz results
        quiz_result = {
            "quiz_id": quiz.get("quiz_id"),
            "score": score,
            "total_questions": total_questions,
            "percentage": percentage_score,
            "passed": percentage_score >= 70,  # Assuming 70% is passing grade
            "timer_expired": timer_expired,  # Record if quiz was auto-submitted due to time expiration
            "time_taken": time_taken,  # Record time taken in seconds
            "time_limit_seconds": total_seconds  # Record time limit in seconds
        }
        
        # Save quiz result to student record
        mongo.db.students.update_one(
            {"email": user_email},
            {"$set": {f"quiz_results.{roadmap_id}.{course_id}.{chapter_title}": quiz_result}}
        )
        
        # If passed, mark chapter as completed
        if percentage_score >= 70:
            mongo.db.students.update_one(
                {"email": user_email},
                {"$set": {f"progress.{roadmap_id}.{course_id}.{chapter_title}": True}}
            )
            
        return render_template("quiz_results.html", 
                              current_user=user_email,
                              quiz=quiz, 
                              score=score, 
                              total=total_questions, 
                              percentage=percentage_score,
                              passed=percentage_score >= 70,
                              timer_expired=timer_expired,
                              time_taken=time_taken,
                              time_limit_seconds=total_seconds,
                              roadmap_id=roadmap_id)
    
    return render_template("take_quiz.html", current_user=user_email,quiz=quiz, roadmap_id=roadmap_id, course_id=course_id, chapter_title=chapter_title)

# Create Quiz (Admin)
@app.route("/admin/create_quiz/<roadmap_id>/<course_id>/<chapter_title>", methods=["GET", "POST"])
def create_quiz(roadmap_id, course_id, chapter_title):
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    
    if request.method == "POST":
        question_count = int(request.form.get("question_count", 0))
        questions = []
        time_limit = request.form.get("time_limit", "10:00")  # Default: 10 minutes
        
        for i in range(question_count):
            question_text = request.form.get(f"question_{i}")
            correct_answer = request.form.get(f"correct_answer_{i}")
            options = []
            
            for j in range(4):  # Assuming 4 options per question
                option = request.form.get(f"option_{i}_{j}")
                if option:
                    options.append(option)
            
            questions.append({
                "question_text": question_text,
                "options": options,
                "correct_answer": correct_answer
            })
        
        quiz = {
            "quiz_id": os.urandom(8).hex(),
            "roadmap_id": roadmap_id,
            "course_id": course_id,
            "chapter_title": chapter_title,
            "questions": questions,
            "passing_score": 70,  # Default passing score (70%)
            "time_limit": time_limit  # Store the time limit
        }
        
        # Check if quiz already exists and update it, or create new
        existing_quiz = mongo.db.quizzes.find_one({
            "roadmap_id": roadmap_id,
            "course_id": course_id,
            "chapter_title": chapter_title
        })
        
        if existing_quiz:
            mongo.db.quizzes.update_one(
                {"quiz_id": existing_quiz["quiz_id"]},
                {"$set": quiz}
            )
        else:
            mongo.db.quizzes.insert_one(quiz)
            
        return redirect(url_for("admin_dashboard", message="Quiz created successfully"))
    
    # Get course and chapter details for context
    course = mongo.db.courses.find_one({"course_id": course_id})
    chapter = None
    
    if course:
        for ch in course.get("chapters", []):
            if ch["title"] == chapter_title:
                chapter = ch
                break
    
    return render_template("create_quiz.html", 
                          roadmap_id=roadmap_id, 
                          course_id=course_id, 
                          chapter_title=chapter_title,
                          course=course,
                          chapter=chapter)

# Quiz Results Dashboard for Students
@app.route("/student/quiz_results")
def student_quiz_results():
    if "user" not in session:
        return redirect(url_for("student_login"))
    
    user_email = session["user"]
    student = mongo.db.students.find_one({"email": user_email})
    
    quiz_results = student.get("quiz_results", {})
    
    # Get roadmap and course details for display
    roadmap_details = {}
    for roadmap_id in quiz_results.keys():
        roadmap = mongo.db.roadmaps.find_one({"roadmap_id": roadmap_id})
        if roadmap:
            roadmap_details[roadmap_id] = {
                "title": roadmap.get("title"),
                "courses": {}
            }
            
            for course_id in quiz_results[roadmap_id].keys():
                course = mongo.db.courses.find_one({"course_id": course_id})
                if course:
                    roadmap_details[roadmap_id]["courses"][course_id] = course.get("name")
    
    return render_template("student_quiz_results.html", 
                          quiz_results=quiz_results,
                          roadmap_details=roadmap_details)
# Student Dashboard
@app.route("/student/dashboard")
@check_session_timeout
def student_dashboard():
    if "user" not in session:
        return redirect(url_for("student_login"))
    user_email = session["user"]
    subscribed_roadmaps = list(mongo.db.roadmaps.find({"subscribed_user_ids": user_email}))
    unsubscribed_roadmaps = list(mongo.db.roadmaps.find({"subscribed_user_ids": {"$ne": user_email}}))
    return render_template("student_dashboard.html",
        user=session["user"],
        subscribed_roadmaps=subscribed_roadmaps,
        unsubscribed_roadmaps=unsubscribed_roadmaps)

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
        mongo.db.students.update_one({"email": session["user"]},
            {"$addToSet": {"subscribed_roadmaps": roadmap_id}})

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

    # Send response back
    status_message = f"Chapter '{chapter_title}' marked as {'Complete' if completed else 'Incomplete'}."
    return redirect(url_for("view_roadmap", roadmap_id=roadmap_id, message=status_message))
@app.route("/student/profile", methods=["GET"])
def view_profile():
    if "user" not in session:
        return redirect(url_for("student_login"))
    
    user_email = session["user"]
    student = mongo.db.students.find_one({"email": user_email})
    
    if not student:
        return redirect(url_for("student_login"))

    # Get subscribed roadmaps details
    roadmaps_data = []
    subscribed_roadmaps = student.get("subscribed_roadmaps", [])
    student_progress = student.get("progress", {})
    student_quiz_results = student.get("quiz_results", {})
    
    for roadmap_id in subscribed_roadmaps:
        roadmap = mongo.db.roadmaps.find_one({"roadmap_id": roadmap_id})
        if roadmap:
            roadmap_progress = student_progress.get(roadmap_id, {})
            roadmap_quiz_results = student_quiz_results.get(roadmap_id, {})
            
            # Get courses for this roadmap
            courses_data = []
            for course_id in roadmap.get("course_ids", []):
                course = mongo.db.courses.find_one({"course_id": course_id})
                if course:
                    # Get chapter completion status
                    course_progress = roadmap_progress.get(course_id, {})
                    course_quiz_results = roadmap_quiz_results.get(course_id, {})
                    
                    # Process chapters with completion status
                    processed_chapters = []
                    total_completed = 0
                    for chapter in course.get("chapters", []):
                        chapter_data = {
                            "title": chapter["title"],
                            "completed": course_progress.get(chapter["title"], False),
                            "quiz_result": course_quiz_results.get(chapter["title"], None)
                        }
                        if chapter_data["completed"]:
                            total_completed += 1
                        processed_chapters.append(chapter_data)
                    
                    # Calculate course progress percentage
                    total_chapters = len(course.get("chapters", []))
                    progress_percentage = (total_completed / total_chapters * 100) if total_chapters > 0 else 0
                    
                    # Add processed course data
                    courses_data.append({
                        "course_id": course_id,
                        "name": course.get("name"),
                        "chapters": processed_chapters,
                        "progress_percentage": progress_percentage
                    })
            
            roadmaps_data.append({
                "roadmap": {
                    "roadmap_id": roadmap_id,
                    "title": roadmap.get("title")
                },
                "courses": courses_data
            })

    # Prepare profile data
    profile_data = {
        "name": student.get("name", ""),
        "email": student.get("email", ""),
        "registration_date": student.get("registration_date", ""),
        "roadmaps": roadmaps_data
    }
        
    return render_template("student_profile.html", student=profile_data)
@app.route("/student/profile/<email>")
def admin_view_student_profile(email):
    if "admin" not in session:
        return jsonify({"error": "Unauthorized"}), 401    
        
    student = mongo.db.students.find_one({"email": email})
    if not student:
        return redirect(url_for("admin_dashboard"))
    roadmaps_data = []
    subscribed_roadmaps = student.get("subscribed_roadmaps", [])
    student_progress = student.get("progress", {})
    student_quiz_results = student.get("quiz_results", {})
    
    for roadmap_id in subscribed_roadmaps:
        roadmap = mongo.db.roadmaps.find_one({"roadmap_id": roadmap_id})
        if roadmap:
            roadmap_progress = student_progress.get(roadmap_id, {})
            roadmap_quiz_results = student_quiz_results.get(roadmap_id, {})
            
            # Get courses for this roadmap
            courses_data = []
            for course_id in roadmap.get("course_ids", []):
                course = mongo.db.courses.find_one({"course_id": course_id})
                if course:
                    # Get chapter completion status
                    course_progress = roadmap_progress.get(course_id, {})
                    course_quiz_results = roadmap_quiz_results.get(course_id, {})
                    
                    # Process chapters with completion status
                    processed_chapters = []
                    total_completed = 0
                    for chapter in course.get("chapters", []):
                        chapter_data = {
                            "title": chapter["title"],
                            "completed": course_progress.get(chapter["title"], False),
                            "quiz_result": course_quiz_results.get(chapter["title"], None)
                        }
                        if chapter_data["completed"]:
                            total_completed += 1
                        processed_chapters.append(chapter_data)
                    
                    # Calculate course progress percentage
                    total_chapters = len(course.get("chapters", []))
                    progress_percentage = (total_completed / total_chapters * 100) if total_chapters > 0 else 0
                    
                    # Add processed course data
                    courses_data.append({
                        "course_id": course_id,
                        "name": course.get("name"),
                        "chapters": processed_chapters,
                        "progress_percentage": progress_percentage
                    })
            
            roadmaps_data.append({
                "roadmap": {
                    "roadmap_id": roadmap_id,
                    "title": roadmap.get("title")
                },
                "courses": courses_data
            })

    # Prepare profile data
    profile_data = {
        "name": student.get("name", ""),
        "email": student.get("email", ""),
        "registration_date": student.get("registration_date", ""),
        "roadmaps": roadmaps_data
    }    
    # Use the same logic as student profile view
    # but with admin privileges
    return render_template("student_profile.html", 
                         student=profile_data, 
                         is_admin_view=True)

@app.route('/form')
def resume_form():
    """Display the resume form page with pre-filled student information."""
    if "user" not in session:
        return redirect(url_for("student_login"))
    
    user_email = session["user"]
    student = mongo.db.students.find_one({"email": user_email})
    
    if not student:
        return redirect(url_for("student_login"))
    
    # Get student's roadmaps and courses for education section
    education_data = []
    projects_data = []
    skills = {"Languages": [], "Frameworks": [], "Developer Tools": [], "Libraries": []}    
    form_data = {
        "personal_info": {
            "name": student.get("name", ""),
            "email": student.get("email", ""),
            "phone": student.get("phone", ""),
            "linkedin_url": student.get("linkedin_url", ""),
            "github_url": student.get("github_url", "")
        },
        "education": education_data,
        "projects": projects_data,
        "skills": skills,
        "cgpa": student.get("cgpa", "")
    }
    
    return render_template('resume_form.html', form_data=form_data)

@app.route('/generate', methods=['POST'])
def generate_resume():
    if not request.is_json:
        return {"error": "Content-Type must be application/json"}, 400
    
    data = request.get_json()
    
    # Generate LaTeX content
    latex_content = ResumeGenerator.from_json(data, "./resume_template.tex")
    
    # Create in-memory file
    mem_file = BytesIO(latex_content.encode('utf-8'))
    
    # Return the file
    return send_file(mem_file,
                    mimetype='application/x-tex',
                    as_attachment=True,
                    download_name='resume.tex')

@app.route('/preview', methods=['POST'])
def preview_resume():
    """Endpoint to generate resume preview"""
    if not request.is_json:
        return {"error": "Content-Type must be application/json"}, 400
    
    data = request.get_json()
    
    try:
        # Generate LaTeX content
        latex_content = ResumeGenerator.from_json(data, "./resume_template.tex")
        
        # Store the preview content in session for the preview page
        session['preview_content'] = latex_content
        
        return jsonify({
            "success": True,
            "redirect_url": url_for('show_preview')
        })
    except Exception as e:
        return jsonify({
            "error": f"Error generating preview: {str(e)}"
        }), 500

@app.route('/show_preview')
def show_preview():
    """Display the resume preview page"""
    if 'preview_content' not in session:
        return redirect(url_for('resume_form'))
        
    latex_content = session['preview_content']
    return render_template('preview_resume.html', latex_content=latex_content)

def calculate_overall_progress(student):
    """Calculate overall progress across all roadmaps"""
    total_chapters = 0
    completed_chapters = 0
    
    for roadmap_id in student.get("subscribed_roadmaps", []):
        progress = student.get("progress", {}).get(roadmap_id, {})
        for course_progress in progress.values():
            completed_chapters += sum(1 for completed in course_progress.values() if completed)
            total_chapters += len(course_progress)
    
    return (completed_chapters / total_chapters * 100) if total_chapters > 0 else 0
@app.route("/student/signup", methods=["GET", "POST"])
def student_signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        cgpa = request.form["cgpa"]
        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
        
        # Check if the student already exists
        if mongo.db.students.find_one({"email": email}):
            return render_template("student_signup.html", error="Email already registered")

        # Insert new student into the database
        student = {
            "name" : name,
            "email": email,
            "password": hashed_password,
            "cgpa": cgpa
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