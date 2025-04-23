from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_pymongo import PyMongo
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
import datetime
from bson.objectid import ObjectId
import random
import string

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/bankdb")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "default_secret_key")

# Initialize MongoDB
mongo = PyMongo(app)

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data.get('_id'))
        self.username = user_data.get('username')
        self.email = user_data.get('email')
        self.role = user_data.get('role')
        self.created_at = user_data.get('created_at', datetime.datetime.now())
        
    def get_created_at_formatted(self):
        if isinstance(self.created_at, datetime.datetime):
            return self.created_at.strftime('%B %d, %Y')
        return 'N/A'

@login_manager.user_loader
def load_user(user_id):
    try:
        user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if user_data:
            return User(user_data)
    except:
        pass
    return None

def generate_account_number():
    """Generate a random account number with 3 capital letters followed by 16 digits"""
    # Generate 3 random capital letters
    letters = ''.join(random.choices(string.ascii_uppercase, k=3))
    # Generate 16 random digits
    digits = ''.join(random.choices(string.digits, k=16))
    return f"{letters}{digits}"

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Try to find user by email first
        user = mongo.db.users.find_one({'email': email})
        
        # If not found by email, try to find by username (for backward compatibility)
        if not user:
            user = mongo.db.users.find_one({'username': email})
        
        if user and check_password_hash(user['password'], password):
            user_obj = User(user)
            login_user(user_obj)
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('customer_dashboard'))
        
        flash('Invalid email or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        
        # Check if username already exists
        if mongo.db.users.find_one({'username': username}):
            flash('Username already exists')
            return redirect(url_for('register'))
        
        # Generate unique account number
        while True:
            account_number = generate_account_number()
            # Check if account number already exists
            if not mongo.db.accounts.find_one({'account_number': account_number}):
                break
        
        # Create new user
        user_id = mongo.db.users.insert_one({
            'username': username,
            'password': generate_password_hash(password),
            'email': email,
            'role': 'customer',
            'created_at': datetime.datetime.now()
        }).inserted_id
        
        # Create account for the user
        mongo.db.accounts.insert_one({
            'user_id': user_id,
            'balance': 0,
            'account_number': account_number,
            'created_at': datetime.datetime.now()
        })
        
        flash('Registration successful. Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('login'))

@app.route('/customer/dashboard')
@login_required
def customer_dashboard():
    if current_user.role != 'customer':
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        # Check if user is active
        user = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
        if not user.get('is_active', True):
            flash('Your account has been deactivated. Please contact support for assistance.')
            logout_user()
            return redirect(url_for('login'))
            
        account = mongo.db.accounts.find_one({'user_id': ObjectId(current_user.id)})
        if not account:
            flash('Account not found')
            return redirect(url_for('index'))
            
        # Get recent transactions
        transactions = list(mongo.db.transactions.find(
            {'user_id': ObjectId(current_user.id)}
        ).sort('created_at', -1).limit(5))
        
        # Format dates for display
        for transaction in transactions:
            if isinstance(transaction.get('created_at'), datetime.datetime):
                transaction['created_at_formatted'] = transaction['created_at'].strftime('%Y-%m-%d %H:%M')
            else:
                transaction['created_at_formatted'] = 'N/A'
        
        # Get recent loans
        recent_loans = list(mongo.db.loans.find(
            {'user_id': ObjectId(current_user.id)}
        ).sort('created_at', -1).limit(3))
        
        return render_template('customer/dashboard.html', 
                            account=account, 
                            transactions=transactions,
                            recent_loans=recent_loans,
                            is_active=user.get('is_active', True))
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}')
        return redirect(url_for('index'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('index'))
    
    try:
        # Get all customers with proper status handling
        customers = list(mongo.db.users.find({'role': 'customer'}))
        
        # Ensure each customer has the is_active field
        for customer in customers:
            if 'is_active' not in customer:
                # Update the customer document with default active status
                mongo.db.users.update_one(
                    {'_id': customer['_id']},
                    {'$set': {'is_active': True}}
                )
                customer['is_active'] = True
            
            # Get account information for each customer
            account = mongo.db.accounts.find_one({'user_id': customer['_id']})
            if account:
                customer['account_number'] = account.get('account_number', 'N/A')
                customer['balance'] = account.get('balance', 0)
            else:
                customer['account_number'] = 'N/A'
                customer['balance'] = 0
            
            # Format registration date
            if 'created_at' in customer:
                customer['registered_on'] = customer['created_at']
            else:
                customer['registered_on'] = datetime.datetime.now()
        
        # Calculate dashboard statistics
        total_customers = len(customers)
        total_balance = sum(customer.get('balance', 0) for customer in customers)
        active_customers = sum(1 for customer in customers if customer.get('is_active', True))
        
        # Count today's registrations
        today = datetime.datetime.now().date()
        todays_registrations = sum(1 for customer in customers 
                                if customer.get('created_at', datetime.datetime.now()).date() == today)
        
        # Print debug information
        print(f"Total customers: {total_customers}")
        print(f"Active customers: {active_customers}")
        print(f"Total balance: {total_balance}")
        print(f"Today's registrations: {todays_registrations}")
        
        # Debug customer status
        for customer in customers:
            print(f"Customer {customer['username']}: is_active = {customer.get('is_active', True)}")
        
        return render_template('admin/dashboard.html',
                            customers=customers,
                            total_customers=total_customers,
                            total_balance=total_balance,
                            active_customers=active_customers,
                            todays_registrations=todays_registrations)
    
    except Exception as e:
        print(f"Error in admin_dashboard: {str(e)}")
        flash(f'Error loading dashboard: {str(e)}')
        return redirect(url_for('index'))

@app.route('/account/balance')
@login_required
def balance():
    try:
        # Get account information
        account = mongo.db.accounts.find_one({'user_id': ObjectId(current_user.id)})
        if not account:
            flash('Account not found')
            return redirect(url_for('customer_dashboard'))
            
        # Get recent transactions
        transactions = list(mongo.db.transactions.find(
            {'user_id': ObjectId(current_user.id)}
        ).sort('created_at', -1).limit(5))
        
        # Format dates for display
        for transaction in transactions:
            if isinstance(transaction.get('created_at'), datetime.datetime):
                transaction['created_at_formatted'] = transaction['created_at'].strftime('%Y-%m-%d %H:%M')
            else:
                transaction['created_at_formatted'] = 'N/A'
        
        return render_template('account/balance.html', 
                            account=account,
                            transactions=transactions)
    except Exception as e:
        flash(f'Error loading balance: {str(e)}')
        return redirect(url_for('customer_dashboard'))

def check_account_status():
    """Helper function to check if user account is active"""
    user = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    if not user or not user.get('is_active', True):
        flash('Your account is currently deactivated. Please contact support for assistance.')
        return False
    return True

@app.route('/account/deposit', methods=['GET', 'POST'])
@login_required
def deposit():
    if not check_account_status():
        return redirect(url_for('customer_dashboard'))
        
    try:
        account = mongo.db.accounts.find_one({'user_id': ObjectId(current_user.id)})
        if not account:
            flash('Account not found')
            return redirect(url_for('customer_dashboard'))
            
        if request.method == 'POST':
            try:
                # Recheck status before processing transaction
                if not check_account_status():
                    return redirect(url_for('customer_dashboard'))
                    
                amount = float(request.form.get('amount', 0))
                password = request.form.get('password')
                
                if not password:
                    flash('Please enter your password to confirm the transaction')
                    return redirect(url_for('deposit'))
                
                # Verify password
                user = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
                if not user or not check_password_hash(user['password'], password):
                    flash('Invalid password')
                    return redirect(url_for('deposit'))
                
                if amount <= 0:
                    flash('Invalid amount')
                    return redirect(url_for('deposit'))
                
                # Update account balance
                result = mongo.db.accounts.update_one(
                    {'user_id': ObjectId(current_user.id)},
                    {'$inc': {'balance': amount}}
                )
                
                if result.modified_count == 0:
                    flash('Error updating balance')
                    return redirect(url_for('deposit'))
                
                # Record transaction
                mongo.db.transactions.insert_one({
                    'user_id': ObjectId(current_user.id),
                    'type': 'deposit',
                    'amount': amount,
                    'created_at': datetime.datetime.now()
                })
                
                flash(f'Successfully deposited ₹{amount}')
                return redirect(url_for('customer_dashboard'))
            except Exception as e:
                flash(f'Error processing deposit: {str(e)}')
                return redirect(url_for('deposit'))
        
        return render_template('account/deposit.html', account=account)
    except Exception as e:
        flash(f'Error loading deposit page: {str(e)}')
        return redirect(url_for('customer_dashboard'))

@app.route('/account/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    if not check_account_status():
        return redirect(url_for('customer_dashboard'))
        
    try:
        account = mongo.db.accounts.find_one({'user_id': ObjectId(current_user.id)})
        if not account:
            flash('Account not found')
            return redirect(url_for('customer_dashboard'))
            
        if request.method == 'POST':
            try:
                # Recheck status before processing transaction
                if not check_account_status():
                    return redirect(url_for('customer_dashboard'))
                    
                amount = float(request.form.get('amount', 0))
                password = request.form.get('password')
                
                if not password:
                    flash('Please enter your password to confirm the transaction')
                    return redirect(url_for('withdraw'))
                
                # Verify password
                user = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
                if not user or not check_password_hash(user['password'], password):
                    flash('Invalid password')
                    return redirect(url_for('withdraw'))
                
                if amount <= 0:
                    flash('Invalid amount')
                    return redirect(url_for('withdraw'))
                
                if account['balance'] < amount:
                    flash('Insufficient balance')
                    return redirect(url_for('withdraw'))
                
                # Update account balance
                result = mongo.db.accounts.update_one(
                    {'user_id': ObjectId(current_user.id)},
                    {'$inc': {'balance': -amount}}
                )
                
                if result.modified_count == 0:
                    flash('Error updating balance')
                    return redirect(url_for('withdraw'))
                
                # Record transaction
                mongo.db.transactions.insert_one({
                    'user_id': ObjectId(current_user.id),
                    'type': 'withdrawal',
                    'amount': amount,
                    'created_at': datetime.datetime.now()
                })
                
                flash(f'Successfully withdrew ₹{amount}')
                return redirect(url_for('customer_dashboard'))
            except Exception as e:
                flash(f'Error processing withdrawal: {str(e)}')
                return redirect(url_for('withdraw'))
        
        return render_template('account/withdraw.html', account=account)
    except Exception as e:
        flash(f'Error loading withdraw page: {str(e)}')
        return redirect(url_for('customer_dashboard'))

@app.route('/account/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    if not check_account_status():
        return redirect(url_for('customer_dashboard'))
        
    try:
        account = mongo.db.accounts.find_one({'user_id': ObjectId(current_user.id)})
        if not account:
            flash('Account not found')
            return redirect(url_for('customer_dashboard'))
            
        if request.method == 'POST':
            try:
                # Recheck status before processing transaction
                if not check_account_status():
                    return redirect(url_for('customer_dashboard'))
                    
                recipient_email = request.form.get('recipient')
                amount = float(request.form.get('amount', 0))
                password = request.form.get('password')
                
                if not password:
                    flash('Please enter your password to confirm the transaction')
                    return redirect(url_for('transfer'))
                
                # Verify password
                user = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
                if not user or not check_password_hash(user['password'], password):
                    flash('Invalid password')
                    return redirect(url_for('transfer'))
                
                if amount <= 0:
                    flash('Invalid amount')
                    return redirect(url_for('transfer'))
                
                # Find recipient by email
                recipient = mongo.db.users.find_one({'email': recipient_email})
                if not recipient:
                    # Try finding by username for backward compatibility
                    recipient = mongo.db.users.find_one({'username': recipient_email})
                
                if not recipient:
                    flash('Recipient not found')
                    return redirect(url_for('transfer'))
                
                # Check if recipient account is active
                if not recipient.get('is_active', True):
                    flash('Cannot transfer to a deactivated account')
                    return redirect(url_for('transfer'))
                
                if account['balance'] < amount:
                    flash('Insufficient balance')
                    return redirect(url_for('transfer'))
                
                # Update sender's balance
                sender_result = mongo.db.accounts.update_one(
                    {'user_id': ObjectId(current_user.id)},
                    {'$inc': {'balance': -amount}}
                )
                
                if sender_result.modified_count == 0:
                    flash('Error updating your balance')
                    return redirect(url_for('transfer'))
                
                # Update recipient's balance
                recipient_result = mongo.db.accounts.update_one(
                    {'user_id': ObjectId(recipient['_id'])},
                    {'$inc': {'balance': amount}}
                )
                
                if recipient_result.modified_count == 0:
                    # Rollback sender's transaction
                    mongo.db.accounts.update_one(
                        {'user_id': ObjectId(current_user.id)},
                        {'$inc': {'balance': amount}}
                    )
                    flash('Error updating recipient balance')
                    return redirect(url_for('transfer'))
                
                # Record transactions
                mongo.db.transactions.insert_one({
                    'user_id': ObjectId(current_user.id),
                    'type': 'transfer_out',
                    'amount': amount,
                    'recipient_id': ObjectId(recipient['_id']),
                    'created_at': datetime.datetime.now()
                })
                
                mongo.db.transactions.insert_one({
                    'user_id': ObjectId(recipient['_id']),
                    'type': 'transfer_in',
                    'amount': amount,
                    'sender_id': ObjectId(current_user.id),
                    'created_at': datetime.datetime.now()
                })
                
                flash(f'Successfully transferred ₹{amount} to {recipient.get("email") or recipient.get("username")}')
                return redirect(url_for('customer_dashboard'))
            except Exception as e:
                flash(f'Error processing transfer: {str(e)}')
                return redirect(url_for('transfer'))
        
        return render_template('account/transfer.html', account=account)
    except Exception as e:
        flash(f'Error loading transfer page: {str(e)}')
        return redirect(url_for('customer_dashboard'))

@app.route('/loan/apply', methods=['GET', 'POST'])
@login_required
def apply_loan():
    if not check_account_status():
        return redirect(url_for('customer_dashboard'))
        
    try:
        account = mongo.db.accounts.find_one({'user_id': ObjectId(current_user.id)})
        if not account:
            flash('Account not found')
            return redirect(url_for('customer_dashboard'))
            
        if request.method == 'POST':
            try:
                # Recheck status before processing loan application
                if not check_account_status():
                    return redirect(url_for('customer_dashboard'))
                    
                amount = float(request.form.get('amount', 0))
                purpose = request.form.get('purpose')
                
                if amount <= 0:
                    flash('Invalid amount')
                    return redirect(url_for('apply_loan'))
                
                if not purpose:
                    flash('Please specify the purpose of the loan')
                    return redirect(url_for('apply_loan'))
                
                # Create loan application
                mongo.db.loans.insert_one({
                    'user_id': ObjectId(current_user.id),
                    'amount': amount,
                    'purpose': purpose,
                    'status': 'pending',
                    'created_at': datetime.datetime.now()
                })
                
                flash('Loan application submitted successfully')
                return redirect(url_for('customer_dashboard'))
            except Exception as e:
                flash(f'Error submitting loan application: {str(e)}')
                return redirect(url_for('apply_loan'))
        
        return render_template('loan/apply.html', account=account)
    except Exception as e:
        flash(f'Error loading loan application page: {str(e)}')
        return redirect(url_for('customer_dashboard'))

@app.route('/admin/loans')
@login_required
def admin_loans():
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    # Get search parameters
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all')
    
    # Base query
    base_query = {}
    
    # Apply status filter
    if status_filter and status_filter != 'all':
        base_query['status'] = status_filter
    
    # Get current datetime for processing time calculations
    now = datetime.datetime.now()
    
    # Get all loans with filters
    loans = list(mongo.db.loans.find(base_query).sort('created_at', -1))
    
    # Get user information for each loan and apply search filter
    filtered_loans = []
    for loan in loans:
        user = mongo.db.users.find_one({'_id': loan['user_id']})
        if user:
            loan['username'] = user.get('username', 'Unknown')
            loan['email'] = user.get('email', 'Unknown')
        else:
            loan['username'] = 'Unknown'
            loan['email'] = 'Unknown'
            
        # Calculate processing time
        if loan.get('processed_at'):
            loan['processing_time'] = (loan['processed_at'] - loan['created_at']).days
        else:
            loan['processing_time'] = (now - loan['created_at']).days
            
        # Apply search filter
        if search_query:
            search_lower = search_query.lower()
            if (search_lower in loan['username'].lower() or 
                search_lower in loan.get('purpose', '').lower() or
                search_lower in loan['email'].lower() or
                search_lower in str(loan.get('amount', ''))):
                filtered_loans.append(loan)
        else:
            filtered_loans.append(loan)
    
    # Calculate loan statistics from filtered loans
    pending_loans = sum(1 for loan in filtered_loans if loan.get('status') == 'pending')
    approved_loans = sum(1 for loan in filtered_loans if loan.get('status') == 'approved')
    rejected_loans = sum(1 for loan in filtered_loans if loan.get('status') == 'rejected')
    
    # Calculate total amount for each status
    total_pending = sum(loan.get('amount', 0) for loan in filtered_loans if loan.get('status') == 'pending')
    total_approved = sum(loan.get('amount', 0) for loan in filtered_loans if loan.get('status') == 'approved')
    total_rejected = sum(loan.get('amount', 0) for loan in filtered_loans if loan.get('status') == 'rejected')
    
    return render_template('admin/loans.html', 
                         loans=filtered_loans,
                         pending_loans=pending_loans,
                         approved_loans=approved_loans,
                         rejected_loans=rejected_loans,
                         total_pending=total_pending,
                         total_approved=total_approved,
                         total_rejected=total_rejected,
                         now=now,
                         search_query=search_query,
                         status_filter=status_filter)

@app.route('/admin/approve_loan/<loan_id>')
@login_required
def approve_loan(loan_id):
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        # Convert string ID to ObjectId
        loan = mongo.db.loans.find_one({'_id': ObjectId(loan_id)})
        
        if not loan:
            flash('Loan not found')
            return redirect(url_for('admin_loans'))
        
        # Update loan status with processed timestamp
        mongo.db.loans.update_one(
            {'_id': ObjectId(loan_id)},
            {
                '$set': {
                    'status': 'approved',
                    'processed_at': datetime.datetime.now(),
                    'processed_by': ObjectId(current_user.id)
                }
            }
        )
        
        # Update user's account balance
        mongo.db.accounts.update_one(
            {'user_id': loan['user_id']},
            {'$inc': {'balance': loan['amount']}}
        )
        
        # Record transaction
        mongo.db.transactions.insert_one({
            'user_id': loan['user_id'],
            'type': 'loan_disbursement',
            'amount': loan['amount'],
            'loan_id': ObjectId(loan_id),
            'processed_by': ObjectId(current_user.id),
            'created_at': datetime.datetime.now()
        })
        
        flash('Loan approved and disbursed successfully')
    except Exception as e:
        flash(f'Error processing loan approval: {str(e)}')
    
    return redirect(url_for('admin_loans'))

@app.route('/admin/reject_loan/<loan_id>', methods=['POST'])
@login_required
def reject_loan(loan_id):
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        # Get rejection reason from form
        rejection_reason = request.form.get('rejection_reason')
        
        if not rejection_reason or rejection_reason.strip() == '':
            flash('Please provide a reason for rejection')
            return redirect(url_for('admin_loans'))
        
        # Convert string ID to ObjectId and find loan
        loan_id_obj = ObjectId(loan_id)
        loan = mongo.db.loans.find_one({'_id': loan_id_obj})
        
        if not loan:
            flash('Loan not found')
            return redirect(url_for('admin_loans'))
        
        if loan.get('status') != 'pending':
            flash('Only pending loans can be rejected')
            return redirect(url_for('admin_loans'))
        
        # Update loan status with processed timestamp and rejection reason
        result = mongo.db.loans.update_one(
            {'_id': loan_id_obj},
            {
                '$set': {
                    'status': 'rejected',
                    'rejection_reason': rejection_reason.strip(),
                    'processed_at': datetime.datetime.now(),
                    'processed_by': ObjectId(current_user.id)
                }
            }
        )
        
        if result.modified_count > 0:
            flash('Loan application has been rejected')
        else:
            flash('Error rejecting loan application')
            
    except Exception as e:
        print(f'Error in reject_loan: {str(e)}')
        flash(f'Error processing loan rejection: {str(e)}')
    
    return redirect(url_for('admin_loans'))

@app.route('/admin/employees')
@login_required
def admin_employees():
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        # Get all employees and convert cursor to list
        employees = list(mongo.db.users.find({'role': 'employee'}))
        
        # Add is_active field if not present
        for employee in employees:
            if 'is_active' not in employee:
                employee['is_active'] = True
        
        # Calculate statistics
        total_employees = len(employees)
        active_employees = sum(1 for emp in employees if emp.get('is_active', True))
        inactive_employees = total_employees - active_employees
        
        return render_template('admin/employees.html',
                             employees=employees,
                             active_employees=active_employees,
                             inactive_employees=inactive_employees)
    except Exception as e:
        print(f"Error in admin_employees: {str(e)}")
        flash(f'Error loading employees: {str(e)}')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_employee', methods=['GET', 'POST'])
@login_required
def add_employee():
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            email = request.form.get('email')
            
            # Validate input
            if not all([username, password, confirm_password, email]):
                flash('All fields are required')
                return redirect(url_for('add_employee'))
            
            # Check password match
            if password != confirm_password:
                flash('Passwords do not match')
                return redirect(url_for('add_employee'))
            
            # Check if username or email already exists
            if mongo.db.users.find_one({'$or': [{'username': username}, {'email': email}]}):
                flash('Username or email already exists')
                return redirect(url_for('add_employee'))
            
            # Create new employee
            employee_id = mongo.db.users.insert_one({
                'username': username,
                'password': generate_password_hash(password),
                'email': email,
                'role': 'employee',
                'is_active': True,
                'created_at': datetime.datetime.now()
            }).inserted_id
            
            flash('Employee added successfully')
            return redirect(url_for('admin_employees'))
        
        return render_template('admin/add_employee.html')
    
    except Exception as e:
        print(f"Error in add_employee: {str(e)}")
        flash(f'Error adding employee: {str(e)}')
        return redirect(url_for('admin_employees'))

@app.route('/admin/customer-report')
@login_required
def admin_customer_report():
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        # Get all customers with their account information
        customers = list(mongo.db.users.find({'role': 'customer'}))
        total_balance = 0
        
        # Process each customer's data
        for customer in customers:
            # Get account information
            account = mongo.db.accounts.find_one({'user_id': customer['_id']})
            if account:
                customer['account_number'] = account['account_number']
                customer['balance'] = account['balance']
                total_balance += account['balance']
            else:
                customer['account_number'] = 'N/A'
                customer['balance'] = 0
            
            # Ensure created_at exists and convert to registered_on
            if 'created_at' in customer:
                customer['registered_on'] = customer['created_at']
            else:
                customer['registered_on'] = datetime.datetime.now()
            
            # Ensure is_active exists
            if 'is_active' not in customer:
                customer['is_active'] = True
        
        # Calculate statistics
        active_customers = sum(1 for c in customers if c.get('is_active', True))
        inactive_customers = len(customers) - active_customers
        
        return render_template('admin/customer_report.html', 
                             customers=customers,
                             active_customers=active_customers,
                             inactive_customers=inactive_customers,
                             total_balance=total_balance)
                             
    except Exception as e:
        print(f"Error in admin_customer_report: {str(e)}")
        flash(f'Error loading customer report: {str(e)}')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/customer-search', methods=['GET', 'POST'])
@login_required
def customer_search():
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('customer_dashboard'))
        
    try:
        search_query = request.args.get('query', '').strip()
        search_results = []
        total_customers = 0
        
        if search_query:
            # Search by account number, username, or email
            customers = list(mongo.db.users.find({
                '$and': [
                    {'role': 'customer'},
                    {'$or': [
                        {'username': {'$regex': search_query, '$options': 'i'}},
                        {'email': {'$regex': search_query, '$options': 'i'}}
                    ]}
                ]
            }))
            
            # Get account details for each customer
            for customer in customers:
                account = mongo.db.accounts.find_one({'user_id': customer['_id']})
                if account:
                    # Get recent transactions
                    transactions = list(mongo.db.transactions.find(
                        {'user_id': customer['_id']}
                    ).sort('created_at', -1).limit(5))
                    
                    # Format dates
                    for transaction in transactions:
                        if isinstance(transaction.get('created_at'), datetime.datetime):
                            transaction['created_at_formatted'] = transaction['created_at'].strftime('%Y-%m-%d %H:%M')
                        else:
                            transaction['created_at_formatted'] = 'N/A'
                    
                    search_results.append({
                        'user': customer,
                        'account': account,
                        'transactions': transactions
                    })
        
        # Get total number of customers
        total_customers = mongo.db.users.count_documents({'role': 'customer'})
        
        return render_template('admin/customer_search.html',
                             search_query=search_query,
                             search_results=search_results,
                             total_customers=total_customers)
                             
    except Exception as e:
        flash(f'Error searching customers: {str(e)}')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/add-customer', methods=['GET', 'POST'])
@login_required
def add_customer():
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            initial_balance = float(request.form.get('initial_balance', 0))
            
            # Validate input
            if not all([username, email, password]):
                flash('All fields are required')
                return redirect(url_for('add_customer'))
            
            # Check if username or email already exists
            if mongo.db.users.find_one({'$or': [{'username': username}, {'email': email}]}):
                flash('Username or email already exists')
                return redirect(url_for('add_customer'))
            
            # Generate unique account number
            while True:
                account_number = generate_account_number()
                # Check if account number already exists
                if not mongo.db.accounts.find_one({'account_number': account_number}):
                    break
            
            # Create new user
            user_id = mongo.db.users.insert_one({
                'username': username,
                'email': email,
                'password': generate_password_hash(password),
                'role': 'customer',
                'created_at': datetime.datetime.now()
            }).inserted_id
            
            # Create account for the user
            mongo.db.accounts.insert_one({
                'user_id': user_id,
                'balance': initial_balance,
                'account_number': account_number,
                'created_at': datetime.datetime.now()
            })
            
            # Record initial deposit if balance > 0
            if initial_balance > 0:
                mongo.db.transactions.insert_one({
                    'user_id': user_id,
                    'type': 'deposit',
                    'amount': initial_balance,
                    'created_at': datetime.datetime.now()
                })
            
            flash('Customer added successfully')
            return redirect(url_for('admin_dashboard'))
            
        return render_template('admin/add_customer.html')
    except Exception as e:
        flash(f'Error adding customer: {str(e)}')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/customer-transactions/<customer_id>')
@login_required
def view_customer_transactions(customer_id):
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('index'))
    
    try:
        # Get customer information
        customer = mongo.db.users.find_one({'_id': ObjectId(customer_id)})
        if not customer:
            flash('Customer not found.')
            return redirect(url_for('admin_dashboard'))
        
        # Get customer's account
        account = mongo.db.accounts.find_one({'user_id': ObjectId(customer_id)})
        if not account:
            flash('Account not found for this customer.')
            return redirect(url_for('admin_dashboard'))
        
        # Get all transactions for this customer
        transactions = list(mongo.db.transactions.find({'user_id': ObjectId(customer_id)}).sort('created_at', -1))
        
        # Format transaction data
        for transaction in transactions:
            if 'created_at' in transaction:
                transaction['created_at_formatted'] = transaction['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            else:
                transaction['created_at_formatted'] = 'N/A'
            
            # Ensure transaction has a status field
            if 'status' not in transaction:
                transaction['status'] = 'completed'
        
        # Create debug information
        debug_info = {
            'customer_id': str(customer_id),
            'customer_found': customer is not None,
            'account_found': account is not None,
            'transaction_count': len(transactions),
            'customer_data': {
                'username': customer.get('username', 'N/A'),
                'email': customer.get('email', 'N/A'),
                'role': customer.get('role', 'N/A')
            },
            'account_data': {
                'account_number': account.get('account_number', 'N/A'),
                'balance': account.get('balance', 0)
            }
        }
        
        # Print debug information
        print(f"Customer ID: {customer_id}")
        print(f"Customer found: {customer is not None}")
        print(f"Account found: {account is not None}")
        print(f"Number of transactions: {len(transactions)}")
        
        return render_template('admin/customer_transactions.html', 
                              customer=customer, 
                              account=account, 
                              transactions=transactions,
                              debug=True,
                              debug_info=debug_info)
    
    except Exception as e:
        print(f"Error in view_customer_transactions: {str(e)}")
        flash(f'Error retrieving transactions: {str(e)}')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/employee/toggle-status/<employee_id>')
@login_required
def toggle_employee_status(employee_id):
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        # Find the employee
        employee = mongo.db.users.find_one({'_id': ObjectId(employee_id), 'role': 'employee'})
        if not employee:
            flash('Employee not found')
            return redirect(url_for('admin_employees'))
        
        # Toggle the active status
        current_status = employee.get('is_active', True)
        new_status = not current_status
        
        # Update the employee status
        mongo.db.users.update_one(
            {'_id': ObjectId(employee_id)},
            {'$set': {'is_active': new_status}}
        )
        
        status_text = 'activated' if new_status else 'suspended'
        flash(f'Employee {employee["username"]} has been {status_text}')
        
    except Exception as e:
        print(f"Error toggling employee status: {str(e)}")
        flash(f'Error updating employee status: {str(e)}')
    
    return redirect(url_for('admin_employees'))

@app.route('/admin/customer/<customer_id>/actions')
@login_required
def admin_customer_actions(customer_id):
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        # Get customer information
        customer = mongo.db.users.find_one({'_id': ObjectId(customer_id), 'role': 'customer'})
        if not customer:
            flash('Customer not found')
            return redirect(url_for('admin_dashboard'))
        
        # Get account information
        account = mongo.db.accounts.find_one({'user_id': ObjectId(customer_id)})
        if not account:
            flash('Account not found')
            return redirect(url_for('admin_dashboard'))
        
        # Get recent transactions
        transactions = list(mongo.db.transactions.find(
            {'user_id': ObjectId(customer_id)}
        ).sort('created_at', -1).limit(10))
        
        # Format transaction dates
        for transaction in transactions:
            if isinstance(transaction.get('created_at'), datetime.datetime):
                transaction['created_at_formatted'] = transaction['created_at'].strftime('%Y-%m-%d %H:%M')
            else:
                transaction['created_at_formatted'] = 'N/A'
        
        return render_template('admin/customer_actions.html',
                             customer=customer,
                             account=account,
                             transactions=transactions)
    
    except Exception as e:
        flash(f'Error loading customer actions: {str(e)}')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/customer/<customer_id>/deposit', methods=['POST'])
@login_required
def admin_deposit(customer_id):
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        amount = float(request.form.get('amount', 0))
        notes = request.form.get('notes', '')
        
        if amount <= 0:
            flash('Invalid amount')
            return redirect(url_for('admin_customer_actions', customer_id=customer_id))
        
        # Update account balance
        result = mongo.db.accounts.update_one(
            {'user_id': ObjectId(customer_id)},
            {'$inc': {'balance': amount}}
        )
        
        if result.modified_count == 0:
            flash('Error updating balance')
            return redirect(url_for('admin_customer_actions', customer_id=customer_id))
        
        # Record transaction
        mongo.db.transactions.insert_one({
            'user_id': ObjectId(customer_id),
            'type': 'deposit',
            'amount': amount,
            'notes': notes,
            'admin_id': ObjectId(current_user.id),
            'created_at': datetime.datetime.now()
        })
        
        flash(f'Successfully deposited ₹{amount}')
        
    except Exception as e:
        flash(f'Error processing deposit: {str(e)}')
    
    return redirect(url_for('admin_customer_actions', customer_id=customer_id))

@app.route('/admin/customer/<customer_id>/withdraw', methods=['POST'])
@login_required
def admin_withdraw(customer_id):
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        amount = float(request.form.get('amount', 0))
        notes = request.form.get('notes', '')
        
        if amount <= 0:
            flash('Invalid amount')
            return redirect(url_for('admin_customer_actions', customer_id=customer_id))
        
        # Check balance
        account = mongo.db.accounts.find_one({'user_id': ObjectId(customer_id)})
        if not account or account['balance'] < amount:
            flash('Insufficient balance')
            return redirect(url_for('admin_customer_actions', customer_id=customer_id))
        
        # Update account balance
        result = mongo.db.accounts.update_one(
            {'user_id': ObjectId(customer_id)},
            {'$inc': {'balance': -amount}}
        )
        
        if result.modified_count == 0:
            flash('Error updating balance')
            return redirect(url_for('admin_customer_actions', customer_id=customer_id))
        
        # Record transaction
        mongo.db.transactions.insert_one({
            'user_id': ObjectId(customer_id),
            'type': 'withdrawal',
            'amount': amount,
            'notes': notes,
            'admin_id': ObjectId(current_user.id),
            'created_at': datetime.datetime.now()
        })
        
        flash(f'Successfully withdrew ₹{amount}')
        
    except Exception as e:
        flash(f'Error processing withdrawal: {str(e)}')
    
    return redirect(url_for('admin_customer_actions', customer_id=customer_id))

@app.route('/admin/customer/<customer_id>/transfer', methods=['POST'])
@login_required
def admin_transfer(customer_id):
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        amount = float(request.form.get('amount', 0))
        recipient_email = request.form.get('recipient')
        notes = request.form.get('notes', '')
        
        if amount <= 0:
            flash('Invalid amount')
            return redirect(url_for('admin_customer_actions', customer_id=customer_id))
        
        # Find sender's account
        sender_account = mongo.db.accounts.find_one({'user_id': ObjectId(customer_id)})
        if not sender_account or sender_account['balance'] < amount:
            flash('Insufficient balance')
            return redirect(url_for('admin_customer_actions', customer_id=customer_id))
        
        # Find recipient
        recipient = mongo.db.users.find_one({'email': recipient_email})
        if not recipient:
            # Try finding by username
            recipient = mongo.db.users.find_one({'username': recipient_email})
        
        if not recipient:
            flash('Recipient not found')
            return redirect(url_for('admin_customer_actions', customer_id=customer_id))
        
        # Check if recipient account is active
        if not recipient.get('is_active', True):
            flash('Cannot transfer to a deactivated account')
            return redirect(url_for('admin_customer_actions', customer_id=customer_id))
        
        # Update sender's balance
        sender_result = mongo.db.accounts.update_one(
            {'user_id': ObjectId(customer_id)},
            {'$inc': {'balance': -amount}}
        )
        
        if sender_result.modified_count == 0:
            flash('Error updating sender balance')
            return redirect(url_for('admin_customer_actions', customer_id=customer_id))
        
        # Update recipient's balance
        recipient_result = mongo.db.accounts.update_one(
            {'user_id': recipient['_id']},
            {'$inc': {'balance': amount}}
        )
        
        if recipient_result.modified_count == 0:
            # Rollback sender's transaction
            mongo.db.accounts.update_one(
                {'user_id': ObjectId(customer_id)},
                {'$inc': {'balance': amount}}
            )
            flash('Error updating recipient balance')
            return redirect(url_for('admin_customer_actions', customer_id=customer_id))
        
        # Record transactions
        mongo.db.transactions.insert_one({
            'user_id': ObjectId(customer_id),
            'type': 'transfer_out',
            'amount': amount,
            'recipient_id': recipient['_id'],
            'notes': notes,
            'admin_id': ObjectId(current_user.id),
            'created_at': datetime.datetime.now()
        })
        
        mongo.db.transactions.insert_one({
            'user_id': recipient['_id'],
            'type': 'transfer_in',
            'amount': amount,
            'sender_id': ObjectId(customer_id),
            'notes': notes,
            'admin_id': ObjectId(current_user.id),
            'created_at': datetime.datetime.now()
        })
        
        flash(f'Successfully transferred ₹{amount} to {recipient.get("email") or recipient.get("username")}')
        
    except Exception as e:
        flash(f'Error processing transfer: {str(e)}')
    
    return redirect(url_for('admin_customer_actions', customer_id=customer_id))

@app.route('/admin/customer/<customer_id>/receipt')
@login_required
def generate_receipt(customer_id):
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        # Convert string ID to ObjectId
        customer_obj_id = ObjectId(customer_id)
        
        # Get customer information with explicit is_active field
        customer = mongo.db.users.find_one({
            '_id': customer_obj_id,
            'role': 'customer'
        })
        
        if not customer:
            flash('Customer not found')
            return redirect(url_for('admin_dashboard'))
        
        # Ensure is_active field exists
        if 'is_active' not in customer:
            customer['is_active'] = True  # Default to active if not set
        
        # Get account information
        account = mongo.db.accounts.find_one({'user_id': customer_obj_id})
        if not account:
            flash('Account not found')
            return redirect(url_for('admin_dashboard'))
        
        # Get recent transactions (last 30 days)
        thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)
        transactions = list(mongo.db.transactions.find({
            'user_id': customer_obj_id,
            'created_at': {'$gte': thirty_days_ago}
        }).sort('created_at', -1))
        
        return render_template('admin/receipt.html',
                             customer=customer,
                             account=account,
                             transactions=transactions,
                             generated_date=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    except Exception as e:
        print(f"Error generating receipt: {str(e)}")
        flash(f'Error generating receipt: {str(e)}')
        return redirect(url_for('admin_dashboard'))

@app.route('/loan/status')
@login_required
def loan_status():
    try:
        # Get all loans for the current user
        loans = list(mongo.db.loans.find({
            'user_id': ObjectId(current_user.id)
        }).sort('created_at', -1))
        
        # Calculate loan statistics
        pending_count = sum(1 for loan in loans if loan.get('status') == 'pending')
        approved_count = sum(1 for loan in loans if loan.get('status') == 'approved')
        rejected_count = sum(1 for loan in loans if loan.get('status') == 'rejected')
        
        # Add processing time information
        now = datetime.datetime.now()
        
        return render_template('customer/loan_status.html',
                             loans=loans,
                             pending_count=pending_count,
                             approved_count=approved_count,
                             rejected_count=rejected_count,
                             now=now)
    except Exception as e:
        flash(f'Error loading loan status: {str(e)}')
        return redirect(url_for('customer_dashboard'))

@app.route('/admin/loan/<loan_id>/details')
@login_required
def loan_details(loan_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Get loan details
        loan = mongo.db.loans.find_one({'_id': ObjectId(loan_id)})
        if not loan:
            return jsonify({'error': 'Loan not found'}), 404
            
        # Get customer details
        user = mongo.db.users.find_one({'_id': loan['user_id']})
        if not user:
            return jsonify({'error': 'Customer not found'}), 404
            
        # Get processor details if loan is processed
        processed_by_name = None
        if loan.get('processed_by'):
            processor = mongo.db.users.find_one({'_id': loan['processed_by']})
            if processor:
                processed_by_name = processor.get('username', 'Unknown')
        
        # Format dates properly
        created_at = loan.get('created_at')
        processed_at = loan.get('processed_at')
        
        # Calculate processing time
        if processed_at:
            processing_time = (processed_at - created_at).days
        else:
            processing_time = (datetime.datetime.now() - created_at).days
        
        # Prepare response data
        response_data = {
            'username': user.get('username', 'Unknown'),
            'email': user.get('email', 'Unknown'),
            'amount': float(loan.get('amount', 0)),
            'purpose': loan.get('purpose', 'Not specified'),
            'status': loan.get('status', 'pending'),
            'created_at': created_at.strftime('%Y-%m-%d %H:%M:%S') if created_at else None,
            'processed_at': processed_at.strftime('%Y-%m-%d %H:%M:%S') if processed_at else None,
            'processed_by_name': processed_by_name,
            'rejection_reason': loan.get('rejection_reason'),
            'processing_time': processing_time
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error fetching loan details: {str(e)}")
        return jsonify({'error': 'An error occurred'}), 500

@app.route('/admin/customer/<customer_id>/deactivate')
@login_required
def deactivate_customer(customer_id):
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        # Convert string ID to ObjectId
        customer_obj_id = ObjectId(customer_id)
        
        # Find the customer and check if they exist
        customer = mongo.db.users.find_one({
            '_id': customer_obj_id,
            'role': 'customer'
        })
        
        if not customer:
            flash('Customer not found')
            return redirect(url_for('admin_dashboard'))
        
        # Check if customer is already inactive
        if not customer.get('is_active', True):
            flash('Customer is already inactive')
            return redirect(url_for('admin_dashboard'))
        
        # Update customer status to inactive
        result = mongo.db.users.update_one(
            {
                '_id': customer_obj_id,
                'role': 'customer'  # Additional safety check
            },
            {
                '$set': {
                    'is_active': False,
                    'deactivated_at': datetime.datetime.now(),
                    'deactivated_by': ObjectId(current_user.id)
                }
            }
        )
        
        if result.matched_count == 0:
            flash('Customer not found or already deactivated')
            return redirect(url_for('admin_dashboard'))
            
        if result.modified_count > 0:
            # Log the deactivation
            mongo.db.activity_logs.insert_one({
                'action': 'customer_deactivated',
                'customer_id': customer_obj_id,
                'admin_id': ObjectId(current_user.id),
                'timestamp': datetime.datetime.now(),
                'customer_username': customer['username']
            })
            
            flash(f'Customer {customer["username"]} has been deactivated successfully')
        else:
            flash('No changes were made to customer status')
            
    except Exception as e:
        print(f"Error deactivating customer: {str(e)}")
        flash(f'Error deactivating customer: {str(e)}')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/customer/<customer_id>/activate')
@login_required
def activate_customer(customer_id):
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        # Convert string ID to ObjectId
        customer_obj_id = ObjectId(customer_id)
        
        # Find the customer and check if they exist
        customer = mongo.db.users.find_one({
            '_id': customer_obj_id,
            'role': 'customer'
        })
        
        if not customer:
            flash('Customer not found')
            return redirect(url_for('admin_dashboard'))
        
        # Check if customer is already active
        if customer.get('is_active', False):
            flash('Customer is already active')
            return redirect(url_for('admin_dashboard'))
        
        # Update customer status to active
        result = mongo.db.users.update_one(
            {
                '_id': customer_obj_id,
                'role': 'customer'  # Additional safety check
            },
            {
                '$set': {
                    'is_active': True,
                    'activated_at': datetime.datetime.now(),
                    'activated_by': ObjectId(current_user.id)
                },
                '$unset': {
                    'deactivated_at': "",
                    'deactivated_by': ""
                }
            }
        )
        
        if result.matched_count == 0:
            flash('Customer not found')
            return redirect(url_for('admin_dashboard'))
            
        if result.modified_count > 0:
            # Log the activation
            mongo.db.activity_logs.insert_one({
                'action': 'customer_activated',
                'customer_id': customer_obj_id,
                'admin_id': ObjectId(current_user.id),
                'timestamp': datetime.datetime.now(),
                'customer_username': customer['username']
            })
            
            flash(f'Customer {customer["username"]} has been activated successfully')
        else:
            flash('No changes were made to customer status')
            
    except Exception as e:
        print(f"Error activating customer: {str(e)}")
        flash(f'Error activating customer: {str(e)}')
        
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True) 