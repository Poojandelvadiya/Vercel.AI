from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import google.generativeai as genai
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import secrets
import mysql.connector
from datetime import datetime
import time

# PIL imports
from PIL import Image  # Basic image handling
from PIL import ImageDraw  # For drawing on images
from PIL import ImageFont  # For adding text to images
from PIL import ImageFilter  # For image filters
from PIL import ImageEnhance  # For image enhancement

import requests
from io import BytesIO
import base64

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = secrets.token_hex(16)

# Mail Settings
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'poojandelvadiya27@gmail.com'
app.config['MAIL_PASSWORD'] = 'hxgu iwah ppfm ofhj'
app.config['MAIL_DEFAULT_SENDER'] = 'poojandelvadiya27@gmail.com'

mail = Mail(app)

# MySQL Configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'chatbot_db'
}

def get_db_connection():
    try:
        # Try to connect to MySQL
        conn = mysql.connector.connect(**db_config)
        
        if not conn.is_connected():
            print("Failed to connect to MySQL")
            return None
            
        cursor = conn.cursor(dictionary=True)
        
        # Import the SQL file if database is empty
        try:
            cursor.execute("SHOW TABLES")
            if not cursor.fetchall():  # If no tables exist
                print("Database is empty. Importing from SQL file...")
                with open('chatbot_db.sql', 'r') as sql_file:
                    sql_script = sql_file.read()
                    # Split and execute each statement
                    for statement in sql_script.split(';'):
                        if statement.strip():
                            cursor.execute(statement)
                    conn.commit()
                    print("Database imported successfully!")
        except Exception as e:
            print(f"Error importing database: {e}")
        
        return conn
        
    except mysql.connector.Error as e:
        error_msg = f"MySQL Connection Error: {e}"
        if e.errno == 1045:  # Access denied error
            error_msg = "Access denied for MySQL user. Check username and password."
        elif e.errno == 2003:  # Can't connect to server
            error_msg = "Cannot connect to MySQL server. Make sure it's running."
        print(error_msg)
        return None
        
    except Exception as e:
        print(f"Unexpected error connecting to MySQL: {e}")
        return None

# Initialize database and tables
def init_db():
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            
            # Import SQL file if it exists
            try:
                with open('chatbot_db.sql', 'r') as sql_file:
                    sql_script = sql_file.read()
                    # Split and execute each statement
                    for statement in sql_script.split(';'):
                        if statement.strip():
                            cursor.execute(statement)
                    conn.commit()
                    print("Database initialized from SQL file successfully!")
            except FileNotFoundError:
                print("chatbot_db.sql file not found. Creating default tables...")
                # Create default tables if SQL file is not found
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        username VARCHAR(80) UNIQUE NOT NULL,
                        email VARCHAR(120) UNIQUE NOT NULL,
                        password VARCHAR(255) NOT NULL,
                        reset_token VARCHAR(100)
                    )
                """)
                conn.commit()
                print("Default tables created successfully!")
            
            # Verify table structure
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print("\nDatabase tables:")
            for table in tables:
                table_name = table[list(table.keys())[0]]
                print(f"\nTable: {table_name}")
                cursor.execute(f"DESCRIBE {table_name}")
                columns = cursor.fetchall()
                for column in columns:
                    print(f"Column: {column['Field']}, Type: {column['Type']}")
            
            cursor.close()
            conn.close()
        else:
            print("Failed to initialize database - could not connect!")
    except mysql.connector.Error as e:
        print(f"Database initialization error: {e}")
        if e.errno == 1049:  # Database doesn't exist
            try:
                # Try to create database
                conn = mysql.connector.connect(
                    host=db_config['host'],
                    user=db_config['user'],
                    password=db_config['password']
                )
                cursor = conn.cursor()
                cursor.execute("CREATE DATABASE IF NOT EXISTS chatbot_db")
                print("Created database chatbot_db")
                cursor.close()
                conn.close()
                # Try initialization again
                init_db()
            except Exception as e2:
                print(f"Failed to create database: {e2}")

# Configure Gemini AI
genai.configure(api_key="AIzaSyDlNE1t-0s005OZ2vc7jLN0Fl8iMJXxdO4")

# API Configurations
PIXABAY_API_KEY = "49391134-bda9c8fd536b88e3754600b4f"  # Your Pixabay API key
PIXABAY_API_URL = "https://pixabay.com/api/"

# File upload config
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"txt", "pdf", "docx", "csv", "json", "py", "java", "html", "css", "js"}

# Routes
@app.route('/')
def landing():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('landing.html')

@app.route('/index')
def index():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    return render_template('index.html', username=session.get('username'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        print(f"Registration attempt - Username: {username}, Email: {email}")
        
        if not username or not email or not password:
            flash('Please fill in all fields', 'error')
            return render_template('register.html')
        
        conn = None
        cursor = None
        try:
            # Get database connection
            conn = get_db_connection()
            if not conn:
                print("Failed to establish database connection")
                flash('Database connection error. Please try again later.', 'error')
                return render_template('register.html')
            
            cursor = conn.cursor(dictionary=True)
            
            # Verify database exists
            try:
                cursor.execute("USE chatbot_db")
            except mysql.connector.Error as e:
                print(f"Database selection error: {e}")
                flash('Database configuration error. Please contact support.', 'error')
                return render_template('register.html')
            
            # Verify users table exists
            cursor.execute("SHOW TABLES LIKE 'users'")
            if not cursor.fetchone():
                print("Users table does not exist, creating it now...")
                try:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            username VARCHAR(80) UNIQUE NOT NULL,
                            email VARCHAR(120) UNIQUE NOT NULL,
                            password VARCHAR(255) NOT NULL,
                            reset_token VARCHAR(100)
                        )
                    """)
                    conn.commit()
                    print("Users table created successfully")
                except mysql.connector.Error as e:
                    print(f"Table creation error: {e}")
                    flash('Error setting up database. Please contact support.', 'error')
                    return render_template('register.html')
            
            # Check if username exists
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                flash('Username already exists', 'error')
                return render_template('register.html')
            
            # Check if email exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash('Email already registered', 'error')
                return render_template('register.html')
            
            try:
                # Hash the password
                hashed_password = generate_password_hash(password)
                
                # Insert new user
                cursor.execute("""
                    INSERT INTO users (username, email, password) 
                    VALUES (%s, %s, %s)
                """, (username, email, hashed_password))
                
                conn.commit()
                print(f"User registered successfully: {username}")
                
                flash('Registration successful! Please sign in.', 'success')
                return redirect(url_for('signin'))
                
            except mysql.connector.Error as e:
                print(f"Error inserting new user: {e}")
                if e.errno == 1062:  # Duplicate entry error
                    flash('Username or email already exists', 'error')
                else:
                    flash('Error creating account. Please try again.', 'error')
                return render_template('register.html')
                
        except mysql.connector.Error as e:
            print(f"MySQL Error during registration: {e}")
            error_message = str(e)
            if e.errno == 2003:
                error_message = "Cannot connect to database server. Please check if MySQL is running."
            elif e.errno == 1045:
                error_message = "Database access denied. Please check credentials."
            elif e.errno == 1049:
                error_message = "Database does not exist."
            flash(f'Database error: {error_message}', 'error')
            return render_template('register.html')
            
        except Exception as e:
            print(f"Unexpected error during registration: {e}")
            flash('An unexpected error occurred during registration', 'error')
            return render_template('register.html')
            
        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()
                print("Database connection closed")
    
    return render_template('register.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please enter both username and password', 'error')
            return render_template('signin.html')
        
        try:
            conn = get_db_connection()
            if not conn:
                flash('Database connection error', 'error')
                return render_template('signin.html')
                
            cursor = conn.cursor(dictionary=True)
            
            # Debug: Print the username being searched
            print(f"Attempting login for username: {username}")
            
            # Get user details including password hash
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            
            # Debug: Print if user was found
            print(f"User found in database: {user is not None}")
            
            if user:
                # Debug: Print password verification attempt
                print(f"Verifying password for user: {user['username']}")
                try:
                    if check_password_hash(user['password'], password):
                        print("Password verified successfully")
                        session['user_id'] = user['id']
                        session['username'] = user['username']
                        return redirect(url_for('index'))
                    else:
                        print("Password verification failed")
                        flash('Invalid username or password', 'error')
                except Exception as e:
                    print(f"Password verification error: {str(e)}")
                    flash('Error verifying password', 'error')
            else:
                flash('Invalid username or password', 'error')
            
            return render_template('signin.html')
                
        except mysql.connector.Error as e:
            print(f"Database error during signin: {e}")
            flash('An error occurred during login. Please try again.', 'error')
            return render_template('signin.html')
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals() and conn:
                conn.close()
            
    return render_template('signin.html')

# Store reset tokens temporarily (in production, use a database)
reset_tokens = {}

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Please enter your email address', 'error')
            return render_template('forgot_password.html')
        
        try:
            # Connect to MySQL database
            conn = get_db_connection()
            if not conn:
                flash('Database connection error. Please try again later.', 'error')
                return render_template('forgot_password.html')
                
            cursor = conn.cursor(dictionary=True)
            
            # Debug: Print email being searched
            print(f"Searching for email: {email}")
            
            # Check if email exists
            cursor.execute("SELECT id, email, username FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            
            # Debug: Print user found or not
            print(f"User found: {user is not None}")
            
            if user:
                try:
                    # Generate reset token
                    token = secrets.token_urlsafe(32)
                    
                    # Store token in database
                    cursor.execute("UPDATE users SET reset_token = %s WHERE id = %s", 
                                 (token, user['id']))
                    conn.commit()
                    
                    # Create reset link
                    reset_link = url_for('reset_password', token=token, _external=True)
                    
                    try:
                        # Send email
                        msg = Message('Password Reset Request',
                                    sender=app.config['MAIL_DEFAULT_SENDER'],
                                    recipients=[email])
                        msg.body = f'''Hi {user['username']},

You have requested to reset your password. Please click on the following link to reset your password:

{reset_link}

If you did not make this request, please ignore this email and no changes will be made to your account.

Best regards,
Your AI Chatbot Team'''
                        
                        mail.send(msg)
                        
                        flash('Password reset instructions have been sent to your email.', 'success')
                        return redirect(url_for('signin'))
                    
                    except Exception as e:
                        print(f"Email sending error: {e}")
                        flash('Error sending email. Please check your email configuration.', 'error')
                        return render_template('forgot_password.html')
                
                except Exception as e:
                    print(f"Token generation/storage error: {e}")
                    flash('Error generating reset token. Please try again.', 'error')
                    return render_template('forgot_password.html')
            else:
                flash('No account found with that email address.', 'error')
                return render_template('forgot_password.html')
        
        except mysql.connector.Error as e:
            print(f"Database error: {e}")
            flash('Database error. Please try again later.', 'error')
            return render_template('forgot_password.html')
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals() and conn:
                conn.close()
    
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if token exists and is valid
        cursor.execute("SELECT id, email FROM users WHERE reset_token = %s", (token,))
        user = cursor.fetchone()
        
        if not user:
            flash('Invalid or expired reset link.', 'error')
            return redirect(url_for('signin'))
        
        if request.method == 'POST':
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            if not password or not confirm_password:
                flash('Please enter both password fields.', 'error')
                return render_template('reset_password.html')
            
            if password != confirm_password:
                flash('Passwords do not match.', 'error')
                return render_template('reset_password.html')
            
            # Hash the new password
            hashed_password = generate_password_hash(password)
            
            # Update password and remove token
            cursor.execute("UPDATE users SET password = %s, reset_token = NULL WHERE id = %s",
                         (hashed_password, user['id']))
            conn.commit()
            
            flash('Your password has been updated successfully.', 'success')
            return redirect(url_for('signin'))
        
        return render_template('reset_password.html')
        
    except mysql.connector.Error as e:
        flash('An error occurred. Please try again later.', 'error')
        print(f"Database error: {e}")
        return redirect(url_for('signin'))
    finally:
        cursor.close()
        conn.close()

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 403

        if "file" not in request.files:
            return jsonify({"error": "❌ No file uploaded"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "❌ No file selected"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": f"❌ File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

        try:
            # Create uploads directory if it doesn't exist
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            
            # Secure the filename and save the file
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)

            # Read and analyze the file content
            try:
                with open(filepath, "r", encoding='utf-8', errors='ignore') as f:
                    content = f.read().strip()  # Remove leading/trailing whitespace
                
                if not content:
                    return jsonify({"error": "❌ File is empty"}), 400
                
                # Analyze the file content
                try:
                    model = genai.GenerativeModel("gemini-1.5-pro")
                    prompt = f"""Please analyze this file content and provide a detailed summary. 
                    If you encounter any special characters or formatting issues, please handle them appropriately.
                    
                    File content:
                    {content}"""
                    
                    response = model.generate_content(prompt)
                    analysis = response.text if response and hasattr(response, "text") else "Analysis failed."
                    
                    return jsonify({
                        "response": analysis,
                        "filename": filename
                    })
                except Exception as e:
                    print(f"AI Analysis error: {str(e)}")
                    return jsonify({"error": f"❌ Error analyzing file content: {str(e)}"}), 500
                
            except Exception as e:
                print(f"File reading error: {str(e)}")
                return jsonify({"error": "❌ Error reading file content"}), 400
            finally:
                # Clean up: remove the uploaded file
                try:
                    os.remove(filepath)
                except:
                    pass
                    
        except Exception as e:
            print(f"File handling error: {str(e)}")
            return jsonify({"error": "❌ Error processing file"}), 500

    except Exception as e:
        print(f"Upload error: {str(e)}")
        return jsonify({"error": "❌ Server error processing upload"}), 500

@app.route("/ai", methods=["POST"])
def use_ai():
    try:
        if 'user_id' not in session:
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
        print(f"AI Error: {str(e)}")  # Add error logging
        return jsonify({"error": "An error occurred while processing your request."}), 500

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

@app.route("/generate-image", methods=["POST"])
def generate_image():
    try:
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 403

        data = request.json
        prompt = data.get("prompt", "").strip()

        if not prompt:
            return jsonify({"error": "Please provide a prompt for image generation."}), 400

        # Using Pixabay API to search for images
        params = {
            'key': PIXABAY_API_KEY,
            'q': prompt,
            'image_type': 'photo',
            'safesearch': 'true',
            'per_page': 3,
            'lang': 'en'
        }

        print(f"Searching for images with prompt: {prompt}")  # Debug log
        
        response = requests.get(
            PIXABAY_API_URL,
            params=params,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            if data['hits'] and len(data['hits']) > 0:
                # Get the first image URL
                image_url = data['hits'][0]['largeImageURL']
                
                # Download the image
                image_response = requests.get(image_url)
                if image_response.status_code == 200:
                    image_base64 = base64.b64encode(image_response.content).decode('utf-8')
                    return jsonify({
                        "image": image_base64,
                        "prompt": prompt
                    })
                else:
                    return jsonify({"error": "Error downloading image"}), 500
            else:
                return jsonify({"error": "No images found for your prompt"}), 404
        else:
            print(f"API Error: {response.text}")  # Debug log
            return jsonify({"error": f"Image search failed: {response.text}"}), 500

    except Exception as e:
        print(f"Image search error: {str(e)}")
        return jsonify({"error": f"An error occurred during image search: {str(e)}"}), 500

# Error handling
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html'), 500

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

if __name__ == "__main__":
    with app.app_context():
        # Initialize database and create tables
        init_db()
        
        try:
            # Connect to database to create test users
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)
                
                # Create test users only if they don't exist
                test_users = [
                    {
                        'username': 'test1',
                        'email': 'test1@example.com',
                        'password': 'test123'
                    },
                    {
                        'username': 'test2',
                        'email': 'test2@example.com',
                        'password': 'test123'
                    }
                ]
                
                for user_data in test_users:
                    try:
                        # Check if user already exists
                        cursor.execute("SELECT id FROM users WHERE email = %s OR username = %s", 
                                     (user_data['email'], user_data['username']))
                        existing_user = cursor.fetchone()
                        
                        if not existing_user:
                            # Hash the password
                            hashed_password = generate_password_hash(user_data['password'])
                            
                            # Insert new user
                            cursor.execute("""
                                INSERT INTO users (username, email, password) 
                                VALUES (%s, %s, %s)
                            """, (user_data['username'], user_data['email'], hashed_password))
                            
                            conn.commit()
                            print(f"Created test user: {user_data['username']}")
                        else:
                            print(f"Test user {user_data['username']} already exists")
                            
                    except Exception as e:
                        print(f"Error creating test user {user_data['username']}: {str(e)}")
                
                # Verify test users exist
                cursor.execute("SELECT username, email FROM users")
                existing_users = cursor.fetchall()
                print("\nExisting users in database:")
                for user in existing_users:
                    print(f"Username: {user['username']}, Email: {user['email']}")
                
                cursor.close()
                conn.close()
                
        except Exception as e:
            print(f"Error setting up test users: {str(e)}")
        
    app.run(debug=True)

def edit_file():
    pass