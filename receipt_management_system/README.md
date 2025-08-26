# Receipt Management System

This is a small, lightweight Receipt Management System built with Flask, Bootstrap, and SQLite. It includes user authentication (Login/Register/Logout), receipt management, appointment tracking, and dashboard visualizations.

## Features:
- User Authentication: Register, Login, Logout
- Add New Receipt: Customer Name, Phone, Amount Paid, Balance, Date, Automatic Receipt Number
- Generate PDF Receipt
- Dashboard: Total Paid, Total Outstanding Balance, Upcoming Appointments, Receipts Trend Chart

## Setup Instructions

### 1. Python Environment Setup

1.  **Navigate to Project Directory:**
    ```bash
    cd receipt_management_system
    ```
2.  **Create and Activate Virtual Environment:**
    ```bash
    python -m venv venv
    # On Windows:
    .\\venv\\Scripts\\activate.ps1
    # On macOS/Linux:
    source venv/bin/activate
    ```
3.  **Install Dependencies:**
    ```bash
    pip install Flask Flask-SQLAlchemy reportlab Flask-Login Werkzeug
    ```

### 2. Database Setup (SQLite)

SQLite is a file-based database, so no external server installation is required. The database file `receipt_management.db` will be created automatically in your project directory when you run the `create-db` command.

1.  **Create Database Tables:**
    ```bash
    flask create-db
    ```
    You should see `Database tables created!` if successful.

### 3. Run the Application

1.  **Ensure you are in the `receipt_management_system` directory** and your virtual environment is active.
2.  **Run the Flask application:**
    ```bash
    flask run
    ```

    Leave this terminal window open.

3.  **Access the application:**
    Open your web browser and go to `http://127.0.0.1:5000/`

## Project Structure

```
receipt_management_system/
├── app.py              # Main Flask application logic
├── receipt_management.db  # SQLite database file
├── README.md           # Project setup and running instructions
├── templates/
│   ├── base.html       # Base HTML template
│   ├── add_receipt.html # Form to add new receipts
│   ├── dashboard.html  # Dashboard view
│   ├── login.html      # User login form
│   └── register.html   # User registration form
└── venv/               # Python virtual environment
```
