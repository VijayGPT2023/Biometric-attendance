import os
import re
import json
import uuid
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session
import pandas as pd

app = Flask(__name__)
app.secret_key = 'biometric-attendance-secret-key-2025'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['DATA_FOLDER'] = os.path.join(os.path.dirname(__file__), 'data')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DATA_FOLDER'], exist_ok=True)

# ---------- Delhi Central Government Public Holidays ----------
DELHI_CG_HOLIDAYS = {
    2024: [
        date(2024, 1, 26), date(2024, 3, 8), date(2024, 3, 25),
        date(2024, 3, 29), date(2024, 4, 11), date(2024, 4, 14),
        date(2024, 4, 17), date(2024, 4, 21), date(2024, 5, 23),
        date(2024, 6, 17), date(2024, 7, 17), date(2024, 8, 15),
        date(2024, 9, 16), date(2024, 10, 2), date(2024, 10, 12),
        date(2024, 11, 1), date(2024, 11, 15), date(2024, 12, 25),
    ],
    2025: [
        date(2025, 1, 26), date(2025, 2, 26), date(2025, 3, 14),
        date(2025, 3, 31), date(2025, 4, 6), date(2025, 4, 10),
        date(2025, 4, 14), date(2025, 4, 18), date(2025, 5, 12),
        date(2025, 6, 7), date(2025, 7, 6), date(2025, 8, 15),
        date(2025, 9, 5), date(2025, 10, 2), date(2025, 10, 20),
        date(2025, 11, 5), date(2025, 12, 25),
    ],
    2026: [
        date(2026, 1, 26), date(2026, 2, 16), date(2026, 3, 3),
        date(2026, 3, 20), date(2026, 3, 26), date(2026, 3, 30),
        date(2026, 4, 3), date(2026, 4, 14), date(2026, 5, 1),
        date(2026, 5, 27), date(2026, 6, 25), date(2026, 8, 15),
        date(2026, 8, 25), date(2026, 10, 2), date(2026, 10, 9),
        date(2026, 10, 19), date(2026, 10, 25), date(2026, 12, 25),
    ],
}
for year in DELHI_CG_HOLIDAYS:
    DELHI_CG_HOLIDAYS[year] = sorted(set(DELHI_CG_HOLIDAYS[year]))

HOLIDAY_NAMES = {
    date(2024, 1, 26): "Republic Day", date(2024, 3, 8): "Maha Shivaratri",
    date(2024, 3, 25): "Holi", date(2024, 3, 29): "Good Friday",
    date(2024, 4, 11): "Id-ul-Fitr", date(2024, 4, 14): "Dr. Ambedkar Jayanti",
    date(2024, 4, 17): "Ram Navami", date(2024, 4, 21): "Mahavir Jayanti",
    date(2024, 5, 23): "Buddha Purnima", date(2024, 6, 17): "Eid ul-Adha",
    date(2024, 7, 17): "Muharram", date(2024, 8, 15): "Independence Day",
    date(2024, 9, 16): "Milad-un-Nabi", date(2024, 10, 2): "Mahatma Gandhi Jayanti",
    date(2024, 10, 12): "Dussehra", date(2024, 11, 1): "Diwali",
    date(2024, 11, 15): "Guru Nanak Jayanti", date(2024, 12, 25): "Christmas",
    date(2025, 1, 26): "Republic Day", date(2025, 2, 26): "Maha Shivaratri",
    date(2025, 3, 14): "Holi", date(2025, 3, 31): "Id-ul-Fitr",
    date(2025, 4, 6): "Ram Navami", date(2025, 4, 10): "Mahavir Jayanti",
    date(2025, 4, 14): "Dr. Ambedkar Jayanti", date(2025, 4, 18): "Good Friday",
    date(2025, 5, 12): "Buddha Purnima", date(2025, 6, 7): "Eid ul-Adha",
    date(2025, 7, 6): "Muharram", date(2025, 8, 15): "Independence Day",
    date(2025, 9, 5): "Milad-un-Nabi",
    date(2025, 10, 2): "Mahatma Gandhi Jayanti / Dussehra",
    date(2025, 10, 20): "Diwali", date(2025, 11, 5): "Guru Nanak Jayanti",
    date(2025, 12, 25): "Christmas",
    date(2026, 1, 26): "Republic Day", date(2026, 2, 16): "Maha Shivaratri",
    date(2026, 3, 3): "Holi", date(2026, 3, 20): "Id-ul-Fitr",
    date(2026, 3, 26): "Ram Navami", date(2026, 3, 30): "Mahavir Jayanti",
    date(2026, 4, 3): "Good Friday", date(2026, 4, 14): "Dr. Ambedkar Jayanti",
    date(2026, 5, 1): "Buddha Purnima", date(2026, 5, 27): "Eid ul-Adha",
    date(2026, 6, 25): "Muharram", date(2026, 8, 15): "Independence Day",
    date(2026, 8, 25): "Milad-un-Nabi", date(2026, 10, 2): "Mahatma Gandhi Jayanti",
    date(2026, 10, 9): "Diwali", date(2026, 10, 19): "Dussehra",
    date(2026, 10, 25): "Guru Nanak Jayanti", date(2026, 12, 25): "Christmas",
}


# ---------- Utility functions ----------

def get_holidays_for_range(start_date, end_date):
    holidays = set()
    for year in range(start_date.year, end_date.year + 1):
        for h in DELHI_CG_HOLIDAYS.get(year, []):
            if start_date <= h <= end_date:
                holidays.add(h)
    return holidays


def get_holiday_names(start_date, end_date):
    return {d: name for d, name in HOLIDAY_NAMES.items() if start_date <= d <= end_date}


def is_weekend(d):
    return d.weekday() in (5, 6)


def parse_time(time_str):
    if pd.isna(time_str) or str(time_str).strip() in ('', '00:00', 'nan'):
        return None
    try:
        parts = str(time_str).strip().split(':')
        h, m = int(parts[0]), int(parts[1])
        if h == 0 and m == 0:
            return None
        return (h, m)
    except (ValueError, IndexError):
        return None


def time_to_minutes(h, m):
    return h * 60 + m


# ---------- XLS Parser ----------

def parse_biometric_xls(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    engine = 'xlrd' if ext == '.xls' else 'openpyxl'
    df = pd.read_excel(filepath, header=None, engine=engine)

    # Extract report date range
    report_info = str(df.iloc[0, 2]) if not pd.isna(df.iloc[0, 2]) else ''
    date_match = re.search(r'(\d{2}-\d{2}-\d{4})\s+To\s+:\s+(\d{2}-\d{2}-\d{4})', report_info)
    if date_match:
        start_date = datetime.strptime(date_match.group(1), '%d-%m-%Y').date()
        end_date = datetime.strptime(date_match.group(2), '%d-%m-%Y').date()
    else:
        start_date = end_date = None

    employees = []
    current_dept = ''
    current_desig = ''

    row_idx = 0
    while row_idx < len(df):
        row = df.iloc[row_idx]
        col1 = str(row.iloc[1]).strip() if not pd.isna(row.iloc[1]) else ''

        # Detect Department / Designation row (appears just before EmpCode row)
        if col1.startswith('Department'):
            current_dept = col1.split(':', 1)[1].strip() if ':' in col1 else ''
            col20 = str(row.iloc[20]).strip() if not pd.isna(row.iloc[20]) else ''
            current_desig = col20.split(':', 1)[1].strip() if ':' in col20 else ''
            row_idx += 1
            continue

        # Detect EmpCode header row
        if col1 == 'EmpCode':
            emp_row = df.iloc[row_idx + 1] if row_idx + 1 < len(df) else None
            if emp_row is None:
                row_idx += 1
                continue

            emp_code = str(emp_row.iloc[1]).strip()
            emp_name = str(emp_row.iloc[3]).strip()

            day_row = df.iloc[row_idx + 2] if row_idx + 2 < len(df) else None
            arrived_row = df.iloc[row_idx + 3] if row_idx + 3 < len(df) else None
            dept_row = df.iloc[row_idx + 4] if row_idx + 4 < len(df) else None
            working_row = df.iloc[row_idx + 5] if row_idx + 5 < len(df) else None
            status_row = df.iloc[row_idx + 7] if row_idx + 7 < len(df) else None

            if day_row is None or arrived_row is None or status_row is None:
                row_idx += 1
                continue

            # Build day-column mapping
            day_col_map = {}
            for col_idx in range(len(day_row)):
                val = day_row.iloc[col_idx]
                if not pd.isna(val):
                    try:
                        day_num = int(val)
                        if 1 <= day_num <= 31:
                            day_col_map[day_num] = col_idx
                    except (ValueError, TypeError):
                        pass

            # Extract daily data
            daily_data = {}
            for day_num, col_idx in day_col_map.items():
                # Handle multi-month reports
                if start_date.month == end_date.month:
                    try:
                        d = date(start_date.year, start_date.month, day_num)
                    except ValueError:
                        continue
                else:
                    # For multi-month, try to figure out which month
                    d = None
                    for m in range(start_date.month, end_date.month + 1):
                        try:
                            candidate = date(start_date.year, m, day_num)
                            if start_date <= candidate <= end_date:
                                d = candidate
                                break
                        except ValueError:
                            continue
                    if d is None:
                        continue

                if d < start_date or d > end_date:
                    continue

                status = str(status_row.iloc[col_idx]).strip() if not pd.isna(status_row.iloc[col_idx]) else ''
                arrival = str(arrived_row.iloc[col_idx]).strip() if not pd.isna(arrived_row.iloc[col_idx]) else '00:00'
                departure = str(dept_row.iloc[col_idx]).strip() if not pd.isna(dept_row.iloc[col_idx]) else '00:00'
                working_hrs = str(working_row.iloc[col_idx]).strip() if not pd.isna(working_row.iloc[col_idx]) else '00:00'

                daily_data[d] = {
                    'status': status,
                    'arrival': arrival,
                    'departure': departure,
                    'working_hrs': working_hrs,
                }

            # Filter out entries with no real name
            name_clean = emp_name.strip().lower()
            is_valid = (
                name_clean
                and name_clean != 'nan'
                and not name_clean.isdigit()
                and 'test' not in name_clean
            )
            if is_valid:
                employees.append({
                    'emp_code': emp_code,
                    'emp_name': emp_name,
                    'department': current_dept,
                    'designation': current_desig,
                    'daily_data': daily_data,
                })

            row_idx += 9
        else:
            row_idx += 1

    return employees, start_date, end_date


# ---------- Employee analysis ----------

def analyze_employee(emp, start_date, end_date, late_threshold, early_threshold,
                     min_hours, allowed_anomalies, permitted_dates=None):
    """Analyze a single employee. permitted_dates is a set of dates approved by HoD."""
    holidays = get_holidays_for_range(start_date, end_date)
    daily = emp['daily_data']
    permitted_dates = permitted_dates or set()

    late_threshold_mins = time_to_minutes(*late_threshold)
    early_threshold_mins = time_to_minutes(*early_threshold)
    min_hours_mins = min_hours * 60

    present_days = 0
    absent_days = 0
    present_on_holidays = 0
    late_arrival_days = []
    early_departure_days = []
    short_hours_days = []
    missing_departure_days = []  # punched in (before 2PM) but no exit punch
    missing_arrival_days = []    # punched out (after 2PM) but no entry punch
    anomaly_dates = set()
    working_days_count = 0

    # Cutoff: single punch before 2PM = arrival, after 2PM = departure
    SINGLE_PUNCH_CUTOFF = time_to_minutes(14, 0)

    current = start_date
    while current <= end_date:
        is_wknd = is_weekend(current)
        is_holiday = current in holidays
        data = daily.get(current)
        status = data['status'] if data else ''

        if is_wknd or is_holiday:
            if status == 'P':
                present_on_holidays += 1
        else:
            working_days_count += 1
            if status == 'P':
                present_days += 1

                raw_arrival = parse_time(data['arrival']) if data else None
                raw_departure = parse_time(data['departure']) if data else None
                working = parse_time(data['working_hrs']) if data else None

                # Determine actual arrival and departure
                # When only one punch exists (the other is 00:00) and no working hours:
                #   - If the recorded time < 2PM → it's an arrival (departure missing)
                #   - If the recorded time >= 2PM → it's a departure (arrival missing)
                arrival = raw_arrival
                departure = raw_departure

                if raw_arrival and not raw_departure and not working:
                    # Single punch in "Arrived" column — check if it's really arrival or departure
                    punch_mins = time_to_minutes(*raw_arrival)
                    if punch_mins >= SINGLE_PUNCH_CUTOFF:
                        # Actually a departure punch, arrival is missing
                        departure = raw_arrival
                        arrival = None
                        missing_arrival_days.append({
                            'date': current,
                            'punch_time': data['arrival'],
                            'interpreted_as': 'departure',
                        })
                        anomaly_dates.add(current)
                    else:
                        # It's an arrival punch, departure is missing
                        missing_departure_days.append({
                            'date': current,
                            'punch_time': data['arrival'],
                            'interpreted_as': 'arrival',
                        })
                        anomaly_dates.add(current)
                elif not raw_arrival and raw_departure and not working:
                    # Single punch in "Dept" column
                    punch_mins = time_to_minutes(*raw_departure)
                    if punch_mins < SINGLE_PUNCH_CUTOFF:
                        arrival = raw_departure
                        departure = None
                        missing_departure_days.append({
                            'date': current,
                            'punch_time': data['departure'],
                            'interpreted_as': 'arrival',
                        })
                        anomaly_dates.add(current)
                    else:
                        missing_arrival_days.append({
                            'date': current,
                            'punch_time': data['departure'],
                            'interpreted_as': 'departure',
                        })
                        anomaly_dates.add(current)

                # Check late arrival (only if we have an actual arrival)
                if arrival and time_to_minutes(*arrival) > late_threshold_mins:
                    late_arrival_days.append({'date': current, 'time': f"{arrival[0]:02d}:{arrival[1]:02d}"})
                    anomaly_dates.add(current)

                # Check early departure (only if we have an actual departure)
                if departure and time_to_minutes(*departure) < early_threshold_mins:
                    early_departure_days.append({'date': current, 'time': f"{departure[0]:02d}:{departure[1]:02d}"})
                    anomaly_dates.add(current)

                # Check short hours (only when working hours are actually recorded > 0)
                if working:
                    if time_to_minutes(*working) < min_hours_mins:
                        short_hours_days.append({'date': current, 'hours': data['working_hrs']})
                        anomaly_dates.add(current)

            elif status == 'A':
                absent_days += 1

        current += timedelta(days=1)

    # Build consolidated anomaly details per date
    # Lookup dicts for quick access
    late_map = {item['date']: item['time'] for item in late_arrival_days}
    early_map = {item['date']: item['time'] for item in early_departure_days}
    short_map = {item['date']: item['hours'] for item in short_hours_days}
    miss_dep_map = {item['date']: item for item in missing_departure_days}
    miss_arr_map = {item['date']: item for item in missing_arrival_days}

    anomaly_details = []
    for ad in sorted(anomaly_dates):
        detail = {
            'date': ad,
            'arrival': '',
            'arrival_status': 'normal',   # normal, late, missing
            'departure': '',
            'departure_status': 'normal', # normal, early, missing
            'hours': '',
            'hours_status': 'normal',     # normal, short, missing
            'types': [],
        }
        # Arrival
        if ad in late_map:
            detail['arrival'] = late_map[ad]
            detail['arrival_status'] = 'late'
            detail['types'].append('Late Arrival')
        elif ad in miss_dep_map:
            detail['arrival'] = miss_dep_map[ad]['punch_time']
            detail['arrival_status'] = 'normal'
        elif ad in miss_arr_map:
            detail['arrival'] = ''
            detail['arrival_status'] = 'missing'
        else:
            # Has both punches, arrival is within limit — get from daily data
            d_data = daily.get(ad)
            if d_data:
                arr = parse_time(d_data['arrival'])
                detail['arrival'] = d_data['arrival'] if arr else ''

        # Departure
        if ad in early_map:
            detail['departure'] = early_map[ad]
            detail['departure_status'] = 'early'
            detail['types'].append('Early Departure')
        elif ad in miss_arr_map:
            detail['departure'] = miss_arr_map[ad]['punch_time']
            detail['departure_status'] = 'normal'
        elif ad in miss_dep_map:
            detail['departure'] = ''
            detail['departure_status'] = 'missing'
        else:
            d_data = daily.get(ad)
            if d_data:
                dep = parse_time(d_data['departure'])
                detail['departure'] = d_data['departure'] if dep else ''

        # Hours
        if ad in short_map:
            detail['hours'] = short_map[ad]
            detail['hours_status'] = 'short'
            detail['types'].append('Short Hours')
        elif ad in miss_dep_map or ad in miss_arr_map:
            detail['hours'] = ''
            detail['hours_status'] = 'missing'
        else:
            d_data = daily.get(ad)
            if d_data:
                wrk = parse_time(d_data['working_hrs'])
                detail['hours'] = d_data['working_hrs'] if wrk else ''

        # Missing punch types
        if ad in miss_dep_map:
            detail['types'].append('Missing Dep. Punch')
        if ad in miss_arr_map:
            detail['types'].append('Missing Arr. Punch')

        anomaly_details.append(detail)

    # Remove permitted dates from anomalies
    effective_anomalies = anomaly_dates - permitted_dates
    total_anomalies = len(effective_anomalies)
    leave_deduction = max(0, total_anomalies - allowed_anomalies)

    return {
        'emp_code': emp['emp_code'],
        'emp_name': emp['emp_name'],
        'department': emp.get('department', ''),
        'designation': emp.get('designation', ''),
        'working_days': working_days_count,
        'present': present_days,
        'absent': absent_days,
        'present_on_holidays': present_on_holidays,
        'late_arrivals': late_arrival_days,
        'late_arrival_count': len(late_arrival_days),
        'early_departures': early_departure_days,
        'early_departure_count': len(early_departure_days),
        'short_hours': short_hours_days,
        'short_hours_count': len(short_hours_days),
        'missing_departure': missing_departure_days,
        'missing_departure_count': len(missing_departure_days),
        'missing_arrival': missing_arrival_days,
        'missing_arrival_count': len(missing_arrival_days),
        'anomaly_details': anomaly_details,
        'all_anomaly_dates': sorted(anomaly_dates),
        'total_anomaly_dates_raw': len(anomaly_dates),
        'permitted_dates': sorted(permitted_dates & anomaly_dates),
        'permitted_count': len(permitted_dates & anomaly_dates),
        'effective_anomaly_dates': sorted(effective_anomalies),
        'effective_anomaly_count': total_anomalies,
        'allowed_anomalies': allowed_anomalies,
        'leave_deduction': leave_deduction,
    }


# ---------- JSON serialization helpers ----------

def serialize_results(results, start_date, end_date, params):
    """Serialize analysis results to JSON-safe dict for storage."""
    data = {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'params': params,
        'employees': [],
    }
    for r in results:
        emp = dict(r)
        # Convert date objects to strings
        for key in ('late_arrivals', 'early_departures', 'short_hours', 'missing_departure', 'missing_arrival'):
            emp[key] = [{'date': item['date'].isoformat(), **{k: v for k, v in item.items() if k != 'date'}}
                        for item in emp[key]]
        for key in ('all_anomaly_dates', 'permitted_dates', 'effective_anomaly_dates'):
            emp[key] = [d.isoformat() for d in emp[key]]
        # anomaly_details
        emp['anomaly_details'] = [
            {**item, 'date': item['date'].isoformat()}
            for item in emp.get('anomaly_details', [])
        ]
        data['employees'].append(emp)
    return data


def deserialize_results(data):
    """Deserialize stored JSON back to results with date objects."""
    start_date = date.fromisoformat(data['start_date'])
    end_date = date.fromisoformat(data['end_date'])
    results = []
    for emp in data['employees']:
        r = dict(emp)
        for key in ('late_arrivals', 'early_departures', 'short_hours', 'missing_departure', 'missing_arrival'):
            r[key] = [{'date': date.fromisoformat(item['date']), **{k: v for k, v in item.items() if k != 'date'}}
                       for item in r.get(key, [])]
        for key in ('all_anomaly_dates', 'permitted_dates', 'effective_anomaly_dates'):
            r[key] = [date.fromisoformat(d) for d in r[key]]
        r['anomaly_details'] = [
            {**item, 'date': date.fromisoformat(item['date'])}
            for item in r.get('anomaly_details', [])
        ]
        results.append(r)
    return results, start_date, end_date, data['params']


# ---------- Routes ----------

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        flash('No file uploaded')
        return redirect(url_for('index'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('index'))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.xls', '.xlsx'):
        flash('Please upload an .xls or .xlsx file')
        return redirect(url_for('index'))

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    try:
        late_h, late_m = map(int, request.form.get('late_time', '10:00').split(':'))
        early_h, early_m = map(int, request.form.get('early_time', '17:00').split(':'))
        min_hours = float(request.form.get('min_hours', '8'))
        allowed_anomalies = int(request.form.get('allowed_anomalies', '2'))
    except (ValueError, TypeError):
        flash('Invalid parameter values')
        return redirect(url_for('index'))

    try:
        employees, start_date, end_date = parse_biometric_xls(filepath)
    except Exception as e:
        flash(f'Error parsing file: {str(e)}')
        return redirect(url_for('index'))

    if not employees:
        flash('No employee data found in the file')
        return redirect(url_for('index'))

    params = {
        'late_time': f"{late_h:02d}:{late_m:02d}",
        'early_time': f"{early_h:02d}:{early_m:02d}",
        'min_hours': min_hours,
        'allowed_anomalies': allowed_anomalies,
    }

    # Analyze each employee (Stage 1 — no permitted dates yet)
    results = []
    for emp in employees:
        result = analyze_employee(emp, start_date, end_date,
                                  (late_h, late_m), (early_h, early_m),
                                  min_hours, allowed_anomalies)
        results.append(result)

    # Save results to disk for Stage 2
    session_id = str(uuid.uuid4())
    serialized = serialize_results(results, start_date, end_date, params)
    # Also save raw employee data for re-analysis
    raw_employees = []
    for emp in employees:
        raw_emp = dict(emp)
        raw_emp['daily_data'] = {d.isoformat(): v for d, v in emp['daily_data'].items()}
        raw_employees.append(raw_emp)
    serialized['raw_employees'] = raw_employees

    data_path = os.path.join(app.config['DATA_FOLDER'], f"{session_id}.json")
    with open(data_path, 'w') as f:
        json.dump(serialized, f)

    try:
        os.remove(filepath)
    except OSError:
        pass

    holidays = get_holidays_for_range(start_date, end_date)
    holiday_names = get_holiday_names(start_date, end_date)

    # Group results by department
    dept_groups = group_by_department(results)

    return render_template('report.html',
                           dept_groups=dept_groups,
                           results=results,
                           start_date=start_date,
                           end_date=end_date,
                           params=params,
                           holidays=sorted(holidays),
                           holiday_names=holiday_names,
                           session_id=session_id,
                           stage='initial')


@app.route('/hod-review/<session_id>', methods=['GET'])
def hod_review(session_id):
    """Show HoD review page where permitted anomaly dates can be marked."""
    data_path = os.path.join(app.config['DATA_FOLDER'], f"{session_id}.json")
    if not os.path.exists(data_path):
        flash('Session expired or not found. Please upload again.')
        return redirect(url_for('index'))

    with open(data_path) as f:
        data = json.load(f)

    results, start_date, end_date, params = deserialize_results(data)
    dept_groups = group_by_department(results)

    # Get department filter from query params
    dept_filter = request.args.get('dept', '')

    holidays = get_holidays_for_range(start_date, end_date)
    holiday_names = get_holiday_names(start_date, end_date)

    return render_template('hod_review.html',
                           dept_groups=dept_groups,
                           results=results,
                           start_date=start_date,
                           end_date=end_date,
                           params=params,
                           holidays=sorted(holidays),
                           holiday_names=holiday_names,
                           session_id=session_id,
                           dept_filter=dept_filter)


@app.route('/hod-submit/<session_id>', methods=['POST'])
def hod_submit(session_id):
    """Process HoD feedback and generate final report."""
    data_path = os.path.join(app.config['DATA_FOLDER'], f"{session_id}.json")
    if not os.path.exists(data_path):
        flash('Session expired or not found. Please upload again.')
        return redirect(url_for('index'))

    with open(data_path) as f:
        data = json.load(f)

    params = data['params']
    start_date = date.fromisoformat(data['start_date'])
    end_date = date.fromisoformat(data['end_date'])
    late_h, late_m = map(int, params['late_time'].split(':'))
    early_h, early_m = map(int, params['early_time'].split(':'))

    # Reconstruct raw employees
    raw_employees = []
    for raw_emp in data['raw_employees']:
        emp = dict(raw_emp)
        emp['daily_data'] = {date.fromisoformat(k): v for k, v in raw_emp['daily_data'].items()}
        raw_employees.append(emp)

    # Collect permitted dates per employee from form
    permitted_map = {}  # emp_code -> set of dates
    for key, value in request.form.items():
        # Format: permit_EMPCODE_YYYY-MM-DD
        if key.startswith('permit_'):
            parts = key.split('_', 2)
            if len(parts) == 3:
                emp_code = parts[1]
                try:
                    permitted_date = date.fromisoformat(parts[2])
                    if emp_code not in permitted_map:
                        permitted_map[emp_code] = set()
                    permitted_map[emp_code].add(permitted_date)
                except ValueError:
                    pass

    # Re-analyze with permitted dates
    results = []
    for emp in raw_employees:
        permitted = permitted_map.get(emp['emp_code'], set())
        result = analyze_employee(emp, start_date, end_date,
                                  (late_h, late_m), (early_h, early_m),
                                  params['min_hours'], params['allowed_anomalies'],
                                  permitted_dates=permitted)
        results.append(result)

    holidays = get_holidays_for_range(start_date, end_date)
    holiday_names = get_holiday_names(start_date, end_date)
    dept_groups = group_by_department(results)

    return render_template('report.html',
                           dept_groups=dept_groups,
                           results=results,
                           start_date=start_date,
                           end_date=end_date,
                           params=params,
                           holidays=sorted(holidays),
                           holiday_names=holiday_names,
                           session_id=session_id,
                           stage='final')


@app.route('/dept-report/<session_id>/<dept_name>')
def dept_report(session_id, dept_name):
    """Printable report for a single department — to send to HoD."""
    data_path = os.path.join(app.config['DATA_FOLDER'], f"{session_id}.json")
    if not os.path.exists(data_path):
        flash('Session expired or not found.')
        return redirect(url_for('index'))

    with open(data_path) as f:
        data = json.load(f)

    results, start_date, end_date, params = deserialize_results(data)
    dept_results = [r for r in results if r['department'] == dept_name]

    holidays = get_holidays_for_range(start_date, end_date)
    holiday_names = get_holiday_names(start_date, end_date)

    return render_template('dept_report.html',
                           dept_name=dept_name,
                           results=dept_results,
                           start_date=start_date,
                           end_date=end_date,
                           params=params,
                           holidays=sorted(holidays),
                           holiday_names=holiday_names,
                           session_id=session_id)


def group_by_department(results):
    """Group results by department, sorted by department name."""
    groups = {}
    for r in results:
        dept = r['department'] or 'Unknown'
        if dept not in groups:
            groups[dept] = []
        groups[dept].append(r)
    return dict(sorted(groups.items()))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)
