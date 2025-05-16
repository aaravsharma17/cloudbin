from flask import Flask, render_template, request, redirect, url_for, flash, session
from models import db, User, EwasteRequest, Voucher
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Create tables
with app.app_context():
    db.create_all()
    # Add sample vouchers if none exist
    if not Voucher.query.first():
        vouchers = [
            Voucher(name="Amazon ₹100", description="₹100 Amazon Gift Card", coins_required=100, code="AMAZON100"),
            Voucher(name="Amazon ₹250", description="₹250 Amazon Gift Card", coins_required=250, code="AMAZON250"),
            Voucher(name="Amazon ₹500", description="₹500 Amazon Gift Card", coins_required=500, code="AMAZON500"),
        ]
        db.session.add_all(vouchers)
        db.session.commit()
    
    # Create default admin if not exists
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@cloudbin.com', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            # Verify the selected role matches user's actual role
            if user.role != role:
                flash(f'Invalid credentials for {role} login', 'danger')
                return redirect(url_for('login'))
                
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash('Login successful!', 'success')
            
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        
        new_user = User(username=username, email=email, role='user')  # Default role is user
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/user/dashboard')
def user_dashboard():
    if 'user_id' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    requests = EwasteRequest.query.filter_by(user_id=user.id).all()
    return render_template('user_dashboard.html', user=user, requests=requests)

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    # Get pending requests with user information
    pending_requests = db.session.query(
        EwasteRequest,
        User.username
    ).join(
        User, EwasteRequest.user_id == User.id
    ).filter(
        EwasteRequest.status == 'pending'
    ).all()
    
    return render_template('admin_dashboard.html', requests=pending_requests)

@app.route('/submit-request', methods=['GET', 'POST'])
def submit_request():
    if 'user_id' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        waste_type = request.form['waste_type']
        quantity = int(request.form['quantity'])
        location = request.form['location']
        
        # Calculate coins (simple calculation - can be enhanced)
        coins = quantity * 10  # 10 coins per item
        
        new_request = EwasteRequest(
            user_id=session['user_id'],
            waste_type=waste_type,
            quantity=quantity,
            location=location,
            coins_awarded=coins
        )
        db.session.add(new_request)
        db.session.commit()
        
        flash('Request submitted successfully!', 'success')
        return redirect(url_for('user_dashboard'))
    
    return render_template('submit_request.html')

@app.route('/admin/approve/<int:request_id>')
def approve_request(request_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    ewaste_request = EwasteRequest.query.get(request_id)
    if ewaste_request:
        ewaste_request.status = 'approved'
        user = User.query.get(ewaste_request.user_id)
        user.ebin_coins += ewaste_request.coins_awarded
        db.session.commit()
        flash('Request approved and coins awarded!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject/<int:request_id>')
def reject_request(request_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    ewaste_request = EwasteRequest.query.get(request_id)
    if ewaste_request:
        ewaste_request.status = 'rejected'
        db.session.commit()
        flash('Request rejected!', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/vouchers')
def vouchers():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    available_vouchers = Voucher.query.filter(Voucher.stock > 0).all()
    return render_template('vouchers.html', user=user, vouchers=available_vouchers)

@app.route('/redeem/<int:voucher_id>')
def redeem_voucher(voucher_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    voucher = Voucher.query.get(voucher_id)
    
    if not voucher or voucher.stock <= 0:
        flash('Voucher not available', 'danger')
        return redirect(url_for('vouchers'))
    
    if user.ebin_coins < voucher.coins_required:
        flash('Not enough Ebin coins', 'danger')
        return redirect(url_for('vouchers'))
    
    user.ebin_coins -= voucher.coins_required
    voucher.stock -= 1
    db.session.commit()
    
    flash(f'Voucher redeemed! Code: {voucher.code}', 'success')
    return redirect(url_for('vouchers'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)