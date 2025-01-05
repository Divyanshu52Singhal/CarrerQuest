class Tracks:
    def __init__(self, db):
        self.db = db

    def add_track(self, roadmap, courses):
        self.db.tracks.insert_one({"roadmap": roadmap, "courses": courses})

    def get_data(self):
        return list(self.db.tracks.find())

class Student:
    def __init__(self, db):
        self.db = db

    def add_info(self, email, info):
        self.db.students.update_one({"email": email}, {"$set": {"info": info}})

class Admin:
    def __init__(self, db):
        self.db = db

    def get_students(self):
        return list(self.db.students.find())
