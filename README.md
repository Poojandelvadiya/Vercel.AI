# AI Chatbot with MongoDB Integration

A Flask-based AI chatbot application that uses MongoDB for data storage and Google's Gemini AI for intelligent responses.

## Features

- User authentication (signup, login, password reset)
- AI-powered chat interface
- File upload and analysis
- Image generation using Pixabay API
- MongoDB database integration
- Email notifications
- Responsive design

## Prerequisites

- Python 3.10 or higher
- MongoDB Atlas account
- Google Gemini AI API key
- Pixabay API key
- Gmail account for email notifications

## Installation

1. Clone the repository:
```bash
git clone https://github.com/poojandelvadiya/Vercel.AI.git
cd ai-chatbot
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the project root with the following variables:
```
MONGODB_URI=your_mongodb_connection_string
GEMINI_API_KEY=your_gemini_api_key
PIXABAY_API_KEY=your_pixabay_api_key
MAIL_USERNAME=your_gmail_address
MAIL_PASSWORD=your_gmail_app_password
```

5. Initialize the database:
```bash
python app.py
```

## Usage

1. Start the application:
```bash
python app.py
```

2. Open your browser and navigate to `http://localhost:5000`

3. Register a new account or use the test credentials:
   - Username: admin
   - Password: admin123

## Project Structure

```
ai-chatbot/
├── app.py              # Main application file
├── requirements.txt    # Python dependencies
├── static/            # Static files (CSS, JS, images)
├── templates/         # HTML templates
├── uploads/          # Temporary file upload directory
└── .env              # Environment variables
```

## Contributing

1. Fork the repository
2. Create a new branch (`git checkout -b feature/improvement`)
3. Make your changes
4. Commit your changes (`git commit -am 'Add new feature'`)
5. Push to the branch (`git push origin feature/improvement`)
6. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Google Gemini AI for the chatbot functionality
- MongoDB Atlas for database hosting
- Pixabay for image generation
- Flask framework and its extensions
