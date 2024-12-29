import redis
from flask import Flask, render_template, request, redirect, url_for, flash, session,jsonify
import attendance
from flask_cors import CORS
from flask_session import Session  # Import Session
import json
import random


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Make sure you use a secure secret key

# Setup Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'  # You can use other types like Redis or MongoDB
Session(app)

# Enable CORS for the entire Flask app
CORS(app)

# Redis connection setup
hostname = 'redis-17795.c325.us-east-1-4.ec2.redns.redis-cloud.com'
port = 17795
password = 'fLnGGZUuGeBFOSOo21yPBi8Z9B08AgZJ'

# Initialize Redis client
r = redis.StrictRedis(
    host=hostname,
    port=port,
    password=password,
    decode_responses=True  # Ensures responses are decoded as strings, not bytes
)

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get login form data
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']  # Get the selected role from the form
        print(username)
        # Check if user exists in Redis and validate password and role
        if r.exists(username):
            print(7)
            stored_password = r.hget(username, 'password')
            stored_role = r.hget(username, 'role')  # Retrieve the stored role
            print('1')
            if stored_password == password and stored_role == role:  # Check both password and role
                flash('Login successful!', 'success')

                # Store the username in the session
                session['username'] = username
                
                # Redirect user to the appropriate dashboard based on role and pass the username
                if role == 'Supervisor':
                    return redirect(url_for('supervisor_dashboard'))
                elif role == 'Manager':
                    return redirect(url_for('manager_dashboard'))
                elif role == 'Staff':
                    return redirect(url_for('staff_dashboard'))
            else:
                flash('Invalid password or role. Please try again.', 'danger')
        else:
            flash('Username not found. Please register first.', 'danger')

    return render_template('Login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get registration form data
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']  # Get the selected role from the form

        # Check if the username already exists
        if r.exists(username):
            flash('Username already exists. Please choose another one.', 'danger')
            return redirect(url_for('register'))
        
        # Store user data in Redis (using username as the key)
        r.hset(username, 'email', email)
        r.hset(username, 'password', password)
        r.hset(username, 'role', role)  # Save the selected role to Redis
        flash('Registration successful! Please fill in the additional details.', 'success')
        return redirect(url_for('forms_page'))
    
    return render_template('Register.html')

# Forms page - Collect additional details (this will redirect to Streamlit page)
@app.route('/forms', methods=['GET'])
def forms_page():
    # Instead of running the script in Flask, redirect to Streamlit app
    streamlit_url = 'http://localhost:8501'  # The URL where your Streamlit app is running
    return redirect(streamlit_url)


# Staff
@app.route('/staff_dashboard', methods=['GET', 'POST'])
def staff_dashboard():
    # Fetch username and email from session
    username = session.get('username')
    cap = username[0]
    user = cap.upper() + username[1:]
    email = session.get('email')

    # Fetch tasks for Srinivas from Redis
    tasks = r.hgetall('tasks:srinivas')
    tasks = [{'id': task_id, 'description': task_desc}
             for task_id, task_desc in tasks.items()]

    # POST method to handle task completion
    if request.method == 'POST':
        completed_tasks = request.form.getlist(
            'completed_tasks')  # Get completed tasks from form
        # Remove completed tasks from Redis
        for task_id in completed_tasks:
            r.hdel('tasks:srinivas', task_id)

        # After removal, fetch updated task list and show success message
        tasks = [{'id': task_id, 'description': task_desc}
                 for task_id, task_desc in r.hgetall('tasks:srinivas').items()]
        return render_template('staff_dashboard.html', username=user, email=email, tasks=tasks, success_message="Tasks updated successfully.")

    # GET request to render the dashboard with tasks
    return render_template('staff_dashboard.html', username=user, email=email, tasks=tasks)

@app.route('/certificate')
def certificate():
    return render_template('certification.html')

@app.route('/e_key_metrics')
def e_key_metrics():
    return render_template('e_key_metrics.html')

# Staff Attendance
@app.route('/staff_attendance')
def staff_attendance():
    # Use session to get the username
    username = session.get('username')
    print(f"Username received in staff_attendance: {username}")
    
    # If the username is not found in session, redirect to login
    if not username:
        flash('You need to log in first.', 'danger')
        return redirect(url_for('login'))

    report_df = attendance.generate_report()
    staff_report = report_df[report_df['Name'] == username].to_dict(orient='records')
    
    return render_template('staff_attendance.html', username=username, attendance_data=staff_report)

@app.route('/staff-leave-request')
def staff_leave_request():
    #username = session['username']
    #email = session['email']

    return render_template('staff_leave.html')


@app.route('/handle-leave-request', methods=['POST'])
def handle_leave():
    reason = request.form.get('reason')
    print(reason)
    username = session['username']
    session['reason'] = reason
    r.hset(username, 'leave_status', 'pending')
    r.hset(username, 'leave_response_message', 'None')

    if reason and r.hget(username, 'leave_status') == 'pending':
        r.hset(username, 'leave_reason', reason)

        # Render a template that shows the success message and then redirects after 5 seconds
        return render_template('success.html', username=username)


@app.route('/view_leave_status')
def view_leave_status():
    username = session['username']
    leave_status = r.hget(username, 'leave_status')
    leave_response_message = r.hget(username, 'leave_response_message')
    return render_template('view_leave_status.html', leave_status=leave_status, leave_response_message=leave_response_message)

@app.route('/view-leave-request')
def view_leave():
    dict = {}

    for key in r.scan_iter('*'):
        # Check if the key is a hash

        if r.type(key) == 'hash':
            if r.hexists(key, 'leave_reason'):
                leave_reason = r.hget(key, 'leave_reason')
                email = r.hget(key, 'email')
                dict[key] = [leave_reason, email]
    print(dict)
    return render_template('Supervisor_view_leave.html', dict=dict)


@app.route('/staff_leave_request_action', methods=['POST'])
def staff_leave_request_action():
    # Handle the leave request action (approve/decline)
    # Assuming 'username' is sent in the POST form
    username = request.form['username']
    # Assuming 'action' is sent in the POST form (e.g., 'approve' or 'decline')
    action = request.form['action']
    print(action)
    # Save the action (e.g., approve or decline) in Redis
    if action == 'approve':
        r.hset(username, 'leave_status', 'Approved')
        r.hset(username, 'leave_response_message',
               'Your leave request has been approved.')
        print(1)
        r.hdel(username, 'leave_reason')
        print(2)
    elif action == 'decline':
        r.hset(username, 'leave_status', 'Declined')
        r.hset(username, 'leave_response_message',
               'Your leave request has been declined.')
        r.hdel(username, 'leave_reason')
        print(0)

    # Redirect to the view where staff can see the updated status
    return redirect('/view-leave-request')

@app.route('/staff-shift-change', )
def shift_change_request():
    return render_template('shift_change_request.html')


@app.route('/shift_history', )
def shift_history():
    return render_template('shift_history.html')

@app.route('/staff-raise-complaints')
def raise_complaint():
    return render_template('staff_complaints.html')


@app.route('/staff-handle-complaints', methods=['POST'])
def handle_complaints():
    username = session['username']
    complaints = request.form['Complaint']
    person = request.form['to_whom']
    cd = request.form['complaint-details']
    print(cd)

    print(complaints)
    if (complaints and person == 'manager'):
        r.hset(username, 'manager_complaints', complaints)
        r.hset(username, 'm_complaint_request', 'pending')
        r.hset(username, 'm_complaint_description', cd)
        return render_template('success_2.html', username=username, person=person)
    elif (complaints and person == 'supervisor'):
        r.hset(username, 'supervisor_complaints', complaints)
        r.hset(username, 's_complaint_request', 'pending')
        r.hset(username, 's_complaint_description', cd)
        return render_template('success_2.html', username=username, person=person)
    else:
        return "NO COMPLAINTS RECEIVED!!"
    # Home route (after login)


# Supervisor
@app.route('/supervisor_dashboard')
def supervisor_dashboard():
    # Get the username from session
    username = session.get('username')
    
    # Pass the username to the template
    return render_template('Supervisor_dashboard.html', username=username)


@app.route('/generate_report')
def generate_report():
    employees = []
    for emp_id in range(1001, 1021):  # Modify the range according to your needs
        employee_key = f"staff:{emp_id}"
        employee = r.hgetall(employee_key)
        if employee:
            # Convert Redis data into Python dictionary with string keys
            employee = {k.decode('utf-8') if isinstance(k, bytes) else k: v.decode('utf-8') if isinstance(v, bytes) else v for k, v in employee.items()}
            
            # Add fallback for missing fields like 'phase', 'tasks_completed', 'total_tasks'
            employee['phase'] = employee.get('phase', 'Unknown')  # 'Unknown' as placeholder if phase is missing
            employee['tasks_completed'] = random.randint(1,20)   # Default to 0 if missing
            employee['total_tasks'] = employee.get('total_tasks', '20')  # Default to 0 if missing
            employees.append(employee)
    
    return render_template("report_generation.html", employees=employees)

@app.route('/key_metrics')
def key_metrics():
    return render_template('key_metrics.html')

@app.route('/greivances')
def greivances():
    return render_template('greivances.html')

@app.route('/current_shift_schedule')
def current_shift_schedule():
    # Fetch all employee keys from Redis
    keys = r.keys('staff:*')

    # Initialize a dictionary to hold employee data grouped by phase
    employee_data = {}

    for key in keys:
        # Get the employee data from Redis
        employee = r.hgetall(key)
        
        # Extract phase and other details
        phase = employee.get('phase', 'Unknown Phase')
        employee_info = {
            'id': key.split(':')[1],
            'name': employee.get('name', 'Unknown'),
            'availability': employee.get('shift', 'Not Assigned')  # Adjust according to your stored fields
        }
        
        # Append the employee to the corresponding phase in employee_data
        if phase not in employee_data:
            employee_data[phase] = []
        employee_data[phase].append(employee_info)

    return render_template('current_shift_schedule.html', employee_data=employee_data)

def fetch_employees_by_phase(phase):
    keys = r.keys(f"staff:*")
    employees = []
    for key in keys:
        employee_data = r.hgetall(key)
        if employee_data.get('phase') == phase:
            employee_data['id'] = key.split(':')[1]  # Extract ID from key
            employees.append(employee_data)
    return employees

@app.route('/allocate_work')
def allocate_work():
    phase = request.args.get('phase', 'Raw Material Production')
    
    # Fetch employees for the selected phase
    employees = fetch_employees_by_phase(phase)
    
    # Sort employees based on KPM (descending order)
    sorted_employees = sorted(employees, key=lambda x: int(x.get('kpm', '0%').replace('%', '')), reverse=True)
    
    # Divide employees into High KPM and Low KPM categories
    high_kpm_employees = [emp for emp in sorted_employees if int(emp.get('kpm', '0%').replace('%', '')) >= 90]
    low_kpm_employees = [emp for emp in sorted_employees if int(emp.get('kpm', '0%').replace('%', '')) < 90]

    # Calculate half the number of employees for day and night shifts
    half_high = len(high_kpm_employees) // 2
    half_low = len(low_kpm_employees) // 2

    # Assign shifts equally between Day and Night for High KPM employees
    for i, employee in enumerate(high_kpm_employees):
        if i < half_high:
            employee['shift'] = 'Day'
        else:
            employee['shift'] = 'Night'
        employee['kpm_category'] = 'High'

    # Assign shifts equally between Day and Night for Low KPM employees
    for i, employee in enumerate(low_kpm_employees):
        if i < half_low:
            employee['shift'] = 'Day'
        else:
            employee['shift'] = 'Night'
        employee['kpm_category'] = 'Low'

    # Combine the two lists back into one
    sorted_employees = high_kpm_employees + low_kpm_employees

    # Store updated employee data in Redis
    for employee in sorted_employees:
        r.hset(f"staff:{employee['id']}", mapping=employee)

    # Debug print
    print(f"Phase: {phase}")
    print(f"Employees fetched and allocated: {sorted_employees}")

    # Render the allocate_work page with the employees and their shifts
    return render_template('allocate_work.html', employees=sorted_employees, phase=phase)

@app.route('/fetch_employees/<phase>', methods=['GET'])
def fetch_employees(phase):
    employees = fetch_employees_by_phase(phase)
    return jsonify(employees)

@app.route('/allocate_shifts/<phase>', methods=['POST'])
def allocate_shifts(phase):
    try:
        # Extract form data
        form_data = request.form

        # Loop through each shift input
        for key in form_data:
            if key.startswith('shift_'):
                employee_id = key.split('_')[1]  # Extract employee ID from the form field name
                shift_value = form_data[key]     # Get the shift value

                # Update the shift field for the employee in Redis
                r.hset(f"staff:{employee_id}", 'shift', shift_value)

        return jsonify({"status": "Shifts updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/edit_employee/<phase>/<employee_id>', methods=['PUT', 'DELETE'])
def edit_employee(phase, employee_id):
    phase = request.args.get('phase')
    
    if request.method == 'DELETE':
        r.delete(f'staff:{employee_id}')
        return jsonify({'status': 'Employee removed'})
    
    if request.method == 'PUT':
        data = request.json
        r.hset(f'staff:{employee_id}', mapping=data)
        return jsonify({'status': 'Employee updated'})


@app.route('/supervisor_com_att')
def supervisor_com_att():
    username = session.get('username')
    return render_template('supervisor_com_att.html', username=username)

@app.route('/all_staff_attendance')
def allstaff_view():
    report_df = attendance.generate_report()
    staff_report = report_df[report_df['Role'] == 'Staff'].to_dict(orient='records')
    return render_template('allstaff.html', attendance_data=staff_report)

@app.route('/supervisor_attendance')
def supervisor_attendance():
    # Use session to get the username
    username = session.get('username')
    print(f"Username received in supervisor_attendance: {username}")
    
    # If the username is not found in session, redirect to login
    if not username:
        flash('You need to log in first.', 'danger')
        return redirect(url_for('login'))

    # Fetch the role from Redis using the username
    role = r.hget(username, 'role')
    print(f"User Role: {role}")
    
    # Check if the logged-in user is a supervisor
    if role == 'Supervisor':
        # Fetch attendance report from the DataFrame
        report_df = attendance.generate_report()

        # Filter the report DataFrame to include only the logged-in supervisor's records
        supervisor_report = report_df[(report_df['Name'] == username) & (report_df['Role'] == 'Supervisor')].to_dict(orient='records')
        print(f"Supervisor Report: {supervisor_report}")

        return render_template('staff_attendance.html', username=username, attendance_data=supervisor_report)
    else:
        # If the user is not a supervisor, redirect them with an error message
        flash('Unauthorized access. Only supervisors can view this page.', 'danger')
        return redirect(url_for('login'))
    
@app.route('/supervisor_schedule')
def supervisor_schedule():
    return render_template('supervisor_schedule.html')

@app.route("/view-complaint-supervisor", methods=['GET'])
def handle_supervisor_complaints():
    dict = {}
    for keys in r.scan_iter('*'):
        print(keys)
        if r.type(keys) == 'hash':
            print(keys)
            if r.hexists(keys, 'supervisor_complaints'):
                print(keys)
                dict[keys] = r.hget(keys, 'supervisor_complaints')
                print(r.hget(keys, 'supervisor_complaints'))
    return render_template('Supervisor_view_complaint.html', dict=dict)


@app.route('/review-complaint-supervisor', methods=['POST'])
def review_complaint_supervisor():
    username = request.form.get('username')
    print(username)
    complaint_description = r.hget(username, 's_complaint_description')
    print(complaint_description)
    return render_template('supervisor_review_complaint.html', complaint_description=complaint_description)



# Manager 
@app.route('/manager_dashboard')
def manager_dashboard():
    username = session.get('username')
    return render_template('Manager_dashboard.html', username=username)

@app.route('/m_key_metrics')
def m_key_metrics():
    return render_template('m_key_metrics.html')

@app.route('/manager_com_att')
def manager_com_att():
    username = session.get('username')
    return render_template('manager_com_att.html', username=username)

@app.route('/view_all_staff')
def view_all_staff():
    report_df = attendance.generate_report()
    staff_report = report_df[report_df['Role'] == 'Staff'].to_dict(orient='records')
    return render_template('allstaff.html', attendance_data=staff_report)

@app.route('/view_all_supervisors')
def view_all_supervisors():
    report_df = attendance.generate_report()
    manager_report = report_df[report_df['Role'] == 'Supervisor'].to_dict(orient='records')
    return render_template('allsupervisor.html', attendance_data=manager_report)

@app.route('/work_allocate')
def work_allocate():
    return render_template('work_allocation.html')

@app.route('/report')
def report():
    return render_template('report.html')

@app.route('/manager_attendance')
def manager_attendance():
    # Use session to get the username
    username = session.get('username')
    print(f"Username received in supervisor_attendance: {username}")
    
    # If the username is not found in session, redirect to login
    if not username:
        flash('You need to log in first.', 'danger')
        return redirect(url_for('login'))

    # Fetch the role from Redis using the username
    role = r.hget(username, 'role')
    print(f"User Role: {role}")
    
    # Check if the logged-in user is a supervisor
    if role == 'Manager':
        # Fetch attendance report from the DataFrame
        report_df = attendance.generate_report()

        # Filter the report DataFrame to include only the logged-in supervisor's records
        manager_report = report_df[(report_df['Name'] == username) & (report_df['Role'] == 'Manager')].to_dict(orient='records')
        print(f"Manager Report: {manager_report}")

        return render_template('staff_attendance.html', username=username, attendance_data=manager_report)
    else:
        # If the user is not a supervisor, redirect them with an error message
        flash('Unauthorized access. Only supervisors can view this page.', 'danger')
        return redirect(url_for('login'))

@app.route('/view-compalint-manager', methods=['GET'])
def handle_manager_comaplaints():
    dict = {}
    for keys in r.scan_iter('*'):
        if r.type(keys) == 'hash':
            if r.hexists(keys, 'manager_complaints'):
                dict[keys] = r.hget(keys, 'manager_complaints')
    return render_template('grievances_m.html', dict=dict)


@app.route('/review-complaint-manager', methods=['POST'])
def review_complaint_manager():
    username = request.form.get('username')
    print(username)
    complaint_description = r.hget(username, 'm_complaint_description')
    print(complaint_description)
    return render_template('Manager_review_complaint.html', complaint_description=complaint_description)


@app.route('/profile')
def profile():
    # Fetch the username from session
    print('profile')
    username = session.get('username')
    print(username)
    # If the user is not logged in, redirect to the login page
    if not username:
        flash('You need to log in first.', 'danger')
        return redirect(url_for('login'))

    role = r.hget(username, 'role') 
    print(role)
    if role:
        key = f'{username}@{role}'
    else:
        flash('User role missing. Please log in again.', 'danger')
        return redirect(url_for('login'))

    # Fetch the serialized data and decode it
    user_details_bytes = r.hget('academy:register:details', key)
    print(user_details_bytes)
    
    if not user_details_bytes:
        flash('Profile not found.', 'danger')
        return redirect(url_for('login'))

    # Deserialize the user details (stored as JSON in Redis)
    user_details = json.loads(user_details_bytes)

    # Add username and role to the user details
    user_data = {
        'username': username,
        'role': role,
        **user_details
    }
    print(user_data)
    if role == 'Supervisor':
        return render_template('profile_sup.html', user=user_data)
    elif role == 'Manager':
        return render_template('profile_man.html', user=user_data)
    elif role == 'Staff':
        return render_template('profile_staff.html', user=user_data)
    else:
        flash('Invalid password or role. Please try again.', 'danger')
      
    
if __name__ == '__main__':
    app.run(debug=True)
