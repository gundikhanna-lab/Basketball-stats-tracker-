from flask import Flask, render_template, request, redirect, url_for
# Importing my custom classes from database.py so I can interact with SQLite and perform math operations
from database import Database, Session, Stats

# Initializing the Flask web application and instantiating my database controller object
app = Flask(__name__)
db = Database()


# ==========================================
# HOMEPAGE ROUTE
# ==========================================
# Main page route - fetches all logged games from SQLite and displays them in an HTML table
@app.route('/')
def index():
    sessions = db.get_all_sessions()
    return render_template('index.html', sessions=sessions)


# ==========================================
# ADD SESSION ROUTE
# ==========================================
# Handles both displaying the entry form (GET) and saving the user's input data (POST)
@app.route('/add', methods=['GET', 'POST'])
def add():
    error = None
    # Gets all 5 positions from the database to dynamically build the checkbox choices on the web page
    positions = db.get_positions()

    # If the user submitted the form (POST request), process the form data
    if request.method == 'POST':
        # Extract text values entered into the form inputs
        date = request.form['date']
        opponent = request.form['opponent']
        points = request.form['points']
        assists = request.form['assists']
        rebounds = request.form['rebounds']
        attendance = request.form['attendance']
        
        # I used getlist() instead of standard request.form here because multiple position 
        # checkboxes can be selected at once, which returns a list of selected IDs
        selected_positions = request.form.getlist('position')

        # --- INPUT VALIDATION ---
        # Stage 1: Make sure no required text fields were left blank
        if not date or not opponent or not points or not assists or not rebounds:
            error = 'All fields are required.'
        # Stage 2: Ensure the player selected at least one position checkbox
        elif not selected_positions:
            error = 'Please select at least one position.'
        # Stage 3: Prevent impossible stats (like negative points) from entering the database
        elif int(points) < 0 or int(assists) < 0 or int(rebounds) < 0:
            error = 'Values cannot be negative.'
        else:
            # If all input validation passes, bundle the data into a Session object and save it to DB
            new_session = Session(date, opponent, points, assists, rebounds, attendance, selected_positions)
            db.add_session(new_session)
            
            # Redirecting back to the homepage prevents duplicate form submissions if the user refreshes the page
            return redirect(url_for('index'))

    # If it's a GET request (or if form validation failed), render the add.html page with any error message
    return render_template('add.html', error=error, positions=positions)


# ==========================================
# DELETE SESSION ROUTE
# ==========================================
# Uses a dynamic URL parameter (<int:session_id>) to get the specific game ID directly from the delete link
@app.route('/delete/<int:session_id>')
def delete(session_id):
    db.delete_session(session_id)
    # Immediately redirect back to homepage to refresh the table view
    return redirect(url_for('index'))


# ==========================================
# FILTER SESSIONS ROUTE
# ==========================================
# Processes date range search queries and displays matching game records
@app.route('/filter', methods=['POST'])
def filter_sessions():
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    error = None
    sessions = []

    # Check that both start and end dates were selected
    if not start_date or not end_date:
        error = 'Please enter both dates.'
        sessions = db.get_all_sessions()
    
    # Logical check: Stop the query if the user picks a start date that comes AFTER the end date.
    # String comparison works here because ISO dates are formatted as YYYY-MM-DD (e.g., "2024-05-10" > "2024-01-01").
    elif start_date > end_date:
        error = 'Start date must be before end date.'
        sessions = db.get_all_sessions()
    else:
        # Fetch games within the selected date boundaries from SQLite
        sessions = db.get_filtered_sessions(start_date, end_date)
        # Edge case handling: Inform the user if no game records fell inside that date range
        if not sessions:
            error = 'No sessions found in this date range.'

    # Re-uses index.html to render the filtered query results so I don't need to build a duplicate page
    return render_template('index.html', sessions=sessions, error=error)


# ==========================================
# STATS DASHBOARD ROUTE
# ==========================================
# Calculates and displays player performance averages, attendance percentage, and graph plotting data
@app.route('/stats')
def stats():
    sessions = db.get_all_sessions()

    # Edge case guard: If no games exist yet, pass empty default values so 
    # stats.html doesn't crash trying to render non-existent dataset calculations
    if not sessions:
        return render_template('stats.html', averages=None, attendance=None, points_per_game=[], position_distribution={}, max_points=1)

    # Delegate mathematical calculations to the Stats processing class
    stats_obj = Stats(sessions)
    averages = stats_obj.get_averages()
    attendance = stats_obj.get_attendance()
    points_per_game = stats_obj.get_points_per_game()
    position_distribution = db.get_position_distribution()

    # Finds the highest-scoring game so I can scale the bar graph height dynamically in CSS/HTML
    max_points = max((p[1] for p in points_per_game), default=1)

    return render_template('stats.html',
                            averages=averages,
                            attendance=attendance,
                            points_per_game=points_per_game,
                            position_distribution=position_distribution,
                            max_points=max_points)


# Launches the Flask local development server when running app.py directly
if __name__ == '__main__':
    app.run(debug=True)