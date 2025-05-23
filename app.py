# Import necessary modules
import os  # Provides functions for interacting with the operating system
import random  # Used for generating random numbers (though not used in the script yet)
import hashlib  # Used for hashing passwords securely
import pyodbc  # For connecting to SQL Server databases
from flask import Flask, stream_template, redirect, url_for, request, session, make_response  # Flask web framework and utilities

# Initialize Flask application
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Secret key for session management

# Set cache timeout for static files
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # One year in seconds

# Define directory for storing book cover images
IMG_DIR = os.path.join(app.static_folder, 'imgs')  # Path to images in static folder

# Global connection pool to the database
connection_pool = None

# Initialize the connection pool for database connections
def init_connection_pool():
    global connection_pool
    try:
        # Define connection string for SQL Server
        connection_string = (
            'DRIVER={SQL Server};'
            'SERVER=(local);'
            'DATABASE=mybookdb;'
            'Trusted_Connection=yes;'
        )
        # Establish connection
        connection_pool = pyodbc.connect(connection_string)
    except Exception as e:
        # On failure, set connection pool to None
        connection_pool = None

# Retrieve an active database connection
def get_db_connection():
    global connection_pool

    # Reinitialize connection pool if it doesn't exist
    if connection_pool is None:
        init_connection_pool()

    try:
        # Test the connection
        cursor = connection_pool.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
    except Exception as e:
        # Reconnect if connection is lost
        print(f"Connection lost, reconnecting: {e}")
        init_connection_pool()

    return connection_pool

# Route to register a new user
@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None  # Variable to store error messages
    if request.method == 'POST':
        # Get and sanitize username and hash password
        username = request.form['username'].strip()
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if username already exists
        cur.execute('SELECT COUNT(*) FROM users WHERE username = ?', (username,))
        if cur.fetchone()[0] > 0:
            conn.close()
            error = f"'{username}' is already taken. Please choose a different username."
            return stream_template('register.html', error=error)

        # Determine if the new user is the first and should be admin
        cur.execute('SELECT COUNT(*) FROM users')
        is_admin = (cur.fetchone()[0] == 0)

        # Insert new user into the database
        cur.execute(
            'INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)',
            (username, password, is_admin)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('login'))  # Redirect to login page after registration
    return stream_template('register.html', error=error)  # Show registration page

# Route to handle user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get and sanitize user input and hash the password
        username = request.form['username'].strip()
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        conn = get_db_connection()
        cur = conn.cursor()

        # Verify credentials
        cur.execute(
            'SELECT id, is_admin FROM users WHERE username = ? AND password = ?',
            (username, password)
        )
        user = cur.fetchone()
        conn.close()

        if user:
            # Set session variables for logged-in user
            session['user_id'] = user[0]
            session['is_admin'] = bool(user[1])
            session['username'] = username
            return redirect(url_for('home'))  # Redirect to home on successful login
    return stream_template('login.html')  # Show login page

# Route to log out the user
@app.route('/logout')
def logout():
    session.clear()  # Clear all session data
    return redirect(url_for('home'))  # Redirect to home page

# Route for home page
@app.route('/')
def home():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM books')  # Get all books from database
    raw = cur.fetchall()
    conn.close()
    books = []
    for b in raw:
        cover = b[4]  # Extract cover image
        books.append((b[0], b[1], b[2], b[3], cover))

    return stream_template('index.html', books=books)  # Show books on home page

# Route to add book to cart
@app.route('/add_to_cart/<int:book_id>')
def add_to_cart(book_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if user not logged in
    conn = get_db_connection()
    cur = conn.cursor()
    # Insert selected book into user's cart
    cur.execute('INSERT INTO cart (user_id, book_id) VALUES (?, ?)',
                (session['user_id'], book_id))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))  # Redirect back to home

# Route to view cart
@app.route('/cart')
def cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect if not logged in
    conn = get_db_connection()
    cur = conn.cursor()
    # Retrieve books in the cart for the logged-in user
    cur.execute(
        'SELECT b.id, b.title, b.author, b.price, b.cover_url '
        'FROM cart c JOIN books b ON c.book_id=b.id WHERE c.user_id=?',
        (session['user_id'],)
    )
    raw = cur.fetchall()
    conn.close()
    items = []
    for i in raw:
        cover = i[4]  # Get cover URL
        items.append((i[0], i[1], i[2], i[3], cover))
    total = sum(x[3] for x in items)  # Calculate total price
    return stream_template('cart.html', cart_items=items, total_price=total)  # Show cart

# Route to clear the cart
@app.route('/clear_cart')
def clear_cart():
    if 'user_id' in session:
        conn = get_db_connection()
        cur = conn.cursor()
        # Remove all items from user's cart
        cur.execute('DELETE FROM cart WHERE user_id=?', (session['user_id'],))
        conn.commit()
        conn.close()
    return redirect(url_for('cart'))  # Redirect to cart

# Route to show checkout page
@app.route('/checkout')
def checkout():
    conn = get_db_connection()
    cur = conn.cursor()
    # Retrieve cart items for current user
    cur.execute(
        'SELECT b.id, b.title, b.author, b.price, b.cover_url '
        'FROM cart c JOIN books b ON c.book_id=b.id WHERE c.user_id=?',
        (session['user_id'],)
    )
    raw = cur.fetchall()

    if not raw:
        conn.close()
        return redirect(url_for('cart'))  # Redirect if cart is empty

    items = []
    for i in raw:
        cover = i[4]  # Extract cover URL
        items.append((i[0], i[1], i[2], i[3], cover))

    total = sum(x[3] for x in items)  # Calculate total price

    conn.close()
    return stream_template('checkout.html', cart_items=items, total_price=total)  # Show checkout page

# Route to place the order
@app.route('/place_order')
def place_order():
    conn = get_db_connection()
    cur = conn.cursor()

    # Calculate total order amount
    cur.execute(
        'SELECT SUM(b.price) FROM cart c JOIN books b ON c.book_id=b.id WHERE c.user_id=?',
        (session['user_id'],)
    )
    total = cur.fetchone()[0]

    if not total:
        conn.close()
        return redirect(url_for('cart'))  # Redirect if no items in cart

    # Insert new order record
    cur.execute(
        'INSERT INTO orders (user_id, total_amount, status) VALUES (?, ?, ?)',
        (session['user_id'], total, 'pending')
    )
    conn.commit()

    # Get new order ID
    cur.execute('SELECT @@IDENTITY')
    order_id = cur.fetchone()[0]

    # Insert each cart item into order_items table
    cur.execute(
        'INSERT INTO order_items (order_id, book_id, quantity, price) '
        'SELECT ?, c.book_id, 1, b.price FROM cart c JOIN books b ON c.book_id=b.id WHERE c.user_id=?',
        (order_id, session['user_id'])
    )

    # Clear user's cart after placing the order
    cur.execute('DELETE FROM cart WHERE user_id=?', (session['user_id'],))

    conn.commit()
    conn.close()

    return redirect(url_for('order_confirmation', order_id=order_id))  # Show confirmation

# Route to view order confirmation
@app.route('/order_confirmation/<int:order_id>')
def order_confirmation(order_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Retrieve order details
    cur.execute(
        'SELECT id, order_date, total_amount, status FROM orders WHERE id=? AND user_id=?',
        (order_id, session['user_id'])
    )
    order = cur.fetchone()

    if not order:
        conn.close()
        return redirect(url_for('orders'))  # Redirect if order not found

    # Retrieve order items
    cur.execute(
        'SELECT oi.id, b.title, b.author, oi.quantity, oi.price, b.cover_url '
        'FROM order_items oi JOIN books b ON oi.book_id=b.id WHERE oi.order_id=?',
        (order_id,)
    )
    raw = cur.fetchall()

    items = []
    for i in raw:
        cover = i[5]  # Get book cover URL
        items.append((i[0], i[1], i[2], i[3], i[4], cover))

    conn.close()

    return stream_template('order_confirmation.html', order=order, order_items=items)  # Show confirmation

# Route to view all user orders
@app.route('/orders')
def orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect if not logged in

    conn = get_db_connection()
    cur = conn.cursor()

    # Retrieve all orders by user, most recent first
    cur.execute(
        'SELECT id, order_date, total_amount, status FROM orders WHERE user_id=? ORDER BY order_date DESC',
        (session['user_id'],)
    )
    orders = cur.fetchall()

    conn.close()

    return stream_template('orders.html', orders=orders)  # Show user's orders

# ... admin_panel and rest of the code continues