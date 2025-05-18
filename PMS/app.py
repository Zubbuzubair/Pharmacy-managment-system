import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, send_file
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import csv
import io

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a secure random key

def get_db_connection():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",        # Replace with your MySQL username
        password="",          # Replace with your MySQL password
        database="pharmacy_management"
    )
    return conn

# Middleware to check if user is logged in
def login_required(f):
    def wrap(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash FROM Users WHERE username = %s", (username,))
        user = cursor.fetchone()
        conn.close()
        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT expiry_days, out_of_stock_threshold, low_stock_threshold FROM AlertSettings WHERE id = 1")
    settings = cursor.fetchone()
    expiry_days = settings[0] if settings else 30
    out_of_stock_threshold = settings[1] if settings else 0
    low_stock_threshold = settings[2] if settings else 10
    current_date = datetime.now().date()
    expiry_threshold = current_date + timedelta(days=expiry_days)
    cursor.execute("SELECT COUNT(*) FROM Inventory WHERE expiry_date < %s", (current_date,))
    expired_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Inventory WHERE expiry_date <= %s AND expiry_date >= %s",
                   (expiry_threshold, current_date))
    expiry_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Inventory WHERE quantity <= %s", (out_of_stock_threshold,))
    out_of_stock_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Inventory WHERE quantity <= %s AND quantity > %s",
                   (low_stock_threshold, out_of_stock_threshold))
    low_stock_count = cursor.fetchone()[0]
    cursor.execute("SELECT drug_name, quantity FROM Inventory")
    stock_data = cursor.fetchall()
    stock_labels = [item[0] for item in stock_data] if stock_data else []
    stock_quantities = [item[1] for item in stock_data] if stock_data else []
    cursor.execute("SELECT COUNT(*) FROM Inventory WHERE expiry_date > %s", (expiry_threshold,))
    non_expiring_count = cursor.fetchone()[0]
    expiring_data = [expired_count, expiry_count, non_expiring_count]
    expiring_labels = ["Expired", "Expiring Soon", "Non-Expiring"]
    cursor.execute("SELECT DATE_FORMAT(date, '%Y-%m') AS month, SUM(total_amount) AS total "
                   "FROM Billing GROUP BY DATE_FORMAT(date, '%Y-%m') ORDER BY month")
    billing_data = cursor.fetchall()
    billing_labels = [item[0] for item in billing_data] if billing_data else []
    billing_totals = [float(item[1]) for item in billing_data] if billing_data else []
    conn.close()
    return render_template('index.html', 
                         expired_count=expired_count,
                         expiry_count=expiry_count, 
                         out_of_stock_count=out_of_stock_count,
                         low_stock_count=low_stock_count,
                         stock_labels=stock_labels,
                         stock_quantities=stock_quantities,
                         expiring_labels=expiring_labels,
                         expiring_data=expiring_data,
                         billing_labels=billing_labels,
                         billing_totals=billing_totals)

@app.route('/expired_items')
@login_required
def expired_items():
    conn = get_db_connection()
    cursor = conn.cursor()
    current_date = datetime.now().date()
    cursor.execute("SELECT * FROM Inventory WHERE expiry_date < %s", (current_date,))
    expired_items = cursor.fetchall()
    conn.close()
    return render_template('expired_items.html', expired_items=expired_items)

@app.route('/expiring_soon_items')
@login_required
def expiring_soon_items():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT expiry_days FROM AlertSettings WHERE id = 1")
    settings = cursor.fetchone()
    expiry_days = settings[0] if settings else 30
    current_date = datetime.now().date()
    expiry_threshold = current_date + timedelta(days=expiry_days)
    cursor.execute("SELECT * FROM Inventory WHERE expiry_date <= %s AND expiry_date >= %s",
                   (expiry_threshold, current_date))
    expiring_items = cursor.fetchall()
    conn.close()
    return render_template('expiring_soon_items.html', expiring_items=expiring_items)

@app.route('/out_of_stock_items')
@login_required
def out_of_stock_items():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT out_of_stock_threshold FROM AlertSettings WHERE id = 1")
    settings = cursor.fetchone()
    out_of_stock_threshold = settings[0] if settings else 0
    cursor.execute("SELECT * FROM Inventory WHERE quantity <= %s", (out_of_stock_threshold,))
    out_of_stock_items = cursor.fetchall()
    conn.close()
    return render_template('out_of_stock_items.html', out_of_stock_items=out_of_stock_items)

@app.route('/low_stock_items')
@login_required
def low_stock_items():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT out_of_stock_threshold, low_stock_threshold FROM AlertSettings WHERE id = 1")
    settings = cursor.fetchone()
    out_of_stock_threshold = settings[0] if settings else 0
    low_stock_threshold = settings[1] if settings else 10
    cursor.execute("SELECT * FROM Inventory WHERE quantity <= %s AND quantity > %s",
                   (low_stock_threshold, out_of_stock_threshold))
    low_stock_items = cursor.fetchall()
    conn.close()
    return render_template('low_stock_items.html', low_stock_items=low_stock_items)

@app.route('/set_alerts', methods=['GET', 'POST'])
@login_required
def set_alerts():
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        expiry_days = int(request.form['expiry_days'])
        out_of_stock_threshold = int(request.form['out_of_stock_threshold'])
        low_stock_threshold = int(request.form['low_stock_threshold'])
        cursor.execute("UPDATE AlertSettings SET expiry_days = %s, out_of_stock_threshold = %s, low_stock_threshold = %s WHERE id = 1",
                       (expiry_days, out_of_stock_threshold, low_stock_threshold))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    cursor.execute("SELECT expiry_days, out_of_stock_threshold, low_stock_threshold FROM AlertSettings WHERE id = 1")
    settings = cursor.fetchone()
    expiry_days = settings[0] if settings else 30
    out_of_stock_threshold = settings[1] if settings else 0
    low_stock_threshold = settings[2] if settings else 10
    conn.close()
    return render_template('set_alerts.html', 
                         expiry_days=expiry_days, 
                         out_of_stock_threshold=out_of_stock_threshold,
                         low_stock_threshold=low_stock_threshold)

@app.route('/inventory')
@login_required
def inventory():
    conn = get_db_connection()
    cursor = conn.cursor()
    search_query = request.args.get('q', '').strip()
    if search_query:
        cursor.execute("SELECT * FROM Inventory WHERE drug_name LIKE %s", (f"%{search_query}%",))
    else:
        cursor.execute("SELECT * FROM Inventory")
    inventory_data = cursor.fetchall()
    conn.close()
    return render_template('inventory.html', inventory=inventory_data, search_query=search_query)

@app.route('/export_inventory')
@login_required
def export_inventory():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Inventory")
    inventory_data = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Drug Name', 'Quantity', 'Expiry Date', 'Price'])
    for row in inventory_data:
        writer.writerow(row)

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=inventory_export.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

@app.route('/edit_inventory/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_inventory(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        drug_name = request.form['drug_name']
        quantity = int(request.form['quantity'])
        expiry_date = request.form['expiry_date']
        price = float(request.form['price'])
        cursor.execute("UPDATE Inventory SET drug_name = %s, quantity = %s, expiry_date = %s, price = %s WHERE id = %s",
                       (drug_name, quantity, expiry_date, price, id))
        conn.commit()
        conn.close()
        return redirect(url_for('inventory'))
    cursor.execute("SELECT * FROM Inventory WHERE id = %s", (id,))
    item = cursor.fetchone()
    conn.close()
    return render_template('edit_inventory.html', item=item)

@app.route('/delete_inventory/<int:id>')
@login_required
def delete_inventory(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Inventory WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('inventory'))

@app.route('/prescriptions')
@login_required
def prescriptions():
    conn = get_db_connection()
    cursor = conn.cursor()
    search_query = request.args.get('q', '').strip()
    if search_query:
        cursor.execute("SELECT p.id, p.patient_name, i.drug_name, p.dosage_quantity, p.dosage_instructions, p.date, p.status "
                       "FROM Prescriptions p JOIN Inventory i ON p.drug_id = i.id "
                       "WHERE p.patient_name LIKE %s OR i.drug_name LIKE %s",
                       (f"%{search_query}%", f"%{search_query}%"))
    else:
        cursor.execute("SELECT p.id, p.patient_name, i.drug_name, p.dosage_quantity, p.dosage_instructions, p.date, p.status "
                       "FROM Prescriptions p JOIN Inventory i ON p.drug_id = i.id")
    prescriptions_data = cursor.fetchall()
    conn.close()
    return render_template('prescriptions.html', prescriptions=prescriptions_data, search_query=search_query)

@app.route('/export_prescriptions')
@login_required
def export_prescriptions():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT p.id, p.patient_name, i.drug_name, p.dosage_quantity, p.dosage_instructions, p.date, p.status "
                   "FROM Prescriptions p JOIN Inventory i ON p.drug_id = i.id")
    prescriptions_data = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Patient Name', 'Drug Name', 'Dosage Quantity', 'Dosage Instructions', 'Date', 'Status'])
    for row in prescriptions_data:
        writer.writerow(row)

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=prescriptions_export.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

@app.route('/edit_prescription/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_prescription(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        patient_name = request.form['patient_name']
        drug_id = int(request.form['drug_id'])
        dosage_quantity = int(request.form['dosage_quantity'])
        dosage_instructions = request.form['dosage_instructions']
        date = request.form['date']
        status = request.form['status']
        cursor.execute("UPDATE Prescriptions SET patient_name = %s, drug_id = %s, dosage_quantity = %s, dosage_instructions = %s, date = %s, status = %s WHERE id = %s",
                       (patient_name, drug_id, dosage_quantity, dosage_instructions, date, status, id))
        conn.commit()
        conn.close()
        return redirect(url_for('prescriptions'))
    cursor.execute("SELECT * FROM Prescriptions WHERE id = %s", (id,))
    prescription = cursor.fetchone()
    cursor.execute("SELECT id, drug_name FROM Inventory")
    drugs = cursor.fetchall()
    conn.close()
    return render_template('edit_prescription.html', prescription=prescription, drugs=drugs)

@app.route('/delete_prescription/<int:id>')
@login_required
def delete_prescription(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Prescriptions WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('prescriptions'))

@app.route('/billing')
@login_required
def billing():
    conn = get_db_connection()
    cursor = conn.cursor()
    search_query = request.args.get('q', '').strip()
    if search_query:
        cursor.execute("SELECT b.id, p.patient_name, b.total_amount, b.payment_status, b.date "
                       "FROM Billing b JOIN Prescriptions p ON b.prescription_id = p.id "
                       "WHERE p.patient_name LIKE %s",
                       (f"%{search_query}%",))
    else:
        cursor.execute("SELECT b.id, p.patient_name, b.total_amount, b.payment_status, b.date "
                       "FROM Billing b JOIN Prescriptions p ON b.prescription_id = p.id")
    billing_data = cursor.fetchall()
    conn.close()
    return render_template('billing.html', billing=billing_data, search_query=search_query)

@app.route('/export_billing')
@login_required
def export_billing():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT b.id, p.patient_name, b.total_amount, b.payment_status, b.date "
                   "FROM Billing b JOIN Prescriptions p ON b.prescription_id = p.id")
    billing_data = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Patient Name', 'Total Amount', 'Payment Status', 'Date'])
    for row in billing_data:
        writer.writerow(row)

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=billing_export.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

@app.route('/edit_billing/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_billing(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        prescription_id = int(request.form['prescription_id'])
        total_amount = float(request.form['total_amount'])
        payment_status = request.form['payment_status']
        date = request.form['date']
        cursor.execute("SELECT prescription_id FROM Billing WHERE id = %s", (id,))
        old_prescription_id = cursor.fetchone()[0]
        if old_prescription_id != prescription_id:
            cursor.execute("SELECT drug_id, dosage_quantity FROM Prescriptions WHERE id = %s", (old_prescription_id,))
            old_pres = cursor.fetchone()
            if old_pres:
                old_drug_id, old_dosage_quantity = old_pres
                cursor.execute("UPDATE Inventory SET quantity = quantity + %s WHERE id = %s", (old_dosage_quantity, old_drug_id))
        cursor.execute("SELECT drug_id, dosage_quantity FROM Prescriptions WHERE id = %s", (prescription_id,))
        pres = cursor.fetchone()
        if pres:
            drug_id, dosage_quantity = pres
            cursor.execute("SELECT quantity FROM Inventory WHERE id = %s", (drug_id,))
            current_quantity = cursor.fetchone()[0]
            if current_quantity >= dosage_quantity:
                cursor.execute("UPDATE Inventory SET quantity = quantity - %s WHERE id = %s", (dosage_quantity, drug_id))
                cursor.execute("UPDATE Billing SET prescription_id = %s, total_amount = %s, payment_status = %s, date = %s WHERE id = %s",
                               (prescription_id, total_amount, payment_status, date, id))
                conn.commit()
            else:
                conn.rollback()
                conn.close()
                return "Error: Insufficient stock for this prescription.", 400
        else:
            conn.close()
            return "Error: Prescription not found.", 400
        conn.close()
        return redirect(url_for('billing'))
    cursor.execute("SELECT * FROM Billing WHERE id = %s", (id,))
    bill = cursor.fetchone()
    cursor.execute("SELECT id, patient_name FROM Prescriptions")
    prescriptions = cursor.fetchall()
    conn.close()
    return render_template('edit_billing.html', bill=bill, prescriptions=prescriptions)

@app.route('/delete_billing/<int:id>')
@login_required
def delete_billing(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT prescription_id FROM Billing WHERE id = %s", (id,))
    prescription_id = cursor.fetchone()[0]
    cursor.execute("SELECT drug_id, dosage_quantity FROM Prescriptions WHERE id = %s", (prescription_id,))
    pres = cursor.fetchone()
    if pres:
        drug_id, dosage_quantity = pres
        cursor.execute("UPDATE Inventory SET quantity = quantity + %s WHERE id = %s", (dosage_quantity, drug_id))
    cursor.execute("DELETE FROM Billing WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('billing'))

@app.route('/add_inventory', methods=['GET', 'POST'])
@login_required
def add_inventory():
    if request.method == 'POST':
        drug_name = request.form['drug_name']
        quantity = request.form['quantity']
        expiry_date = request.form['expiry_date']
        price = request.form['price']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Inventory (drug_name, quantity, expiry_date, price) "
                       "VALUES (%s, %s, %s, %s)",
                       (drug_name, quantity, expiry_date, price))
        conn.commit()
        conn.close()
        return redirect(url_for('inventory'))
    return render_template('add_inventory.html')

@app.route('/add_prescription', methods=['GET', 'POST'])
@login_required
def add_prescription():
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        patient_name = request.form['patient_name']
        drug_id = int(request.form['drug_id'])
        dosage_quantity = int(request.form['dosage_quantity'])
        dosage_instructions = request.form['dosage_instructions']
        date = request.form['date']
        status = request.form['status']
        cursor.execute("INSERT INTO Prescriptions (patient_name, drug_id, dosage_quantity, dosage_instructions, date, status) "
                       "VALUES (%s, %s, %s, %s, %s, %s)",
                       (patient_name, drug_id, dosage_quantity, dosage_instructions, date, status))
        conn.commit()
        conn.close()
        return redirect(url_for('prescriptions'))
    cursor.execute("SELECT id, drug_name FROM Inventory")
    drugs = cursor.fetchall()
    conn.close()
    return render_template('add_prescription.html', drugs=drugs)

@app.route('/add_billing', methods=['GET', 'POST'])
@login_required
def add_billing():
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        prescription_id = int(request.form['prescription_id'])
        total_amount = float(request.form['total_amount'])
        payment_status = request.form['payment_status']
        date = request.form['date']
        cursor.execute("SELECT drug_id, dosage_quantity FROM Prescriptions WHERE id = %s", (prescription_id,))
        pres = cursor.fetchone()
        if pres:
            drug_id, dosage_quantity = pres
            cursor.execute("SELECT quantity FROM Inventory WHERE id = %s", (drug_id,))
            current_quantity = cursor.fetchone()[0]
            if current_quantity >= dosage_quantity:
                cursor.execute("UPDATE Inventory SET quantity = quantity - %s WHERE id = %s", (dosage_quantity, drug_id))
                cursor.execute("INSERT INTO Billing (prescription_id, total_amount, payment_status, date) "
                               "VALUES (%s, %s, %s, %s)",
                               (prescription_id, total_amount, payment_status, date))
                conn.commit()
            else:
                conn.rollback()
                conn.close()
                return "Error: Insufficient stock for this prescription.", 400
        else:
            conn.close()
            return "Error: Prescription not found.", 400
        conn.close()
        return redirect(url_for('billing'))
    cursor.execute("SELECT id, patient_name FROM Prescriptions")
    prescriptions = cursor.fetchall()
    conn.close()
    return render_template('add_billing.html', prescriptions=prescriptions)

@app.route('/init_user')
def init_user():
    conn = get_db_connection()
    cursor = conn.cursor()
    password = "admin123"  # Default password for the 'admin' user
    password_hash = generate_password_hash(password)
    cursor.execute("UPDATE Users SET password_hash = %s WHERE username = 'admin'", (password_hash,))
    conn.commit()
    conn.close()
    return "Default user initialized. Username: admin, Password: admin123"

if __name__ == '__main__':
    app.run(debug=True)
