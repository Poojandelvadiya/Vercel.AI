from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import google.generativeai as genai
import os
import sqlite3
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Use a fixed key for development
app.debug = True  # Enable debug mode for better error messages

# Configure Gemini AI
genai.configure(api_key="AIzaSyDlNE1t-0s005OZ2vc7jLN0Fl8iMJXxdO4")

# File upload config
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"txt", "pdf", "docx", "csv", "json", "py", "java", "html", "css", "js"}

# Database configuration
DATABASE = 'user.db'

# Initialize database
def init_db():
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )
            ''')
            conn.commit()
            print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {str(e)}")

init_db()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Routes
@app.route("/")
def landing():
    if 'username' in session:
        return redirect(url_for('chatbot'))
    return render_template("landing.html")

@app.route("/chatbot")
def chatbot():
    print("Session:", session)  # Debug print
    if 'username' not in session:
        print("No username in session")  # Debug print
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    print("Rendering chatbot template")  # Debug print
    return render_template("index.html")  # Make sure this matches your template name

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Add print statements for debugging
        print("Form Data:", request.form)
        
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not username or not email or not password:
            flash('All fields are required!', 'error')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        
        try:
            with sqlite3.connect(DATABASE) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                    (username, email, hashed_password)
                )
                conn.commit()
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists!', 'error')
            return redirect(url_for('register'))
        except Exception as e:
            print("Error:", str(e))  # Add this for debugging
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            with sqlite3.connect(DATABASE) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
                user = cursor.fetchone()
                
                if user and check_password_hash(user[3], password):
                    session['username'] = username
                    session['user_id'] = user[0]
                    flash('Login successful!', 'success')
                    return redirect(url_for('chatbot'))
                else:
                    flash('Invalid username or password!', 'error')
                    return redirect(url_for('login'))
        except Exception as e:
            print("Login error:", str(e))
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(url_for('login'))
    
    return render_template('signin.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

@app.route("/upload", methods=["POST"])
def upload_file():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 403

    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        with open(filepath, "r") as f:
            content = f.read()
        analysis = analyze_file(content)
        return jsonify({"message": analysis, "filename": filename})
    return jsonify({"error": "Invalid file"}), 400

def analyze_file(content):
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(f"Analyze this file:\n{content}")
        return response.text if response and hasattr(response, "text") else "Analysis failed."
    except Exception as e:
        return f"Analysis error: {str(e)}"

@app.route("/ai", methods=["POST"])
def use_ai():
    try:
        if 'username' not in session:
            return jsonify({"error": "Unauthorized"}), 403

        data = request.json
        prompt = data.get("prompt", "").strip()

        if not prompt:
            return jsonify({"error": "Please enter a valid prompt."}), 400

        model = genai.GenerativeModel(
            "gemini-1.5-pro",
            system_instruction=(
                "You are a helpful AI assistant. Respond naturally to conversations. "
                "For greetings, respond warmly and ask how you can help. "
                "Always maintain proper grammar and formatting. "
                "Use the same language as the user's question."
            )
        )

        response = model.generate_content(prompt)

        if not response or not hasattr(response, "text"):
            return jsonify({"response": "Hello! How can I assist you today?"})

        reply = response.text.replace("\n", "<br>")
        return jsonify({"response": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/demo-chat')
def demo_chat():
    return render_template('index.html', demo=True)

@app.route('/chat', methods=['POST'])
def chat():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    message = data.get('message')
    
    # Here you would integrate with your AI model
    response = "This is a sample response. Replace with actual AI response."
    
    return jsonify({'response': response})

# Error handling
@app.errorhandler(404)
def page_not_found(e):
    print(f"404 error: {request.url}")  # Debug print
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/404.html'), 500

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"Unhandled exception: {str(e)}")  # Debug print
    return render_template('errors/404.html'), 500

if __name__ == "__main__":
    app.run(debug=True)