from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secure_secret_key_here' # Needed for session management

def get_db_connection():
    conn = sqlite3.connect('university_social.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                university TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                university TEXT NOT NULL,
                content TEXT NOT NULL,
                post_time TEXT NOT NULL,
                like_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                FOREIGN KEY (post_id) REFERENCES posts (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
    conn.close()

init_db()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    # Students view posts specific to their university (addressing safety/cross-university concerns)
    user_uni = session['university']
    posts = conn.execute('''
        SELECT posts.*, users.username 
        FROM posts 
        JOIN users ON posts.user_id = users.id 
        WHERE posts.university = ? 
        ORDER BY posts.id DESC
    ''', (user_uni,)).fetchall()
    conn.close()
    
    return render_template('index.html', posts=posts, university=user_uni)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        university = request.form['university']
        
        conn = get_db_connection()
        try:
            with conn:
                conn.execute('INSERT INTO users (username, password, university) VALUES (?, ?, ?)',
                             (username, password, university))
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists.', 'danger')
        finally:
            conn.close()
            
    return render_template('auth.html', mode='register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', 
                            (username, password)).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['university'] = user['university']
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
            
    return render_template('auth.html', mode='login')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/create-post', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    content = request.form['content']
    post_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    with conn:
        conn.execute('INSERT INTO posts (user_id, university, content, post_time) VALUES (?, ?, ?, ?)',
                     (session['user_id'], session['university'], content, post_time))
    conn.close()
    return redirect(url_for('index'))

@app.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    with conn:
        conn.execute('UPDATE posts SET like_count = like_count + 1 WHERE id = ?', (post_id,))
    conn.close()
    return redirect(url_for('index'))

@app.route('/report/<int:post_id>', methods=['POST'])
def report_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    reason = request.form.get('reason', 'Inappropriate content')
    conn = get_db_connection()
    with conn:
        conn.execute('INSERT INTO reports (post_id, user_id, reason) VALUES (?, ?, ?)',
                     (post_id, session['user_id'], reason))
    conn.close()
    flash('Post has been reported to administrators.', 'warning')
    return redirect(url_for('index'))

@app.route('/reports-dashboard')
def reports_dashboard():
    # Fulfills the project requirement to generate required reports
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    user_credentials = conn.execute('SELECT username, password, university FROM users').fetchall()
    board_summary = conn.execute('''
        SELECT university, COUNT(posts.id) as post_count, SUM(like_count) as total_likes 
        FROM posts GROUP BY university
    ''').fetchall()
    all_reports = conn.execute('''
        SELECT reports.id, posts.content, users.username as reporter, reports.reason 
        FROM reports 
        JOIN posts ON reports.post_id = posts.id 
        JOIN users ON reports.user_id = users.id
    ''').fetchall()
    conn.close()
    
    return render_template('reports.html', 
                           user_credentials=user_credentials, 
                           board_summary=board_summary, 
                           all_reports=all_reports)

if __name__ == '__main__':
    app.run(debug=True)