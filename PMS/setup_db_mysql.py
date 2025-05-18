import mysql.connector
from mysql.connector import Error

# Initialize conn and cursor as None
conn = None
cursor = None

try:
    # Attempt to connect to MySQL
    print("Attempting to connect to MySQL...")
    conn = mysql.connector.connect(
        host="localhost",
        user="root",          # Replace with your MySQL username
        password="Purple786@",          # Replace with your MySQL password
        database="pharmacy_management"  # Specify the existing database
    )
    cursor = conn.cursor()
    print("Connected successfully!")

    # Create tables (if they don’t exist)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Inventory (
            id INT PRIMARY KEY AUTO_INCREMENT,
            drug_name VARCHAR(100) NOT NULL,
            quantity INT NOT NULL,
            expiry_date DATE NOT NULL,
            price DECIMAL(10, 2) NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Prescriptions (
            id INT PRIMARY KEY AUTO_INCREMENT,
            patient_name VARCHAR(100) NOT NULL,
            drug_id INT NOT NULL,
            dosage VARCHAR(50) NOT NULL,
            date DATE NOT NULL,
            status ENUM('Pending', 'Filled', 'Cancelled') NOT NULL,
            FOREIGN KEY (drug_id) REFERENCES Inventory(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Billing (
            id INT PRIMARY KEY AUTO_INCREMENT,
            prescription_id INT NOT NULL,
            total_amount DECIMAL(10, 2) NOT NULL,
            payment_status ENUM('Pending', 'Paid', 'Failed') NOT NULL,
            date DATE NOT NULL,
            FOREIGN KEY (prescription_id) REFERENCES Prescriptions(id)
        )
    ''')

    # Insert sample data
    cursor.execute("INSERT IGNORE INTO Inventory (drug_name, quantity, expiry_date, price) VALUES (%s, %s, %s, %s)",
                   ('Paracetamol', 100, '2026-12-31', 0.50))
    cursor.execute("INSERT IGNORE INTO Inventory (drug_name, quantity, expiry_date, price) VALUES (%s, %s, %s, %s)",
                   ('Ibuprofen', 50, '2025-11-15', 0.75))
    cursor.execute("INSERT IGNORE INTO Prescriptions (patient_name, drug_id, dosage, date, status) VALUES (%s, %s, %s, %s, %s)",
                   ('John Doe', 1, '1 tablet daily', '2025-03-26', 'Pending'))
    cursor.execute("INSERT IGNORE INTO Billing (prescription_id, total_amount, payment_status, date) VALUES (%s, %s, %s, %s)",
                   (1, 5.00, 'Pending', '2025-03-26'))

    conn.commit()
    print("Tables created and sample data inserted successfully!")

    # Verify data
    cursor.execute("SELECT * FROM Inventory")
    print("Inventory:", cursor.fetchall())
    cursor.execute("SELECT * FROM Prescriptions")
    print("Prescriptions:", cursor.fetchall())
    cursor.execute("SELECT * FROM Billing")
    print("Billing:", cursor.fetchall())

except Error as e:
    print(f"Failed to connect to MySQL. Error: {e}")

finally:
    if 'cursor' in locals() and cursor is not None:
        cursor.close()
    if 'conn' in locals() and conn is not None and conn.is_connected():
        conn.close()
        print("MySQL connection closed.")
    else:
        print("No connection was established, nothing to close.")