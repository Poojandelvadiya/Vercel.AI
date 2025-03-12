import time
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import google.generativeai as genai
import asyncio
import os
import sqlite3
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Set a secret key for sessions
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Set Google Gemini API Key
genai.configure(api_key="YOUR_GEMINI_API_KEY")  # Replace with a valid API key

# Directory for storing uploaded files
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure the uploads folder exists
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Allowed file extensions
ALLOWED_EXTENSIONS = {"txt", "pdf", "docx", "csv", "json", "py", "java", "html", "css", "js"}

# SQLite Database Setup
DATABASE = "users.db"

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL)''')

        conn.execute('''CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id))''')

init_db()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index():
    if "username" in session:
        return render_template("index.html")
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username=?", (username,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user[2], password):
                session["username"] = username
                return redirect(url_for("index"))
            else:
                return "Invalid credentials. Please try again.", 400
    
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password)

        try:
            with sqlite3.connect(DATABASE) as conn:
                conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return "Username already exists. Please choose another one.", 400
    
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        if "username" not in session:
            return jsonify({"error": "Unauthorized access. Please login."}), 403

        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files["file"]

        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)

            # If file is text-based, process it
            if filename.endswith(("txt", "csv", "json", "py", "java", "html", "css", "js")):
                with open(filepath, "r", encoding="utf-8") as f:
                    file_content = f.read()
                response = analyze_file(file_content)
            else:
                response = "File uploaded successfully, but AI analysis is not supported for this format."

            return jsonify({"message": response, "filename": filename})

        return jsonify({"error": "Invalid file format"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def analyze_file(content):
    """Send file content to AI for processing."""
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(f"Analyze this file:\n{content}")
        return response.text if response and hasattr(response, "text") else "No response from AI."
    except Exception as e:
        return f"AI Error: {str(e)}"

@app.route("/ai", methods=["POST"])
def use_ai():
    try:
        if "username" not in session:
            return jsonify({"error": "Unauthorized access. Please login."}), 403

        data = request.json
        prompt = data.get("prompt", "").strip()
        filename = data.get("filename")

        if not prompt and not filename:
            return jsonify({"error": "Prompt or file is required"}), 400

        if filename:
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            if not os.path.exists(filepath):
                return jsonify({"error": f"File '{filename}' not found."}), 404

            with open(filepath, "r", encoding="utf-8") as f:
                file_content = f.read()
            prompt += f"\n\nFile content:\n{file_content}"

        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(prompt)

        reply = response.text if response and hasattr(response, "text") else "No response from AI."

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username=?", (session["username"],))
            user_id = cursor.fetchone()
            if user_id:
                cursor.execute("INSERT INTO history (user_id, content) VALUES (?, ?)", (user_id[0], prompt))
                conn.commit()

        return jsonify({"response": reply})

    except Exception as e:
        return jsonify({"error": f"AI Error: {str(e)}"}), 500

@app.route("/history", methods=["GET"])
def get_history():
    if "username" not in session:
        return jsonify({"error": "Unauthorized access. Please login."}), 403

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username=?", (session["username"],))
        user_id = cursor.fetchone()[0]
        cursor.execute("SELECT content, timestamp FROM history WHERE user_id=? ORDER BY timestamp DESC", (user_id,))
        history = cursor.fetchall()

    return jsonify({"history": [{"content": row[0], "timestamp": row[1]} for row in history]})

if __name__ == "__main__":
    app.run(debug=True)
