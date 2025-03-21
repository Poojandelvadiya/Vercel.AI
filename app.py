from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import google.generativeai as genai
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import secrets
from pymongo import MongoClient
from datetime import datetime
import time
import json
import urllib.parse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import requests
import base64
from PIL import Image
from io import BytesIO
import ssl
import paramiko
import socks
import socket

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = secrets.token_hex(16)

# Mail Settings
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'poojandelvadiya27@gmail.com'
app.config['MAIL_PASSWORD'] = 'wdvb bpqy jujm rbgj'
app.config['MAIL_DEFAULT_SENDER'] = 'poojandelvadiya27@gmail.com'

mail = Mail(app)

# MongoDB Configuration
MONGODB_USERNAME = urllib.parse.quote_plus("poojandelvadiya27")
MONGODB_PASSWORD = urllib.parse.quote_plus("Poojan27@")
MONGODB_URI = f"mongodb+srv://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@cluster0.6dw8w.mongodb.net/chatbot_db?retryWrites=true&w=majority"

# SSH Configuration
SSH_HOST = "cluster0.6dw8w.mongodb.net"  # MongoDB Atlas cluster hostname
SSH_PORT = 22  # Default SSH port
SSH_USERNAME = "poojandelvadiya27"  # Your MongoDB Atlas username
SSH_KEY_PATH = "mongodb_ssh_key"  # Path to your SSH private key
SSH_PASSPHRASE = ""  # Your SSH key passphrase (if you set one when creating the key)
MONGODB_HOST = "cluster0.6dw8w.mongodb.net"  # MongoDB Atlas host
MONGODB_PORT = 27017  # MongoDB port

def setup_ssh_tunnel():
    try:
        # Create SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Load private key with passphrase if set
        private_key = paramiko.RSAKey.from_private_key_file(
            SSH_KEY_PATH,
            password=SSH_PASSPHRASE if SSH_PASSPHRASE else None
        )
        
        # Connect to SSH server
        ssh.connect(
            hostname=SSH_HOST,
            port=SSH_PORT,
            username=SSH_USERNAME,
            pkey=private_key
        )
        
        # Create SOCKS proxy
        socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 1080)
        socket.socket = socks.socksocket
        
        return ssh
    except Exception as e:
        print(f"SSH Tunnel Error: {str(e)}")
        return None

def get_db_connection():
    try:
        # Initialize MongoDB client with connection options
        client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000,  # 5 seconds timeout
            connectTimeoutMS=5000,
            socketTimeoutMS=5000
        )
        
        # Test the connection
        client.server_info()
        return client.chatbot_db
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None

def init_db():
    db = get_db_connection()
    if db is None:
        print("Failed to connect to database")
        return
    
    try:
        # Create collections if they don't exist
        if 'users' not in db.list_collection_names():
            db.create_collection('users')
        if 'chat_history' not in db.list_collection_names():
            db.create_collection('chat_history')
        
        # Create indexes
        db.users.create_index([('username', 1)], unique=True)
        db.users.create_index([('email', 1)], unique=True)
        db.chat_history.create_index([('user_id', 1)])
        db.chat_history.create_index([('timestamp', 1)])
        
        # Insert sample users if users collection is empty
        if db.users.count_documents({}) == 0:
            sample_users = [
                {
                    'username': 'admin',
                    'email': 'admin@example.com',
                    'password': generate_password_hash('admin123'),
                    'role': 'admin',
                    'created_at': datetime.utcnow()
                },
                {
                    'username': 'user',
                    'email': 'user@example.com',
                    'password': generate_password_hash('user123'),
                    'role': 'user',
                    'created_at': datetime.utcnow()
                }
            ]
            db.users.insert_many(sample_users)
            print("Sample users created")
        
        print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")

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
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        try:
            db = get_db_connection()
            if db is not None:
                # Check if username already exists
                if db.users.find_one({'username': username}):
                    flash('Username already exists!', 'error')
                    return render_template('Register.html')
                
                # Check if email already exists
                if db.users.find_one({'email': email}):
                    flash('Email already registered!', 'error')
                    return render_template('Register.html')
                
                # Hash password
                hashed_password = generate_password_hash(password)
                
                # Insert new user
                db.users.insert_one({
                    'username': username,
                    'email': email,
                    'password': hashed_password
                })
                
                flash('Registration successful! Please sign in.', 'success')
                return redirect(url_for('signin'))
            else:
                flash('Database connection error. Please try again later.', 'error')
                return render_template('Register.html')
                
        except Exception as e:
            print(f"Registration error: {str(e)}")
            flash('An error occurred during registration. Please try again.', 'error')
            return render_template('Register.html')
    
    return render_template('Register.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please enter both username and password', 'error')
            return render_template('signin.html')
        
        try:
            db = get_db_connection()
            if db is None:
                flash('Database connection error. Please try again later.', 'error')
                return render_template('signin.html')
            
            # Find user by username
            user = db.users.find_one({'username': username})
            
            if user and check_password_hash(user['password'], password):
                # Record login history
                db.login_history.insert_one({
                    'user_id': user['_id'],
                    'username': user['username'],
                    'login_time': datetime.utcnow()
                })
                
                session['user_id'] = str(user['_id'])
                session['username'] = user['username']
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password', 'error')
                return render_template('signin.html')
                
        except Exception as e:
            print(f"Signin error: {e}")
            flash('An error occurred during login. Please try again later.', 'error')
            return render_template('signin.html')
            
    return render_template('signin.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Please enter your email address', 'error')
            return render_template('forgot_password.html')
        
        try:
            db = get_db_connection()
            if not db:
                flash('Database connection error', 'error')
                return render_template('forgot_password.html')
            
            # Find user by email
            user = db.users.find_one({'email': email})
            
            if user:
                # Generate reset token
                token = secrets.token_urlsafe(32)
                
                # Update user with reset token
                db.users.update_one(
                    {'_id': user['_id']},
                    {'$set': {'reset_token': token}}
                )
                
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
                    flash('Error sending email. Please try again later.', 'error')
                    return render_template('forgot_password.html')
            else:
                flash('No account found with that email address.', 'error')
                return render_template('forgot_password.html')
                
        except Exception as e:
            print(f"Forgot password error: {e}")
            flash('An error occurred. Please try again later.', 'error')
            return render_template('forgot_password.html')
    
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        db = get_db_connection()
        if not db:
            flash('Database connection error', 'error')
            return redirect(url_for('signin'))
        
        # Find user with reset token
        user = db.users.find_one({'reset_token': token})
        
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
            
            # Update password and remove token
            hashed_password = generate_password_hash(password)
            db.users.update_one(
                {'_id': user['_id']},
                {
                    '$set': {'password': hashed_password},
                    '$unset': {'reset_token': ""}
                }
            )
            
            flash('Your password has been updated successfully.', 'success')
            return redirect(url_for('signin'))
        
        return render_template('reset_password.html')
        
    except Exception as e:
        print(f"Reset password error: {e}")
        flash('An error occurred. Please try again later.', 'error')
        return redirect(url_for('signin'))

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
                    # Convert image to base64
                    image = Image.open(BytesIO(image_response.content))
                    buffered = BytesIO()
                    image.save(buffered, format="JPEG")
                    image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
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
            db = get_db_connection()
            if db is not None:  # Changed from 'if db:' to 'if db is not None:'
                cursor = db.users.find()
                
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
                        existing_user = db.users.find_one({'username': user_data['username']})
                        
                        if not existing_user:
                            # Hash the password
                            hashed_password = generate_password_hash(user_data['password'])
                            
                            # Insert new user
                            db.users.insert_one({
                                'username': user_data['username'],
                                'email': user_data['email'],
                                'password': hashed_password
                            })
                            
                            print(f"Created test user: {user_data['username']}")
                        else:
                            print(f"Test user {user_data['username']} already exists")
                            
                    except Exception as e:
                        print(f"Error creating test user {user_data['username']}: {str(e)}")
                
                        existing_users = db.users.find()
            print("\nExisting users in database:")
            for user in existing_users:
                    print(f"Username: {user['username']}, Email: {user['email']}")
            
        except Exception as e:
            print(f"Error setting up test users: {str(e)}")
    
    # Use a more stable server configuration
    try:
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
            use_reloader=False  # Disable reloader to prevent socket issues
        )
    except Exception as e:
        print(f"Server error: {str(e)}")
        # Fallback to basic configuration
    app.run(debug=True)

def edit_file():
    pass
