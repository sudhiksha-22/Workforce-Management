from flask import Flask, render_template, jsonify
import redis
import pandas as pd
from datetime import timedelta

app = Flask(__name__)

# Connect to Redis Client
hostname='redis-17795.c325.us-east-1-4.ec2.redns.redis-cloud.com'
port=17795
password='fLnGGZUuGeBFOSOo21yPBi8Z9B08AgZJ'

r = redis.StrictRedis(host=hostname,
                      port=port,
                      password=password)
name = 'attendance:logs'

def load_logs(name, end=-1):
    """Retrieve logs from Redis."""
    logs_list = r.lrange(name, start=0, end=end)
    return logs_list


def generate_report():
    """Generate attendance report as a DataFrame."""
    logs_list = load_logs(name=name)
    convert_byte_to_string = lambda x: x.decode('utf-8')
    logs_list_string = list(map(convert_byte_to_string, logs_list))
    split_string = lambda x: x.split('@')
    logs_nested_list = list(map(split_string, logs_list_string))

    # Convert nested list into dataframe
    logs_df = pd.DataFrame(logs_nested_list, columns=['Name', 'Role', 'Timestamp'])

    # Clean data and timestamps
    logs_df['Timestamp'] = logs_df['Timestamp'].apply(lambda x: x.split('.')[0])
    logs_df['Timestamp'] = pd.to_datetime(logs_df['Timestamp'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    logs_df['Date'] = logs_df['Timestamp'].dt.date

    # Calculate In-time and Out-time
    report_df = logs_df.groupby(by=['Date', 'Name', 'Role']).agg(
        In_time=pd.NamedAgg(column='Timestamp', aggfunc='min'), 
        Out_time=pd.NamedAgg(column='Timestamp', aggfunc='max')
    ).reset_index()

    report_df['In_time'] = pd.to_datetime(report_df['In_time'])
    report_df['Out_time'] = pd.to_datetime(report_df['Out_time'])

    # Calculate duration in hours
    report_df['Duration'] = report_df['Out_time'] - report_df['In_time']
    report_df['Duration_hours'] = report_df['Duration'].apply(lambda x: x.total_seconds() / 3600)

    # Generate attendance status
    def status_marker(duration_hours):
        if pd.isnull(duration_hours):
            return 'Absent'
        elif duration_hours < 1:
            return 'Absent (Less than 1 hr)'
        elif 1 <= duration_hours < 4:
            return 'Half Day (less than 4 hours)'
        elif 4 <= duration_hours < 6:
            return 'Half Day'
        else:
            return 'Present'

    report_df['Status'] = report_df['Duration_hours'].apply(status_marker)
    return report_df

@app.route('/')
def index():
    report_df = generate_report()
    attendance_data = report_df.to_dict(orient='records')
    return render_template('attendance.html', attendance_data=attendance_data)

@app.route('/staff')
def staff_view():
    report_df = generate_report()
    staff_report = report_df[report_df['Name'] == 'siva'].to_dict(orient='records')
    return render_template('staff_attendance.html', attendance_data=staff_report)

@app.route('/supervisor')
def supervisor_view():
    report_df = generate_report()

    # Ensure no extra spaces and convert to lowercase for uniform comparison
    report_df['Name'] = report_df['Name'].str.strip().str.lower()

    # Filter by Yuthika (convert name to lowercase for comparison)
    supervisor_report = report_df[report_df['Name'] == 'yuthika'].to_dict(orient='records')

    # Debug: Print the filtered DataFrame to see if records exist
    print(report_df[report_df['Name'] == 'yuthika'])

    return render_template('supervisor.html', attendance_data=supervisor_report)

@app.route('/allstaff')
def allstaff_view():
    report_df = generate_report()
    staff_report = report_df[report_df['Role'] == 'Staff'].to_dict(orient='records')
    return render_template('allstaff.html', attendance_data=staff_report)

@app.route('/manager')
def manager_view():
    report_df = generate_report()
    manager_report = report_df[report_df['Name'] == 'Bharathy'].to_dict(orient='records')
    return render_template('manager.html', attendance_data=manager_report)

@app.route('/allsupervisors')
def allsupervisors_view():
    report_df = generate_report()
    supervisors_report = report_df[report_df['Role'] == 'Supervisor'].to_dict(orient='records')
    return render_template('allsupervisor.html', attendance_data=supervisors_report)


if __name__ == '__main__':
    app.run(debug=True)
