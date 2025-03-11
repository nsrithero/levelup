from flask_mysqldb import MySQL
import MySQLdb.cursors
from flask import flash, Flask, render_template, request, redirect, session, url_for,jsonify
from flask_session import Session  # Import Flask-Session
from datetime import datetime, timedelta

app = Flask(__name__)

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'  # Change if needed
app.config['MYSQL_PASSWORD'] = ''  # Add your MySQL password
app.config['MYSQL_DB'] = 'levelup'

mysql = MySQL(app)

# Session Configuration
# app.secret_key = 'your_secret_key'
# app.config['SESSION_TYPE'] = 'filesystem'

# ✅ Add SECRET_KEY to Fix the Error
app.config['SECRET_KEY'] = 'your_very_secret_key_here'  # Replace with a strong key



# ✅ Configure Flask-Session for Persistent Session
app.config['SESSION_TYPE'] = 'filesystem'  # Store sessions on the server
app.config['SESSION_PERMANENT'] = True  # Keep session until logout
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)  # Set a long expiration (1 year)
app.config['SESSION_FILE_DIR'] = './flask_sessions/'  # Directory for storing session files
app.config['SESSION_USE_SIGNER'] = True  # Prevent tampering with session cookies
app.config['SESSION_KEY_PREFIX'] = 'levelup_'  # Prefix for session keys

Session(app)  # Initialize Flask-Session



# Function to Create Database & Table if Not Exists
def create_database_and_table():
    connection = MySQLdb.connect(
        host="localhost",
        user="root",
        password=""  # Add your MySQL password if required
    )
    cursor = connection.cursor()

    # Create Database if not exists
    cursor.execute("CREATE DATABASE IF NOT EXISTS levelup")
    cursor.execute("USE levelup")

    # Create Guilds Table First
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guilds (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            guild_name VARCHAR(255) UNIQUE NOT NULL,
            leader_id BIGINT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Create quest history Table First
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quest_history (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            completed_tasks TEXT NOT NULL,
            date_completed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

    """)

    # Create Users Table After Guilds
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            rank CHAR(1) DEFAULT 'E',
            hp VARCHAR(255) DEFAULT '100',
            mp VARCHAR(255) DEFAULT '100',
            exp_own VARCHAR(255) DEFAULT '0',
            exp_target VARCHAR(255) DEFAULT '810',
            guild_id BIGINT DEFAULT NULL,
            FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE SET NULL
        ) AUTO_INCREMENT = 1000000001;
    """)

    connection.commit()
    cursor.close()
    connection.close()

# Run the function to create DB & Table on startup
create_database_and_table()


@app.route('/')
def home():
    if 'email' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE username = %s", (session['username'],))
        user = cursor.fetchone()
        cursor.close()

        if user:
            rank = user['rank']

            # if rank in ['E', 'D', 'C']:
            #     user_image = 'static/assets/profile/blue/img.png'
            # elif rank in ['B', 'A']:
            #     user_image = 'static/assets/profile/purple/img.jpeg'
            # elif rank == 'S':
            #     user_image = 'static/assets/profile/red/img.jpg'
            # else:
            #     user_image = 'static/assets/profile/blue/img.png'

            # print("User Image Path:", user_image)  # Debugging Line

            return render_template('home.html', user=user)

    return render_template('index.html', error="Please log in first!")

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    if not username or not password:
        return render_template('index.html', error="All fields are required!")

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    user = cursor.fetchone()
    cursor.close()

    if user:
        session.permanent = True  # ✅ Keep session active until logout
        session['user_id'] = user['id']
        session['email'] = user['email']
        session['username'] = user['username']
        session['rank'] = user['rank']

        return render_template('home.html', user=user)
    else:
        return render_template('index.html', error="Invalid username or password!")



@app.route('/signup', methods=['POST'])
def signup():
    email = request.form.get('email')
    password = request.form.get('password')
    username = request.form.get('username')

    if not email or not password or not username:
        return jsonify({"error": "All fields are required!"}), 400

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Check if username already exists
    cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
    existing_user = cursor.fetchone()
    if existing_user:
        return jsonify({"error": "Username already exists! Please choose another."}), 400

    # Check if email already exists
    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    existing_email = cursor.fetchone()
    if existing_email:
        return jsonify({"error": "Email already registered! Try logging in."}), 400

    # Insert new user
    cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                   (username, email, password))
    mysql.connection.commit()

    # Retrieve the new user's ID
    cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
    new_user = cursor.fetchone()
    cursor.close()

    if new_user:
        # Set session variables
        session['user_id'] = new_user['id']  # ✅ Store user ID
        session['email'] = email
        session['username'] = username

        return jsonify({"success": "Signup successful!", "redirect": "/"})  # Redirect after signup
    else:
        return jsonify({"error": "Signup failed, please try again!"}), 500

@app.route('/ranking')
def ranking():
    if 'username' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch logged-in user details
    cursor.execute("SELECT id, username, rank, exp_own FROM users WHERE username = %s", (session['username'],))
    user = cursor.fetchone()

    # Fetch all users sorted by EXP
    cursor.execute("""
        SELECT users.id, users.username, users.rank, users.exp_own, guilds.guild_name AS guildname
        FROM users
        LEFT JOIN guilds ON users.guild_id = guilds.id  -- Join based on users.guild_id, not leader_id
        ORDER BY CAST(users.exp_own AS SIGNED) DESC
    """)

    users = cursor.fetchall()
    cursor.close()

    # Assign ranking positions and find current user's rank
    user_rank = None
    current_user = None

    for index, userss in enumerate(users, start=1):
        userss['rank_position'] = index  # Set ranking position
        if userss['username'] == session['username']:  # Find current user
            user_rank = index
            current_user = userss

    return render_template('ranking.html', user=user, users=users, user_rank=user_rank, current_user=current_user)



@app.route('/guild')
def guild():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Fetch user info
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, username, rank, guild_id FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()

    if not user:
        return redirect(url_for('logout'))  # Redirect if user not found

    user_data = {
        "id": user[0],
        "username": user[1],
        "rank": user[2],
        "guild_id": user[3]
    }

    # If the user is not in a guild
    if user_data["guild_id"] is None:
        return render_template('guild.html', user=user_data, guild=None, members=[])

    # Fetch guild details
    cur.execute("SELECT id, guild_name, leader_id FROM guilds WHERE id = %s", (user_data["guild_id"],))
    guild = cur.fetchone()

    if not guild:
        return render_template('guild.html', user=user_data, guild=None, members=[])

    guild_data = {
        "id": guild[0],
        "guild_name": guild[1],
        "leader_id": guild[2]
    }

    # Fetch leader name
    cur.execute("SELECT username FROM users WHERE id = %s", (guild_data["leader_id"],))
    leader = cur.fetchone()
    leader_name = leader[0] if leader else "Unknown"

    # Fetch guild members
    cur.execute("SELECT id, username, rank, exp_own FROM users WHERE guild_id = %s", (guild_data["id"],))
    members = cur.fetchall()
    member_list = [{"id": m[0], "username": m[1], "rank": m[2], "exp_own": m[3]} for m in members]

    cur.close()
    return render_template('guild.html', user=user_data, guild=guild_data, leader_name=leader_name, members=member_list)

# ----------------- Create Guild -----------------
@app.route('/create_guild', methods=['POST'])
def create_guild():
    if 'user_id' not in session:
        return jsonify({"error": "You must be logged in."})

    user_id = session['user_id']
    guild_name = request.form.get('guild_name')

    if not guild_name:
        return jsonify({"error": "Guild name is required!"})

    cur = mysql.connection.cursor()

    # Check if user is already in a guild
    cur.execute("SELECT guild_id FROM users WHERE id = %s", (user_id,))
    existing_guild = cur.fetchone()
    if existing_guild and existing_guild[0]:
        return jsonify({"error": "You are already in a guild!"})

    # Check if guild name exists
    cur.execute("SELECT id FROM guilds WHERE guild_name = %s", (guild_name,))
    existing_guild = cur.fetchone()
    if existing_guild:
        return jsonify({"error": "Guild name already taken!"})

    # Create Guild
    cur.execute("INSERT INTO guilds (guild_name, leader_id) VALUES (%s, %s)", (guild_name, user_id))
    mysql.connection.commit()

    # Get the new guild ID
    cur.execute("SELECT id FROM guilds WHERE guild_name = %s", (guild_name,))
    new_guild_id = cur.fetchone()[0]

    # Update user with the new guild ID
    cur.execute("UPDATE users SET guild_id = %s WHERE id = %s", (new_guild_id, user_id))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('guild'))


# ----------------- Join Guild -----------------
@app.route('/join_guild', methods=['POST'])
def join_guild():
    if 'user_id' not in session:
        return jsonify({"error": "You must be logged in."})

    user_id = session['user_id']
    guild_id = request.form.get('guild_id')

    if not guild_id:
        return jsonify({"error": "Guild ID is required!"})

    cur = mysql.connection.cursor()

    # Check if user is already in a guild
    cur.execute("SELECT guild_id FROM users WHERE id = %s", (user_id,))
    existing_guild = cur.fetchone()
    if existing_guild and existing_guild[0]:
        return jsonify({"error": "You are already in a guild!"})

    # Check if guild exists
    cur.execute("SELECT id FROM guilds WHERE id = %s", (guild_id,))
    guild = cur.fetchone()
    if not guild:
        return jsonify({"error": "Guild not found!"})

    # Add user to the guild
    cur.execute("UPDATE users SET guild_id = %s WHERE id = %s", (guild_id, user_id))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('guild'))

# ----------------- Leave Guild -----------------
@app.route('/leave_guild', methods=['POST'])
def leave_guild():
    if 'user_id' not in session:
        return jsonify({"error": "You must be logged in."})

    user_id = session['user_id']

    cur = mysql.connection.cursor()

    # Check user guild
    cur.execute("SELECT guild_id FROM users WHERE id = %s", (user_id,))
    guild_id = cur.fetchone()

    if not guild_id or guild_id[0] is None:
        return jsonify({"error": "You are not in a guild!"})

    # Remove user from guild
    cur.execute("UPDATE users SET guild_id = NULL WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('guild'))

# ----------------- Transfer Guild Leadership -----------------
@app.route('/transfer_leadership', methods=['POST'])
def transfer_leadership():
    if 'user_id' not in session:
        return jsonify({"error": "You must be logged in."})

    user_id = session['user_id']
    new_leader_id = request.form.get('new_leader_id')

    if not new_leader_id:
        return jsonify({"error": "Please select a new leader!"})

    cur = mysql.connection.cursor()

    # Check if user is the guild leader
    cur.execute("SELECT id FROM guilds WHERE leader_id = %s", (user_id,))
    guild = cur.fetchone()
    if not guild:
        return jsonify({"error": "You are not the guild leader!"})

    # Transfer leadership
    cur.execute("UPDATE guilds SET leader_id = %s WHERE id = %s", (new_leader_id, guild[0]))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('guild'))

# -------------------------------------------------------- START-QUESTS ------------------------------------------------------

from flask import request, jsonify
from datetime import datetime, timedelta

# Define rank rules as a dictionary
RANK_RULES = {
    "E": {"exp_gain": 30, "target_exp": 810, "penalty": -15},
    "D": {"exp_gain": 50, "target_exp": 1650, "penalty": -30},
    "C": {"exp_gain": 80, "target_exp": 3840, "penalty": -50},
    "B": {"exp_gain": 120, "target_exp": 7680, "penalty": -80},
    "A": {"exp_gain": 170, "target_exp": 14110, "penalty": -120},
    "S": {"exp_gain": 230, "target_exp": 25300, "penalty": -170},
    "O": {"exp_gain": 30, "target_exp": float("inf"), "penalty": -50}
}


@app.route('/complete_quest', methods=['POST'])
def complete_quest():
    if 'user_id' not in session:
        return jsonify({"error": "You must be logged in."}), 403

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch user data
    cursor.execute("SELECT rank, exp_own, exp_target FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user:
        return jsonify({"error": "User not found."}), 404

    rank = user['rank']
    exp_own = int(user['exp_own'])
    exp_target = int(user['exp_target'])

    # Get EXP rules based on rank
    exp_gain = RANK_RULES[rank]['exp_gain']

    # Update user's EXP
    exp_own += exp_gain

    # Check for rank-up
    if exp_own >= exp_target:
        new_rank = next_rank(rank)
        new_target_exp = RANK_RULES[new_rank]['target_exp']
        exp_own = 0  # Reset EXP on rank-up
    else:
        new_rank = rank
        new_target_exp = exp_target

    # Update user record
    cursor.execute("""
        UPDATE users SET exp_own = %s, rank = %s, exp_target = %s WHERE id = %s
    """, (exp_own, new_rank, new_target_exp, user_id))
    mysql.connection.commit()
    cursor.close()

    return jsonify({"success": "Quest completed!", "new_exp": exp_own, "rank": new_rank})


def next_rank(current_rank):
    rank_order = ["E", "D", "C", "B", "A", "S", "O"]
    if current_rank in rank_order:
        index = rank_order.index(current_rank)
        return rank_order[index + 1] if index + 1 < len(rank_order) else current_rank
    return current_rank

@app.route('/quest')
def quest():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    # Check last quest completion date
    cursor.execute("""
        SELECT DATE(date_completed) AS last_completed FROM quest_history
        WHERE user_id = %s ORDER BY date_completed DESC LIMIT 1
    """, (user_id,))
    last_quest = cursor.fetchone()
    today = datetime.now().date()
    last_completed_date = last_quest['last_completed'] if last_quest else None

    quest_completed_today = last_completed_date == today

    cursor.execute("""
        SELECT DATE(date_completed) AS date, completed_tasks FROM quest_history
        WHERE user_id = %s ORDER BY date_completed DESC LIMIT 10
    """, (user_id,))
    quest_history = cursor.fetchall()
    cursor.close()

    return render_template('quest.html', user=user)
                           # , quest_history=quest_history,
                           # quest_completed_today=quest_completed_today)


from datetime import datetime, timedelta


@app.route('/apply_penalty', methods=['POST'])
def apply_penalty():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch all users
    cursor.execute("SELECT id, rank, exp_own, exp_target FROM users")
    users = cursor.fetchall()

    for user in users:
        user_id = user['id']
        rank = user['rank']
        exp_own = int(user['exp_own'])
        exp_target = int(user['exp_target'])

        # Get penalty amount for the rank
        penalty = RANK_RULES[rank]['penalty']

        # Apply penalty
        exp_own = max(0, exp_own + penalty)  # Prevent negative EXP

        # If EXP is fully lost, reset based on 20% rule
        if exp_own == 0:
            exp_own = int(0.2 * exp_target)

        # Update database
        cursor.execute("""
            UPDATE users SET exp_own = %s WHERE id = %s
        """, (exp_own, user_id))

    mysql.connection.commit()
    cursor.close()

    return jsonify({"success": "Penalties applied successfully!"})


# @app.route('/check_quest_status', methods=['GET'])
# def check_quest_status():
#     if 'user_id' not in session:
#         return jsonify({"completed": False, "error": "Not logged in"})
#
#     user_id = session['user_id']
#     cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
#
#     # Fetch user rank
#     cursor.execute("SELECT rank FROM users WHERE id = %s", (user_id,))
#     user = cursor.fetchone()
#     if not user:
#         return jsonify({"completed": False, "error": "User not found"})
#
#     rank = user['rank']
#     required_tasks = RANK_RULES[rank]  # Get the tasks for the rank
#
#     # Check if the user has completed tasks (You need a table to track completions!)
#     cursor.execute("SELECT * FROM quest_progress WHERE user_id = %s AND date = CURDATE()", (user_id,))
#     quest_data = cursor.fetchone()
#     cursor.close()
#
#     # If quest progress exists for today, mark it as completed
#     completed = bool(quest_data)
#     return jsonify({"completed": completed})


from datetime import datetime, timedelta


@app.route('/check_quest_status', methods=['GET'])
def check_quest_status():
    if 'user_id' not in session:
        return jsonify({"completed": False, "error": "Not logged in"})

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Check if the user has completed today's quest from quest_history
    cursor.execute("SELECT date_completed FROM quest_history WHERE user_id = %s ORDER BY date_completed DESC LIMIT 1",
                   (user_id,))
    last_completion = cursor.fetchone()
    cursor.close()

    if last_completion:
        last_completion_time = last_completion['date_completed']
        reset_time = datetime.now().replace(hour=4, minute=0, second=0, microsecond=0)  # Reset at 4 AM

        print(f"Last Completion: {last_completion_time}, Reset Time: {reset_time}")  # Debugging Log

        if last_completion_time and last_completion_time > reset_time - timedelta(days=1):
            return jsonify({"completed": True, "last_completed": str(last_completion_time)})  # Include debug info

    return jsonify({"completed": False})

# -------------------------------------------------------- END-QUESTS ------------------------------------------------------

# @app.route('/logout')
# def logout():
#     session.pop('user_id', None)  # ✅ Remove user_id
#     session.pop('email', None)
#     session.pop('username', None)
#     session.pop('rank', None)
#     return redirect('/')

@app.route('/logout')
def logout():
    session.clear()  # ✅ Clears all session data
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True,host='192.168.1.7')
