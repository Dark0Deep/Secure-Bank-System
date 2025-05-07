# Bank Management System

A comprehensive bank management system with customer and admin functionalities.

## Features

- Customer and Admin login
- Account management
- Balance checking
- Deposits and withdrawals
- Money transfers
- Loan management
- Employee management
- Customer reports

## Setup Instructions

1. Install MongoDB on your system
2. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a .env file with your MongoDB connection string:
   ```
   MONGO_URI=mongodb://localhost:27017/bankdb
   SECRET_KEY=your_secret_key
   ```
4. Run the application:
   ```
   python app.py
   ```
5. Access the application at http://localhopythst:5000

## Project Structure

- `app.py`: Main application file
- `models/`: Database models
- `routes/`: API routes
- `static/`: CSS, JS, and other static files
- `templates/`: HTML templates
- `utils/`: Utility functions 