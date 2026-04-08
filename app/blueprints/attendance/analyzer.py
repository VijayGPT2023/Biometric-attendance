"""Attendance anomaly analyzer - preserved from v1 (proven logic)."""
from datetime import timedelta
from app.utils.helpers import parse_time, time_to_minutes, is_weekend


def analyze_employee(emp, start_date, end_date, late_threshold, early_threshold,
                     min_hours, allowed_anomalies, holidays=None, permitted_dates=None):
    """Analyze a single employee's attendance data.

    Args:
        emp: dict with emp_code, emp_name, department, designation, daily_data
        start_date, end_date: date range
        late_threshold: tuple (h, m) e.g. (10, 0)
        early_threshold: tuple (h, m) e.g. (17, 0)
        min_hours: float e.g. 8.0
        allowed_anomalies: int e.g. 2
        holidays: set of holiday dates
        permitted_dates: set of dates approved by HoD

    Returns: dict with all analysis results
    """
    holidays = holidays or set()
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
    missing_departure_days = []
    missing_arrival_days = []
    anomaly_dates = set()
    working_days_count = 0

    SINGLE_PUNCH_CUTOFF = time_to_minutes(14, 0)

    current = start_date
    while current <= end_date:
        is_wknd = is_weekend(current)
        is_hol = current in holidays
        data = daily.get(current)
        status = data['status'] if data else ''

        if is_wknd or is_hol:
            if status == 'P':
                present_on_holidays += 1
        else:
            working_days_count += 1
            if status == 'P':
                present_days += 1

                raw_arrival = parse_time(data['arrival']) if data else None
                raw_departure = parse_time(data['departure']) if data else None
                working = parse_time(data['working_hrs']) if data else None

                arrival = raw_arrival
                departure = raw_departure

                if raw_arrival and not raw_departure and not working:
                    punch_mins = time_to_minutes(*raw_arrival)
                    if punch_mins >= SINGLE_PUNCH_CUTOFF:
                        departure = raw_arrival
                        arrival = None
                        missing_arrival_days.append({
                            'date': current, 'punch_time': data['arrival'],
                            'interpreted_as': 'departure',
                        })
                        anomaly_dates.add(current)
                    else:
                        missing_departure_days.append({
                            'date': current, 'punch_time': data['arrival'],
                            'interpreted_as': 'arrival',
                        })
                        anomaly_dates.add(current)
                elif not raw_arrival and raw_departure and not working:
                    punch_mins = time_to_minutes(*raw_departure)
                    if punch_mins < SINGLE_PUNCH_CUTOFF:
                        arrival = raw_departure
                        departure = None
                        missing_departure_days.append({
                            'date': current, 'punch_time': data['departure'],
                            'interpreted_as': 'arrival',
                        })
                        anomaly_dates.add(current)
                    else:
                        missing_arrival_days.append({
                            'date': current, 'punch_time': data['departure'],
                            'interpreted_as': 'departure',
                        })
                        anomaly_dates.add(current)

                if arrival and time_to_minutes(*arrival) > late_threshold_mins:
                    late_arrival_days.append({'date': current, 'time': f"{arrival[0]:02d}:{arrival[1]:02d}"})
                    anomaly_dates.add(current)

                if departure and time_to_minutes(*departure) < early_threshold_mins:
                    early_departure_days.append({'date': current, 'time': f"{departure[0]:02d}:{departure[1]:02d}"})
                    anomaly_dates.add(current)

                if working:
                    if time_to_minutes(*working) < min_hours_mins:
                        short_hours_days.append({'date': current, 'hours': data['working_hrs']})
                        anomaly_dates.add(current)

            elif status == 'A':
                absent_days += 1

        current += timedelta(days=1)

    # Build anomaly details
    late_map = {item['date']: item['time'] for item in late_arrival_days}
    early_map = {item['date']: item['time'] for item in early_departure_days}
    short_map = {item['date']: item['hours'] for item in short_hours_days}
    miss_dep_map = {item['date']: item for item in missing_departure_days}
    miss_arr_map = {item['date']: item for item in missing_arrival_days}

    anomaly_details = []
    for ad in sorted(anomaly_dates):
        detail = {
            'date': ad, 'arrival': '', 'arrival_status': 'normal',
            'departure': '', 'departure_status': 'normal',
            'hours': '', 'hours_status': 'normal', 'types': [],
        }
        if ad in late_map:
            detail['arrival'] = late_map[ad]
            detail['arrival_status'] = 'late'
            detail['types'].append('Late Arrival')
        elif ad in miss_dep_map:
            detail['arrival'] = miss_dep_map[ad]['punch_time']
        elif ad in miss_arr_map:
            detail['arrival_status'] = 'missing'
        else:
            d_data = daily.get(ad)
            if d_data:
                arr = parse_time(d_data['arrival'])
                detail['arrival'] = d_data['arrival'] if arr else ''

        if ad in early_map:
            detail['departure'] = early_map[ad]
            detail['departure_status'] = 'early'
            detail['types'].append('Early Departure')
        elif ad in miss_arr_map:
            detail['departure'] = miss_arr_map[ad]['punch_time']
        elif ad in miss_dep_map:
            detail['departure_status'] = 'missing'
        else:
            d_data = daily.get(ad)
            if d_data:
                dep = parse_time(d_data['departure'])
                detail['departure'] = d_data['departure'] if dep else ''

        if ad in short_map:
            detail['hours'] = short_map[ad]
            detail['hours_status'] = 'short'
            detail['types'].append('Short Hours')
        elif ad in miss_dep_map or ad in miss_arr_map:
            detail['hours_status'] = 'missing'
        else:
            d_data = daily.get(ad)
            if d_data:
                wrk = parse_time(d_data['working_hrs'])
                detail['hours'] = d_data['working_hrs'] if wrk else ''

        if ad in miss_dep_map:
            detail['types'].append('Missing Dep. Punch')
        if ad in miss_arr_map:
            detail['types'].append('Missing Arr. Punch')

        anomaly_details.append(detail)

    effective_anomalies = anomaly_dates - permitted_dates
    total_anomalies = len(effective_anomalies)
    leave_deduction = max(0, (total_anomalies - allowed_anomalies) * 0.5)

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
