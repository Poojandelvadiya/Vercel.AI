from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import google.generativeai as genai
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import secrets
from datetime import datetime
import time
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import json
import logging
from functools import wraps

# PIL imports
from PIL import Image  # Basic image handling
from PIL import ImageDraw  # For drawing on images
from PIL import ImageFont  # For adding text to images
from PIL import ImageFilter  # For image filters
from PIL import ImageEnhance  # For image enhancement

import requests
from io import BytesIO
import base64

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# MongoDB Configuration
MONGO_URI = os.getenv('MONGODB_URI')
DB_NAME = os.getenv('MONGODB_DB', 'Vercel')

# Initialize MongoDB client
client = None
db = None

def get_db():
    """Get MongoDB database connection"""
    global client, db
    try:
        if client is None:
            client = MongoClient(MONGO_URI)
            db = client[DB_NAME]
            # Test connection
            client.server_info()
            logger.info("Successfully connected to MongoDB Atlas!")
        return db
    except Exception as e:
        logger.error(f"MongoDB connection error: {str(e)}")
        return None

def init_db():
    """Initialize database collections and indexes"""
    try:
        db = get_db()
        if db is None:
            return False

        # Create collections if they don't exist
        collections = ['users', 'login_history', 'chat_history']
        for collection in collections:
            if collection not in db.list_collection_names():
                db.create_collection(collection)

        # Create indexes
        db.users.create_index([("username", 1)], unique=True)
        db.users.create_index([("email", 1)], unique=True)
        db.login_history.create_index([("user_id", 1), ("login_time", -1)])
        db.chat_history.create_index([("user_id", 1), ("timestamp", -1)])
        db.chat_history.create_index([("timestamp", 1)], expireAfterSeconds=2592000)  # 30 days TTL

        logger.info("Database collections and indexes initialized successfully!")
        return True
    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
        return False

def setup_test_users():
    """Set up test users if they don't exist"""
    try:
        db = get_db()
        if db is None:
            return False

        test_users = [
            {
                "username": "admin",
                "email": "admin@example.com",
                "password": generate_password_hash("admin123")
            },
            {
                "username": "test",
                "email": "test@example.com",
                "password": generate_password_hash("test123")
            },
            {
                "username": "user1",
                "email": "user1@example.com",
                "password": generate_password_hash("password123")
            }
        ]

        for user in test_users:
            if not db.users.find_one({"username": user["username"]}):
                db.users.insert_one(user)

        logger.info("Test users setup completed successfully!")
        return True
    except Exception as e:
        logger.error(f"Error setting up test users: {str(e)}")
        return False

# Initialize database and setup test users
init_db()
setup_test_users()

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
    
    # Get database connection
    db = get_db()
    if db is None:
        flash('Database connection error', 'error')
        return render_template('index.html', username=session.get('username'), chat_history=[])
    
    try:
        # Get user's chat history with proper user_id filtering
        user_id = session['user_id']
        chat_history = list(db.chat_history.find(
            {"user_id": user_id},  # Filter by current user's ID
            {"message": 1, "response": 1, "timestamp": 1, "_id": 0}
        ).sort("timestamp", 1))  # Sort by timestamp in ascending order
        
        # Convert ObjectId to string for JSON serialization
        for msg in chat_history:
            msg['timestamp'] = msg['timestamp'].isoformat()
        
        print(f"Found {len(chat_history)} messages for user {user_id}")  # Debug log
        
        return render_template('index.html', 
                             username=session.get('username'),
                             chat_history=chat_history)
    except Exception as e:
        print(f"Error fetching chat history: {str(e)}")
        return render_template('index.html', 
                             username=session.get('username'),
                             chat_history=[])

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
        
        db = get_db()
        if db is None:
            print("Failed to establish database connection")
            flash('Database connection error. Please try again later.', 'error')
            return render_template('register.html')
        
        # Check if username exists
        if db.users.count_documents({"username": username}) > 0:
            flash('Username already exists', 'error')
            return render_template('register.html')
        
        # Check if email exists
        if db.users.count_documents({"email": email}) > 0:
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        try:
            # Hash the password
            hashed_password = generate_password_hash(password)
            
            # Insert new user
            db.users.insert_one({
                "username": username,
                "email": email,
                "password": hashed_password
            })
            
            print(f"User registered successfully: {username}")
            
            flash('Registration successful! Please sign in.', 'success')
            return redirect(url_for('signin'))
            
        except Exception as e:
            print(f"Error inserting new user: {e}")
            if e.code == 11000:  # Duplicate key error
                flash('Username or email already exists', 'error')
            else:
                flash('Error creating account. Please try again.', 'error')
            return render_template('register.html')

    return render_template('register.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please enter both username and password', 'error')
            return render_template('signin.html')
        
        db = get_db()
        if db is None:
            flash('Database connection error', 'error')
            return render_template('signin.html')
        
        # Debug: Print the username being searched
        print(f"Attempting login for username: {username}")
        
        # Get user details including password hash
        user = db.users.find_one({"username": username})
        
        # Debug: Print if user was found
        print(f"User found in database: {user is not None}")
        
        if user:
            # Debug: Print password verification attempt
            print(f"Verifying password for user: {user['username']}")
            try:
                if check_password_hash(user['password'], password):
                    print("Password verified successfully")
                    session['user_id'] = str(user['_id'])
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
    
    # For GET request, just render the signin template
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
        
        db = get_db()
        if not db:
            flash('Database connection error. Please try again later.', 'error')
            return render_template('forgot_password.html')
        
        # Debug: Print email being searched
        print(f"Searching for email: {email}")
        
        # Check if email exists
        user = db.users.find_one({"email": email})
        
        # Debug: Print user found or not
        print(f"User found: {user is not None}")
        
        if user:
            try:
                # Generate reset token
                token = secrets.token_urlsafe(32)
                
                # Store token in database
                db.users.update_one(
                    {"_id": ObjectId(user['_id'])},
                    {"$set": {"reset_token": token}}
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
                    flash('Error sending email. Please check your email configuration.', 'error')
                    return render_template('forgot_password.html')
            
            except Exception as e:
                print(f"Token generation/storage error: {e}")
                flash('Error generating reset token. Please try again.', 'error')
                return render_template('forgot_password.html')
        else:
            flash('No account found with that email address.', 'error')
            return render_template('forgot_password.html')
    
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        db = get_db()
        user = db.users.find_one({"reset_token": token})
        
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
            db.users.update_one(
                {"_id": ObjectId(user['_id'])},
                {"$set": {"password": hashed_password, "reset_token": None}}
            )
            
            flash('Your password has been updated successfully.', 'success')
            return redirect(url_for('signin'))
        
        return render_template('reset_password.html')
        
    except Exception as e:
        flash('An error occurred. Please try again later.', 'error')
        print(f"Database error: {e}")
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

        # Get database connection
        db = get_db()
        if db is None:
            return jsonify({"error": "Database connection error"}), 500

        try:
            user_id = session['user_id']  # Get current user's ID
            
            # Get last 5 messages for context with proper user_id filtering
            chat_history = list(db.chat_history.find(
                {"user_id": user_id},  # Filter by current user's ID
                {"message": 1, "response": 1, "_id": 0}
            ).sort("timestamp", -1).limit(5))
            
            # Build context from history
            context = ""
            if chat_history:
                context = "Previous conversation:\n"
                for msg in reversed(chat_history):
                    context += f"User: {msg['message']}\nAssistant: {msg['response']}\n"
            
            # Create prompt with context
            full_prompt = f"{context}\nCurrent message: {prompt}"
            
            # Configure the model with simplified parameters
            model = genai.GenerativeModel(
                "gemini-1.5-pro",
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 2048
                }
            )

            # Generate response with retry mechanism
            max_retries = 3
            retry_count = 0
            last_error = None

            while retry_count < max_retries:
                try:
                    response = model.generate_content(full_prompt)
                    
                    if response and hasattr(response, 'text'):
                        reply = response.text.strip()
                        
                        # Store the conversation in database with proper user_id
                        db.chat_history.insert_one({
                            "user_id": user_id,  # Use the current user's ID
                            "message": prompt,
                            "response": reply,
                            "timestamp": datetime.utcnow()
                        })
                        
                        print(f"Stored message for user {user_id}")  # Debug log
                        
                        # Return response with timestamp and streaming flag
                        return jsonify({
                            "response": reply,
                            "timestamp": datetime.utcnow().isoformat(),
                            "stream": True  # Flag to indicate streaming response
                        })
                    
                    retry_count += 1
                    time.sleep(1)  # Wait before retrying
                    
                except Exception as e:
                    last_error = str(e)
                    retry_count += 1
                    time.sleep(1)
                    print(f"Attempt {retry_count} failed: {last_error}")
            
            # If all retries failed
            error_message = "I apologize, but I encountered an error while generating the response. Please try again."
            if "quota" in last_error.lower():
                error_message = "I've reached my response limit. Please try again later."
            elif "invalid" in last_error.lower():
                error_message = "I couldn't process your request. Please try rephrasing your question."
            elif "timeout" in last_error.lower():
                error_message = "The request timed out. Please try again."
            
            return jsonify({
                "response": error_message,
                "timestamp": datetime.utcnow().isoformat(),
                "stream": False  # No streaming for error messages
            })
            
        except Exception as e:
            print(f"AI Generation error: {str(e)}")
            return jsonify({
                "response": "An error occurred while processing your request. Please try again.",
                "timestamp": datetime.utcnow().isoformat(),
                "stream": False  # No streaming for error messages
            })
            
    except Exception as e:
        print(f"AI Error: {str(e)}")
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
        # Initialize database and create collections
        init_db()
        
        try:
            # Connect to database to create test users
            db = get_db()
            if db is not None:  # Fixed the database check
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
                        existing_user = db.users.find_one({"email": user_data['email']})
                        
                        if not existing_user:
                            # Hash the password
                            hashed_password = generate_password_hash(user_data['password'])
                            
                            # Insert new user
                            db.users.insert_one({
                                "username": user_data['username'],
                                "email": user_data['email'],
                                "password": hashed_password
                            })
                            
                            print(f"Created test user: {user_data['username']}")
                        else:
                            print(f"Test user {user_data['username']} already exists")
                            
                    except Exception as e:
                        print(f"Error creating test user {user_data['username']}: {str(e)}")
                
                # Verify test users exist
                existing_users = db.users.find()
                print("\nExisting users in database:")
                for user in existing_users:
                    print(f"Username: {user['username']}, Email: {user['email']}")
                
        except Exception as e:
            print(f"Error setting up test users: {str(e)}")
        
    app.run(debug=True)

def edit_file():
    pass