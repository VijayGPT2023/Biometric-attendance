"""Biometric XLS parser - preserved from v1 (proven logic)."""
import os
import re
from datetime import datetime, date
import pandas as pd
from app.utils.helpers import normalize_dept


def parse_biometric_xls(filepath):
    """Parse a biometric attendance XLS/XLSX file.
    Returns: (employees_list, start_date, end_date)
    """
    ext = os.path.splitext(filepath)[1].lower()
    engine = 'xlrd' if ext == '.xls' else 'openpyxl'
    df = pd.read_excel(filepath, header=None, engine=engine)

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

        if col1.startswith('Department') or (col1.startswith('Dept:') and col1 != 'Dept.Time' and 'Dept.Time' not in col1):
            if ':-' in col1:
                current_dept = col1.split(':-', 1)[1].strip()
            elif ':' in col1:
                current_dept = col1.split(':', 1)[1].strip()
            else:
                current_dept = col1

            current_desig = ''
            for desig_col in [20, 15]:
                if desig_col < len(row):
                    desig_val = str(row.iloc[desig_col]).strip() if not pd.isna(row.iloc[desig_col]) else ''
                    if desig_val.startswith('Desig'):
                        current_desig = desig_val.split(':', 1)[1].strip() if ':' in desig_val else ''
                        break
            row_idx += 1
            continue

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

            daily_data = {}
            for day_num, col_idx in day_col_map.items():
                if start_date.month == end_date.month:
                    try:
                        d = date(start_date.year, start_date.month, day_num)
                    except ValueError:
                        continue
                else:
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

                raw_status = str(status_row.iloc[col_idx]).strip() if not pd.isna(status_row.iloc[col_idx]) else ''
                status = raw_status
                if raw_status in ('P-LT', 'POW'):
                    status = 'P'

                arrival = str(arrived_row.iloc[col_idx]).strip() if not pd.isna(arrived_row.iloc[col_idx]) else '00:00'
                departure = str(dept_row.iloc[col_idx]).strip() if not pd.isna(dept_row.iloc[col_idx]) else '00:00'
                working_hrs = str(working_row.iloc[col_idx]).strip() if not pd.isna(working_row.iloc[col_idx]) else '00:00'

                daily_data[d] = {
                    'status': status,
                    'raw_status': raw_status,
                    'arrival': arrival,
                    'departure': departure,
                    'working_hrs': working_hrs,
                }

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
                    'department': normalize_dept(current_dept),
                    'designation': current_desig,
                    'daily_data': daily_data,
                })

            row_idx += 9
        else:
            row_idx += 1

    return employees, start_date, end_date


def merge_multi_month(file_results):
    """Merge employees from multiple monthly files."""
    if len(file_results) == 1:
        return file_results[0]

    overall_start = min(r[1] for r in file_results)
    overall_end = max(r[2] for r in file_results)

    emp_map = {}
    for employees, _, _ in file_results:
        for emp in employees:
            code = emp['emp_code']
            if code not in emp_map:
                emp_map[code] = {
                    'emp_code': code,
                    'emp_name': emp['emp_name'],
                    'department': emp['department'],
                    'designation': emp['designation'],
                    'daily_data': {},
                }
            else:
                if emp['department'] and not emp_map[code]['department']:
                    emp_map[code]['department'] = emp['department']
                if emp['designation'] and not emp_map[code]['designation']:
                    emp_map[code]['designation'] = emp['designation']
                if len(emp['emp_name']) > len(emp_map[code]['emp_name']):
                    emp_map[code]['emp_name'] = emp['emp_name']

            emp_map[code]['daily_data'].update(emp['daily_data'])

    return list(emp_map.values()), overall_start, overall_end
