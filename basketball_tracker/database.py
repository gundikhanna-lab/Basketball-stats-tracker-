import sqlite3  # Using the built-in sqlite3 library to handle the database


# ==========================================
# SESSION CLASS
# ==========================================
# I made a Session class to keep all the data for one game grouped together. 
# This makes it easier to pass the data around the program as an object instead of dealing with loose variables.
class Session:
    # The constructor sets up a new game session when the user submits the form
    def __init__(self, date, opponent, points, assists, rebounds, attendance, positions):
        self.date = date
        self.opponent = opponent
        
        # The HTML form sends numbers as text (strings). I have to convert them to integers here, 
        # otherwise my math calculations in the Stats class will crash.
        self.points = int(points)
        self.assists = int(assists)
        self.rebounds = int(rebounds)
        
        self.attendance = attendance
        # This is a list because a player can select multiple position checkboxes on the form
        self.positions = positions  


# ==========================================
# DATABASE CLASS
# ==========================================
# This class handles all the SQL queries so the main app file doesn't get cluttered.
class Database:
    def __init__(self, db_name="sessions.db"):
        self.db_name = db_name
        # Call create_table right away so the database file and tables are ready before the user does anything
        self.create_table()

    # Helper method to open the database connection
    def connect(self):
        conn = sqlite3.connect(self.db_name)
        # SQLite has foreign keys turned off by default. I need to turn them on so that
        # my "ON DELETE CASCADE" rule below actually works when I delete a game.
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # Sets up the database structure if it's the first time the app is running
    def create_table(self):
        conn = self.connect()

        # Table to hold the main stats for each game. 
        # I used AUTOINCREMENT for the primary key so I don't have to generate IDs manually.
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                opponent TEXT NOT NULL,
                points INTEGER NOT NULL,
                assists INTEGER NOT NULL,
                rebounds INTEGER NOT NULL,
                attendance TEXT NOT NULL
            )
        ''')

        # A simple table just to store the names of the 5 basketball positions
        conn.execute('''
            CREATE TABLE IF NOT EXISTS position (
                position_id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_name TEXT NOT NULL
            )
        ''')

        # This is a junction table. Because one game can have multiple positions, and one position 
        # can be played in multiple games, I needed this to handle the Many-to-Many relationship.
        conn.execute('''
            CREATE TABLE IF NOT EXISTS session_position (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                position_id INTEGER,
                
                -- ON DELETE CASCADE means if I delete a game from 'sessions', 
                -- it automatically deletes the linked rows in this table so I don't leave behind junk data.
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (position_id) REFERENCES position(position_id)
            )
        ''')
        
        # Check if the positions table is empty. If it is, insert the 5 standard basketball positions.
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM position")
        if cursor.fetchone()[0] == 0:
            # Using executemany to insert all of them at once instead of writing 5 separate insert queries
            cursor.executemany("INSERT INTO position (position_name) VALUES (?)", [
                ("Point Guard",),
                ("Shooting Guard",),
                ("Small Forward",),
                ("Power Forward",),
                ("Center",)
            ])
        conn.commit()
        conn.close()

    # Takes a Session object and saves it to the database
    def add_session(self, session):
        conn = self.connect()
        cursor = conn.cursor()

        # I use question marks (?) to insert data safely. This prevents SQL injection attacks 
        # if someone types weird characters into the web form.
        cursor.execute('''
            INSERT INTO sessions (date, opponent, points, assists, rebounds, attendance)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session.date, session.opponent, session.points,
              session.assists, session.rebounds, session.attendance))

        # Get the ID of the game we just inserted so we know how to link it to the selected positions
        session_id = cursor.lastrowid  

        # Loop through whatever position checkboxes the user selected and add a link in the junction table for each one
        for pos_id in session.positions:
            cursor.execute('''
                INSERT INTO session_position (session_id, position_id)
                VALUES (?, ?)
            ''', (session_id, pos_id))

        conn.commit()
        conn.close()

    # Deletes a specific game using its ID
    def delete_session(self, session_id):
        conn = self.connect()
        conn.execute('DELETE FROM sessions WHERE id = ?', (session_id,))
        conn.commit()
        conn.close()

    # Gets the list of 5 positions to generate the checkboxes on the form
    def get_positions(self):
        conn = self.connect()
        rows = conn.execute('SELECT * FROM position').fetchall()
        conn.close()
        return rows

    # Gets all the games from the database to show on the homepage, newest first
    def get_all_sessions(self):
        conn = self.connect()
        # I use a LEFT JOIN just in case a game somehow has no positions linked to it (so it doesn't disappear).
        # GROUP_CONCAT takes the multiple linked positions and combines them into one string (like "Point Guard, Center")
        # so it's easy to display in the HTML table.
        query = '''
            SELECT s.id, s.date, s.opponent, s.points, s.assists, s.rebounds, s.attendance,
                   GROUP_CONCAT(p.position_name, ', ') as positions_played
            FROM sessions s
            LEFT JOIN session_position sp ON s.id = sp.session_id
            LEFT JOIN position p ON sp.position_id = p.position_id
            GROUP BY s.id
            ORDER BY s.date DESC
        '''
        rows = conn.execute(query).fetchall()
        conn.close()
        return rows

    # Works exactly like get_all_sessions, but adds a WHERE clause to filter between two dates
    def get_filtered_sessions(self, start_date, end_date):
        conn = self.connect()
        query = '''
            SELECT s.id, s.date, s.opponent, s.points, s.assists, s.rebounds, s.attendance,
                   GROUP_CONCAT(p.position_name, ', ') as positions_played
            FROM sessions s
            LEFT JOIN session_position sp ON s.id = sp.session_id
            LEFT JOIN position p ON sp.position_id = p.position_id
            WHERE s.date BETWEEN ? AND ?
            GROUP BY s.id
            ORDER BY s.date ASC
        '''
        rows = conn.execute(query, (start_date, end_date)).fetchall()
        conn.close()
        return rows

    # Counts how many times the user played each position to show on the stats page
    def get_position_distribution(self):
        conn = self.connect()
        # I start the join from the 'position' table so that if a position has 0 games, 
        # it still shows up in the results with a count of 0 instead of just vanishing.
        query = '''
            SELECT p.position_name, COUNT(sp.position_id) as count
            FROM position p
            LEFT JOIN session_position sp ON p.position_id = sp.position_id
            GROUP BY p.position_id
        '''
        rows = conn.execute(query).fetchall()
        conn.close()
        # Converts the database rows into a Python dictionary to make it easier for the front-end to read
        return {row[0]: row[1] for row in rows}  


# ==========================================
# STATS CLASS
# ==========================================
# I separated the math calculations into their own class to keep the code organized 
# and keep the database class focused purely on SQL.
class Stats:
    def __init__(self, sessions):
        self.sessions = sessions

    # Calculates the average points, assists, and rebounds per game
    def get_averages(self):
        # If there are no games logged yet, return None so the app doesn't divide by zero and crash
        if not self.sessions:
            return None

        count = len(self.sessions)
        # s[3], s[4], and s[5] match the column order from the SQL SELECT query
        # I add them all up, divide by the total games, and round to 1 decimal place so it looks clean
        avg_points = round(sum(s[3] for s in self.sessions) / count, 1)
        avg_assists = round(sum(s[4] for s in self.sessions) / count, 1)
        avg_rebounds = round(sum(s[5] for s in self.sessions) / count, 1)

        return {
            'points': avg_points,
            'assists': avg_assists,
            'rebounds': avg_rebounds
        }

    # Calculates how many games the player actually attended vs missed
    def get_attendance(self):
        total = len(self.sessions)
        # s[6] is the attendance column. This loops through and counts every game marked "Yes"
        attended = sum(1 for s in self.sessions if s[6] == 'Yes')
        
        # Calculates the percentage, but checks if total > 0 first to avoid a divide by zero crash
        percentage = round((attended / total) * 100, 1) if total > 0 else 0
        return {'attended': attended, 'total': total, 'percentage': percentage}

    # Prepares the data for the points per game graph on the stats page
    def get_points_per_game(self):
        # Sorts the games by date, then extracts just the date and points into a clean list for the graph
        return [(s[1], s[3]) for s in sorted(self.sessions, key=lambda x: x[1])]