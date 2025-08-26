from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy  # pyright: ignore[reportMissingImports]
from datetime import datetime
import os
from reportlab.lib.pagesizes import letter  # pyright: ignore[reportMissingModuleSource]
from reportlab.pdfgen import canvas  # pyright: ignore[reportMissingModuleSource]
from io import BytesIO
from sqlalchemy import func  # pyright: ignore[reportMissingImports]
import random
import string
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user  # pyright: ignore[reportMissingImports]
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_key_that_you_should_change' # Add a secret key for Flask sessions

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///receipt_management.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User Model for Authentication
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

# Database Models
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20))
    receipts = db.relationship('Receipt', backref='customer', lazy=True)
    appointments = db.relationship('Appointment', backref='customer', lazy=True)

    def __repr__(self):
        return f'<Customer {self.name}>'

class Receipt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receipt_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    amount_paid = db.Column(db.Numeric(10, 2), nullable=False)
    balance = db.Column(db.Numeric(10, 2), nullable=False)
    receipt_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<Receipt {self.receipt_number}>'

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.Text)

    def __repr__(self):
        return f'<Appointment {self.appointment_date}>'

# --- Dummy Data Removed ---

@app.route('/')
@login_required
def dashboard():
    # Get search parameters
    search_query = request.args.get('search', '')
    filter_type = request.args.get('filter_type', '')
    date_filter = request.args.get('date_filter', '')
    
    # Base queries
    receipts_query = db.session.query(Receipt.id, Receipt.receipt_number, Receipt.customer_id, Receipt.amount_paid, Receipt.balance, Receipt.receipt_date, Customer.name.label('customer_name'), Customer.phone.label('customer_phone')).join(Customer)
    customers_query = Customer.query
    
    # Apply search filters
    if search_query:
        if filter_type == 'receipt':
            receipts_query = receipts_query.filter(
                db.or_(
                    Receipt.receipt_number.ilike(f'%{search_query}%'),
                    Customer.name.ilike(f'%{search_query}%')
                )
            )
        elif filter_type == 'customer':
            customers_query = customers_query.filter(
                Customer.name.ilike(f'%{search_query}%')
            )
        elif filter_type == 'amount':
            try:
                amount = float(search_query)
                receipts_query = receipts_query.filter(
                    db.or_(
                        Receipt.amount_paid == amount,
                        Receipt.balance == amount
                    )
                )
            except ValueError:
                pass
        else:
            # Search in all fields
            receipts_query = receipts_query.filter(
                db.or_(
                    Receipt.receipt_number.ilike(f'%{search_query}%'),
                    Customer.name.ilike(f'%{search_query}%'),
                    Customer.phone.ilike(f'%{search_query}%')
                )
            )
            customers_query = customers_query.filter(
                db.or_(
                    Customer.name.ilike(f'%{search_query}%'),
                    Customer.phone.ilike(f'%{search_query}%')
                )
            )
    
    # Apply date filter
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            receipts_query = receipts_query.filter(Receipt.receipt_date == filter_date)
        except ValueError:
            pass
    
    # Get filtered results
    recent_payments = receipts_query.order_by(Receipt.id.desc()).limit(10).all()
    
    # Calculate totals from filtered data
    total_paid = receipts_query.with_entities(func.sum(Receipt.amount_paid)).scalar() or 0
    total_balance = receipts_query.with_entities(func.sum(Receipt.balance)).scalar() or 0
    total_customers = customers_query.count()
    total_payments = receipts_query.count()

    upcoming_appointments = Appointment.query.filter(Appointment.appointment_date >= datetime.utcnow()).order_by(Appointment.appointment_date).limit(5).all()

    # Chart data
    receipts_data = []
    chart_labels = []
    chart_data = []

    return render_template('dashboard.html', 
                           total_paid=total_paid, 
                           total_balance=total_balance,
                           total_customers=total_customers,
                           total_payments=total_payments,
                           recent_payments=recent_payments,
                           upcoming_appointments=upcoming_appointments,
                           chart_labels=chart_labels,
                           chart_data=chart_data)

@app.route('/view_payments')
@login_required
def view_payments():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    amount_filter = request.args.get('amount_filter', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    sort_by = request.args.get('sort_by', 'date_desc')
    
    # Base query
    query = Receipt.query.join(Customer)
    
    # Apply search filter
    if search_query:
        query = query.filter(
            db.or_(
                Receipt.receipt_number.ilike(f'%{search_query}%'),
                Customer.name.ilike(f'%{search_query}%'),
                Customer.phone.ilike(f'%{search_query}%')
            )
        )
    
    # Apply amount filter
    if amount_filter == 'paid':
        query = query.filter(Receipt.amount_paid > 0)
    elif amount_filter == 'balance':
        query = query.filter(Receipt.balance > 0)
    
    # Apply date filters
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(Receipt.receipt_date >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(Receipt.receipt_date <= to_date)
        except ValueError:
            pass
    
    # Apply sorting
    if sort_by == 'date_desc':
        query = query.order_by(Receipt.receipt_date.desc())
    elif sort_by == 'date_asc':
        query = query.order_by(Receipt.receipt_date.asc())
    elif sort_by == 'amount_desc':
        query = query.order_by(Receipt.amount_paid.desc())
    elif sort_by == 'amount_asc':
        query = query.order_by(Receipt.amount_paid.asc())
    else:
        query = query.order_by(Receipt.receipt_date.desc())
    
    payments = query.paginate(
        page=page, per_page=20, error_out=False)
    return render_template('view_payments.html', payments=payments)

@app.route('/view_customers')
@login_required
def view_customers():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort_by', 'name_asc')
    
    # Base query
    query = Customer.query
    
    # Apply search filter
    if search_query:
        query = query.filter(
            db.or_(
                Customer.name.ilike(f'%{search_query}%'),
                Customer.phone.ilike(f'%{search_query}%')
            )
        )
    
    # Apply sorting
    if sort_by == 'name_asc':
        query = query.order_by(Customer.name.asc())
    elif sort_by == 'name_desc':
        query = query.order_by(Customer.name.desc())
    elif sort_by == 'id_asc':
        query = query.order_by(Customer.id.asc())
    elif sort_by == 'id_desc':
        query = query.order_by(Customer.id.desc())
    else:
        query = query.order_by(Customer.name.asc())
    
    customers = query.paginate(
        page=page, per_page=20, error_out=False)
    return render_template('view_customers.html', customers=customers)

@app.route('/view_appointments')
@login_required
def view_appointments():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    sort_by = request.args.get('sort_by', 'date_asc')
    
    # Base query
    query = Appointment.query.join(Customer)
    
    # Apply search filter
    if search_query:
        query = query.filter(
            db.or_(
                Customer.name.ilike(f'%{search_query}%'),
                Customer.phone.ilike(f'%{search_query}%'),
                Appointment.description.ilike(f'%{search_query}%')
            )
        )
    
    # Apply date filters
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Appointment.appointment_date >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(Appointment.appointment_date <= to_date)
        except ValueError:
            pass
    
    # Apply sorting
    if sort_by == 'date_asc':
        query = query.order_by(Appointment.appointment_date.asc())
    elif sort_by == 'date_desc':
        query = query.order_by(Appointment.appointment_date.desc())
    elif sort_by == 'customer_asc':
        query = query.order_by(Customer.name.asc())
    elif sort_by == 'customer_desc':
        query = query.order_by(Customer.name.desc())
    else:
        query = query.order_by(Appointment.appointment_date.asc())
    
    appointments = query.paginate(
        page=page, per_page=20, error_out=False)
    return render_template('view_appointments.html', appointments=appointments)

@app.route('/add_receipt', methods=['GET', 'POST'])
@login_required
def add_receipt():
    if request.method == 'POST':
        customer_name = request.form['customer_name']
        phone = request.form['phone']
        amount_paid = float(request.form['amount_paid'])
        balance = float(request.form['balance'])
        receipt_date = datetime.strptime(request.form['receipt_date'], '%Y-%m-%d').date()
        
        # Automatic Receipt Number Generation
        last_receipt = Receipt.query.order_by(Receipt.id.desc()).first()
        if last_receipt:
            last_num = int(last_receipt.receipt_number[1:])
            new_num = last_num + 1
            receipt_number = f"R{new_num:03d}"
        else:
            receipt_number = "R001"

        customer = Customer.query.filter_by(name=customer_name).first()
        if not customer:
            customer = Customer(name=customer_name, phone=phone)
            db.session.add(customer)
            db.session.commit()

        new_receipt = Receipt(receipt_number=receipt_number,
                              customer_id=customer.id,
                              amount_paid=amount_paid,
                              balance=balance,
                              receipt_date=receipt_date)
        db.session.add(new_receipt)
        db.session.commit()

        flash('Receipt added successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    # Generate a unique receipt number for display on the form (optional)
    last_receipt = Receipt.query.order_by(Receipt.id.desc()).first()
    if last_receipt:
        last_num = int(last_receipt.receipt_number[1:])
        new_num = last_num + 1
        suggested_receipt_number = f"R{new_num:03d}"
    else:
        suggested_receipt_number = "R001"

    return render_template('add_receipt.html', suggested_receipt_number=suggested_receipt_number)

@app.route('/generate_receipt_pdf/<int:receipt_id>')
@login_required
def generate_receipt_pdf(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)
    customer = Customer.query.get_or_404(receipt.customer_id)

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    p.drawString(100, height - 50, f"Receipt Number: {receipt.receipt_number}")
    p.drawString(100, height - 70, f"Date: {receipt.receipt_date.strftime('%Y-%m-%d')}")
    p.drawString(100, height - 90, f"Customer Name: {customer.name}")
    p.drawString(100, height - 110, f"Phone: {customer.phone or 'N/A'}")
    p.drawString(100, height - 130, f"Amount Paid: ${receipt.amount_paid:.2f}")
    p.drawString(100, height - 150, f"Balance: ${receipt.balance:.2f}")

    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f'receipt_{receipt.receipt_number}.pdf', mimetype='application/pdf')

@app.route('/generate_receipt_doc/<int:receipt_id>')
@login_required
def generate_receipt_doc(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)
    customer = Customer.query.get_or_404(receipt.customer_id)
    
    # Create a simple text file as DOC alternative
    content = f"""RECEIPT

Receipt Number: {receipt.receipt_number}
Date: {receipt.receipt_date.strftime('%Y-%m-%d')}
Customer Name: {customer.name}
Phone: {customer.phone or 'N/A'}
Amount Paid: ${receipt.amount_paid:.2f}
Balance: ${receipt.balance:.2f}

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    buffer = BytesIO()
    buffer.write(content.encode('utf-8'))
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=True, download_name=f'receipt_{receipt.receipt_number}.txt', mimetype='text/plain')

@app.route('/view_receipt/<int:receipt_id>')
@login_required
def view_receipt(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)
    return render_template('view_receipt.html', receipt=receipt)

@app.route('/edit_receipt/<int:receipt_id>', methods=['GET', 'POST'])
@login_required
def edit_receipt(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)
    if request.method == 'POST':
        receipt.amount_paid = float(request.form['amount_paid'])
        receipt.balance = float(request.form['balance'])
        receipt.receipt_date = datetime.strptime(request.form['receipt_date'], '%Y-%m-%d').date()
        db.session.commit()
        flash('Receipt updated successfully!', 'success')
        return redirect(url_for('view_payments'))
    return render_template('edit_receipt.html', receipt=receipt)

@app.route('/delete_receipt/<int:receipt_id>', methods=['DELETE'])
@login_required
def delete_receipt(receipt_id):
    try:
        receipt = Receipt.query.get_or_404(receipt_id)
        db.session.delete(receipt)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists. Please choose a different one.', 'danger')
        else:
            new_user = User(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Login failed. Check your username and password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

@app.cli.command("create-db")
def create_db():
    """Creates the database tables."""
    with app.app_context():
        db.create_all()
    print("Database tables created!")
