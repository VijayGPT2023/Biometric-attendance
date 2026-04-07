import os
import re
import json
import uuid
import sqlite3
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, session, g, jsonify)
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'biometric-attendance-secret-key-2025')

# Use RAILWAY_VOLUME_MOUNT_PATH for persistent storage on Railway, else local
PERSIST_DIR = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', os.path.dirname(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(PERSIST_DIR, 'uploads')
app.config['DATA_FOLDER'] = os.path.join(PERSIST_DIR, 'data')
app.config['DATABASE'] = os.path.join(PERSIST_DIR, 'biometric.db')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DATA_FOLDER'], exist_ok=True)


# ================================================================
#  DEPARTMENT NAME NORMALIZATION
# ================================================================

DEPT_NAME_MAP = {
    'AB':                           'AB Group',
    'AB Group':                     'AB Group',
    'ADMIN':                        'Admin',
    'Admin':                        'Admin',
    'Housekeeping Agency (Admin)':  'Admin',
    'MTS Agency (Admin)':           'Admin',
    'DG SECRETRIAT':                'DG Sectt',
    'DG Sectt':                     'DG Sectt',
    'EC':                           'ECA Group',
    'ECA':                          'ECA Group',
    'ECA Group':                    'ECA Group',
    'ECAJ':                         'ECA Group',
    'EN':                           'ECA Group',
    'EM':                           'EM Group',
    'EM Group':                     'EM Group',
    'ES':                           'ES Group',
    'ES Group':                     'ES Group',
    'FIN.':                         'Finance',
    'Finance':                      'Finance',
    'HQ':                           'HQ',
    'HRM':                          'HRM Group',
    'HRM Group':                    'HRM Group',
    'IE GROUP':                     'IE Group',
    'IE Group':                     'IE Group',
    'IS':                           'IS Group',
    'IS Group':                     'IS Group',
    'IT':                           'IT Group',
    'IT Group':                     'IT Group',
}


def normalize_dept(name):
    """Normalize department name using the mapping."""
    return DEPT_NAME_MAP.get(name.strip(), name.strip()) if name else 'Unknown'


# ================================================================
#  DATABASE
# ================================================================

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config['DATABASE'])
    db.execute('PRAGMA foreign_keys = ON')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS head_departments (
            user_id INTEGER NOT NULL,
            dept_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, dept_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (dept_id) REFERENCES departments(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS upload_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_uuid TEXT UNIQUE NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            params_json TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS justifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_uuid TEXT NOT NULL,
            emp_code TEXT NOT NULL,
            anomaly_date TEXT NOT NULL,
            anomaly_types TEXT DEFAULT '',
            justification TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            head_remark TEXT DEFAULT '',
            admin_remark TEXT DEFAULT '',
            finalized INTEGER DEFAULT 0,
            final_decision TEXT DEFAULT '',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(session_uuid, emp_code, anomaly_date)
        );
    ''')
    # Create default admin user if not exists
    existing = db.execute('SELECT id FROM users WHERE emp_code = ?', ('admin',)).fetchone()
    if not existing:
        db.execute(
            'INSERT INTO users (emp_code, name, password_hash, role, username) VALUES (?, ?, ?, ?, ?)',
            ('admin', 'Administrator', generate_password_hash('admin123'), 'admin', 'admin'))
        db.commit()
        seed_users(db)
    db.close()


def seed_users(db):
    """Auto-seed all employees, departments, and head accounts on first startup."""
    pw = generate_password_hash('npc123')

    # --- Canonical departments ---
    CANONICAL_DEPTS = [
        'AB Group', 'Admin', 'DG Sectt', 'ECA Group', 'EM Group',
        'ES Group', 'Finance', 'HQ', 'HRM Group', 'IE Group', 'IS Group', 'IT Group'
    ]
    for dept in CANONICAL_DEPTS:
        db.execute('INSERT OR IGNORE INTO departments (name) VALUES (?)', (dept,))
    db.commit()
    dept_id_map = {r[1]: r[0] for r in db.execute('SELECT id, name FROM departments').fetchall()}

    # --- Position-based head accounts ---
    # DG, DDG-I, DDG-II -> ALL DEPARTMENTS
    top_roles = [
        ('DG',     'Director General', 'dg'),
        ('DDG-I',  'DDG-I',            'ddg1'),
        ('DDG-II', 'DDG-II',           'ddg2'),
    ]
    all_dept_ids = list(dept_id_map.values())
    for emp_code, name, username in top_roles:
        db.execute('INSERT OR IGNORE INTO users (emp_code, name, password_hash, role, username) VALUES (?, ?, ?, ?, ?)',
                   (emp_code, name, pw, 'head', username))
        uid = db.execute('SELECT id FROM users WHERE emp_code = ?', (emp_code,)).fetchone()[0]
        for did in all_dept_ids:
            db.execute('INSERT OR IGNORE INTO head_departments (user_id, dept_id) VALUES (?, ?)', (uid, did))

    # GH accounts -> specific departments
    gh_accounts = [
        ('GH-AB',    'GH AB Group',    'gh.abgroup',   ['AB Group']),
        ('GH-ADMIN', 'GH Admin',       'gh.admin',     ['Admin', 'DG Sectt', 'HQ']),
        ('GH-ECA',   'GH ECA Group',   'gh.ecagroup',  ['ECA Group', 'IS Group']),
        ('GH-EM',    'GH EM Group',    'gh.emgroup',   ['EM Group']),
        ('GH-ES',    'GH ES Group',    'gh.esgroup',   ['ES Group']),
        ('GH-FIN',   'GH Finance',     'gh.finance',   ['Finance']),
        ('GH-HRM',   'GH HRM Group',   'gh.hrmgroup',  ['HRM Group']),
        ('GH-IE',    'GH IE Group',    'gh.iegroup',   ['IE Group']),
        ('GH-IT',    'GH IT Group',    'gh.itgroup',   ['IT Group']),
    ]
    for emp_code, name, username, dept_names in gh_accounts:
        db.execute('INSERT OR IGNORE INTO users (emp_code, name, password_hash, role, username) VALUES (?, ?, ?, ?, ?)',
                   (emp_code, name, pw, 'head', username))
        uid = db.execute('SELECT id FROM users WHERE emp_code = ?', (emp_code,)).fetchone()[0]
        for dn in dept_names:
            if dn in dept_id_map:
                db.execute('INSERT OR IGNORE INTO head_departments (user_id, dept_id) VALUES (?, ?)',
                           (uid, dept_id_map[dn]))

    # --- Employee accounts (Jan-Mar 2026 data) ---
    EMPLOYEES = [
        ('00000097', 'Aman Gulati',             'IE Group'),
        ('00000099', 'Nakul',                   'AB Group'),
        ('00000101', 'Md. Khalid Anwar',        'Admin'),
        ('00000103', 'Mahotsav Priya',          'ECA Group'),
        ('00000105', 'Raj Kumar',               'Admin'),
        ('00000111', 'Amit Dabas',              'DG Sectt'),
        ('00000113', 'Raj Kumar Rawat',         'ECA Group'),
        ('00000116', 'M.M. Senghal',            'Finance'),
        ('00000120', 'Nand Kishor',             'Admin'),
        ('00000123', 'Tukeshwar Yadav',         'EM Group'),
        ('00000124', 'Chadra Prakash',          'EM Group'),
        ('00000130', 'Shivani Maurya',          'IS Group'),
        ('00000132', 'Shivam Kumar',            'ECA Group'),
        ('00000133', 'Sai Shankar G Nair',      'ECA Group'),
        ('00000135', 'Deepika Goswami',         'HRM Group'),
        ('00000136', 'Sankriti Thakur',         'ES Group'),
        ('00000138', 'Shukla Pal Maitra',       'ECA Group'),
        ('00000139', 'Saurabh Singh',           'AB Group'),
        ('00000140', 'Sandeep Aka',             'IE Group'),
        ('00000141', 'Pradeep Kumar',           'Admin'),
        ('00000142', 'Vikas',                   'Admin'),
        ('00000143', 'Mahender',                'Admin'),
        ('00000144', 'Shashank Srivastava',     'EM Group'),
        ('00000145', 'Rachna',                  'DG Sectt'),
        ('00000146', 'S N Rao',                 'Admin'),
        ('00000147', 'Ramesh Kumar',            'Admin'),
        ('00000148', 'K K Sharma',              'Admin'),
        ('00000149', 'Diwakar',                 'Admin'),
        ('00000152', 'Mohd Asim',               'Admin'),
        ('00000153', 'C N Dubey',               'Admin'),
        ('00000158', 'Uday Bhan Yadav',         'Admin'),
        ('00000159', 'Chaman Kumar Shukla',     'EM Group'),
        ('00000160', 'Vijay Kumar',             'Admin'),
        ('00000161', 'Akash Bhartiya',          'ECA Group'),
        ('00000162', 'Ronak',                   'ECA Group'),
        ('00000163', 'Dr Rajat Sharma',         'Admin'),
        ('00000164', 'Geetika Sharma',          'IT Group'),
        ('00000165', 'Rachana Shalini',         'Admin'),
        ('00000166', 'Kritika Garg',            'IE Group'),
        ('00000167', 'Tanaya Kapila',           'IE Group'),
        ('00000168', 'Dipti Rawat',             'IE Group'),
        ('00000169', 'Durgesh Verma',           'IE Group'),
        ('00000170', 'Purnika',                 'IE Group'),
        ('00000181', 'Naveen',                  'IE Group'),
        ('00000182', 'Yatish',                  'IE Group'),
        ('00000183', 'Bikash Kumar',            'IE Group'),
        ('00000184', 'P Ganesh Patro',          'Admin'),
        ('00000185', 'Chanchal Soni',           'IE Group'),
        ('00000186', 'Anita Singh',             'Admin'),
        ('00000187', 'Shahzad',                 'Admin'),
        ('00000188', 'Ayushman Shukla',         'Admin'),
        ('00000189', 'Mayank Mishra',           'Admin'),
        ('1',        'Malkhan Singh',           'Admin'),
        ('2',        'Nidhi',                   'Admin'),
        ('3',        'Sandeep Kumar Gupta',     'Admin'),
        ('5',        'Pooja Nag',               'Admin'),
        ('6',        'Yadu Kumar Yadav',        'Admin'),
        ('S007',     'Abhishek',                'Admin'),
        ('S008',     'Rohtas',                  'Admin'),
        ('S009',     'Gushneer',                'IE Group'),
        ('S010',     'Om Pal',                  'Finance'),
        ('S011',     'Bijender',                'HQ'),
        ('S012',     'Vikas Kumar Nehra',       'HRM Group'),
        ('S013',     'Sourabh Yadav',           'AB Group'),
        ('S014',     'Deepak',                  'Finance'),
        ('S015',     'Ganesh Deen',             'Admin'),
        ('S016',     'Abhishek',                'IT Group'),
        ('S017',     'Vijay Kr. Nehra',         'ECA Group'),
        ('S018',     'Sourabh Mittal',          'Admin'),
        ('S019',     'Ashok Kr.',               'Admin'),
        ('S020',     'Shurveer Singh',          'Admin'),
        ('S021',     'Arun Kaushik',            'Finance'),
        ('S022',     'Nitin',                   'Admin'),
        ('S023',     'Suraj Bhan',              'Admin'),
        ('S024',     'Rajiv Bihari',            'Finance'),
        ('S025',     'Shashi Ranjan',           'IS Group'),
        ('S026',     'Amitava Ray',             'Admin'),
        ('S027',     'Anup',                    'Admin'),
        ('S028',     'Neeraj',                  'Finance'),
        ('S029',     'Rekha Kumari',            'ES Group'),
        ('S030',     'Heeralal Mehto',          'ECA Group'),
        ('S031',     'T.D Pandey',              'DG Sectt'),
        ('S032',     'Gopi Nath',               'Finance'),
        ('S033',     'Sweta',                   'Finance'),
        ('S034',     'Moh. Kadir',              'Finance'),
        ('S035',     'Mahender Deep Kaur',      'Finance'),
        ('S036',     'Dharam Veer',             'Finance'),
        ('S037',     'Pinky',                   'Finance'),
        ('S038',     'Jai Karan',               'Admin'),
        ('S039',     'Ashutosh Makup',          'IE Group'),
        ('S040',     'Makan Singh Negi',        'IE Group'),
        ('S041',     'Saroj',                   'IE Group'),
        ('S042',     'Dayavati',                'IE Group'),
        ('S043',     'Sanjeev Bhatia',          'DG Sectt'),
        ('S044',     'Sunil Kumar Jha',         'AB Group'),
        ('S045',     'Rashid',                  'Finance'),
        ('S046',     'Sidharth Pal',            'IE Group'),
        ('S047',     'S.P Singh',               'AB Group'),
        ('S048',     'Kumud Jacob',             'IE Group'),
        ('S049',     'Sunil Kr.',               'AB Group'),
        ('S050',     'Om Prakash',              'Admin'),
        ('S051',     'Ashish',                  'AB Group'),
        ('S052',     'Binko',                   'AB Group'),
        ('S053',     'Hemant Kr.',              'AB Group'),
        ('S054',     'Bajrang',                 'AB Group'),
        ('S055',     'D.K Rahul',               'HRM Group'),
        ('S056',     'Rajesh Chand Katoch',     'ES Group'),
        ('S057',     'Urmila',                  'Admin'),
        ('S058',     'Lalit Shankar Kamde',     'ECA Group'),
        ('S059',     'Abhinav Mishra',          'Admin'),
        ('S060',     'Anand Verma',             'EM Group'),
        ('S061',     'Asmita Raj',              'HRM Group'),
        ('S062',     'Rajendra Paswan',         'ES Group'),
        ('S063',     'Tribhuvan',               'ECA Group'),
        ('S064',     'B. Prabhakar',            'IE Group'),
        ('S065',     'Hemant',                  'ECA Group'),
        ('S066',     'Nikita',                  'ECA Group'),
        ('S067',     'Rajesh Sund',             'ES Group'),
        ('S068',     'Santosh Kumar',           'IT Group'),
        ('S069',     'Shabnam',                 'ECA Group'),
        ('S070',     'Anupam Saini',            'IS Group'),
        ('S071',     'Nikhil Negi',             'Finance'),
        ('S072',     'Rajiv Gupta',             'IT Group'),
        ('S073',     'Devender Laun',           'IE Group'),
        ('S074',     'Sita Sharan Jha',         'ES Group'),
        ('S075',     'Jitendra Kr. Srivastava', 'EM Group'),
        ('S076',     'Naman Upadhyay',          'IE Group'),
        ('S077',     'S.P Tripathi',            'HRM Group'),
        ('S078',     'Ashish Prabhash Bhandwalkar', 'ECA Group'),
        ('S079',     'Sanjay Kr. Triwedi',      'IE Group'),
        ('S080',     'Ashmita',                 'IT Group'),
        ('S081',     'Manoj Kr. Acharya',       'Admin'),
        ('S082',     'Samdhani',                'HRM Group'),
        ('S083',     'Saurabh Sharma',          'Admin'),
        ('S084',     'Kritika Shukla',          'HRM Group'),
        ('S085',     'Bhuvan',                  'IS Group'),
        ('S086',     'Nitin Agarwal',           'ES Group'),
        ('S087',     'Nisha',                   'Admin'),
        ('S088',     'Vinod Kr. Singh',         'Admin'),
        ('S089',     'Manish Meena',            'EM Group'),
        ('S090',     'Prashant Srivastava',     'EM Group'),
        ('S091',     'Abhishek',                'EM Group'),
        ('S092',     'Harsh Thukral',           'ECA Group'),
        ('S093',     'N.H Panchbhai',           'IT Group'),
        ('S094',     'Shirish Paliwal',         'IE Group'),
        ('S095',     'K.D Bhardwaj',            'ECA Group'),
        ('S106',     'Suresh Kumar',            'Admin'),
    ]

    def make_username(name):
        clean = name.strip()
        for prefix in ['Mr. ', 'Mr ', 'Mrs. ', 'Dr. ', 'Dr ', 'Sh. ', 'Sh ']:
            if clean.lower().startswith(prefix.lower()):
                clean = clean[len(prefix):]
        parts = [p.strip().lower().replace('.', '').replace(',', '') for p in clean.split() if p.strip()]
        parts = [p for p in parts if p]
        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        first, last = parts[0], parts[-1]
        if len(first) <= 2 and len(parts) > 2:
            first = parts[1]
        return f'{first}.{last}'

    used = {'admin', 'dg', 'ddg1', 'ddg2',
            'gh.abgroup', 'gh.admin', 'gh.ecagroup', 'gh.emgroup',
            'gh.esgroup', 'gh.finance', 'gh.hrmgroup', 'gh.iegroup', 'gh.itgroup'}

    for emp_code, name, dept in EMPLOYEES:
        uname = make_username(name) or emp_code.lower()
        base = uname
        counter = 2
        while uname in used:
            uname = f'{base}{counter}'
            counter += 1
        used.add(uname)
        db.execute(
            'INSERT OR IGNORE INTO users (emp_code, name, password_hash, role, username) VALUES (?, ?, ?, ?, ?)',
            (emp_code, name, pw, 'employee', uname))

    db.commit()


# ================================================================
#  AUTH DECORATORS
# ================================================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if session.get('role') not in roles:
                flash('Access denied.')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ================================================================
#  DELHI CENTRAL GOVERNMENT PUBLIC HOLIDAYS
# ================================================================

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


# ================================================================
#  UTILITY FUNCTIONS
# ================================================================

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


# ================================================================
#  XLS PARSER
# ================================================================

def parse_biometric_xls(filepath):
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


# ================================================================
#  EMPLOYEE ANALYSIS
# ================================================================

def analyze_employee(emp, start_date, end_date, late_threshold, early_threshold,
                     min_hours, allowed_anomalies, permitted_dates=None):
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
    missing_departure_days = []
    missing_arrival_days = []
    anomaly_dates = set()
    working_days_count = 0

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

                arrival = raw_arrival
                departure = raw_departure

                if raw_arrival and not raw_departure and not working:
                    punch_mins = time_to_minutes(*raw_arrival)
                    if punch_mins >= SINGLE_PUNCH_CUTOFF:
                        departure = raw_arrival
                        arrival = None
                        missing_arrival_days.append({
                            'date': current,
                            'punch_time': data['arrival'],
                            'interpreted_as': 'departure',
                        })
                        anomaly_dates.add(current)
                    else:
                        missing_departure_days.append({
                            'date': current,
                            'punch_time': data['arrival'],
                            'interpreted_as': 'arrival',
                        })
                        anomaly_dates.add(current)
                elif not raw_arrival and raw_departure and not working:
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
            'date': ad,
            'arrival': '',
            'arrival_status': 'normal',
            'departure': '',
            'departure_status': 'normal',
            'hours': '',
            'hours_status': 'normal',
            'types': [],
        }
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
            detail['departure_status'] = 'normal'
        elif ad in miss_dep_map:
            detail['departure'] = ''
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
            detail['hours'] = ''
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
    # Leave deduction: 0.5 EL per anomaly day beyond allowed count
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


# ================================================================
#  JSON SERIALIZATION HELPERS
# ================================================================

def serialize_results(results, start_date, end_date, params):
    data = {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'params': params,
        'employees': [],
    }
    for r in results:
        emp = dict(r)
        for key in ('late_arrivals', 'early_departures', 'short_hours',
                     'missing_departure', 'missing_arrival'):
            emp[key] = [{'date': item['date'].isoformat(),
                         **{k: v for k, v in item.items() if k != 'date'}}
                        for item in emp[key]]
        for key in ('all_anomaly_dates', 'permitted_dates', 'effective_anomaly_dates'):
            emp[key] = [d.isoformat() for d in emp[key]]
        emp['anomaly_details'] = [
            {**item, 'date': item['date'].isoformat()}
            for item in emp.get('anomaly_details', [])
        ]
        data['employees'].append(emp)
    return data


def deserialize_results(data):
    start_date = date.fromisoformat(data['start_date'])
    end_date = date.fromisoformat(data['end_date'])
    results = []
    for emp in data['employees']:
        r = dict(emp)
        for key in ('late_arrivals', 'early_departures', 'short_hours',
                     'missing_departure', 'missing_arrival'):
            r[key] = [{'date': date.fromisoformat(item['date']),
                        **{k: v for k, v in item.items() if k != 'date'}}
                       for item in r.get(key, [])]
        for key in ('all_anomaly_dates', 'permitted_dates', 'effective_anomaly_dates'):
            r[key] = [date.fromisoformat(d) for d in r[key]]
        r['anomaly_details'] = [
            {**item, 'date': date.fromisoformat(item['date'])}
            for item in r.get('anomaly_details', [])
        ]
        results.append(r)
    return results, start_date, end_date, data['params']


def group_by_department(results):
    groups = {}
    for r in results:
        dept = r['department'] or 'Unknown'
        if dept not in groups:
            groups[dept] = []
        groups[dept].append(r)
    return dict(sorted(groups.items()))


# ================================================================
#  HELPER: populate justification rows after upload
# ================================================================

def populate_justifications(session_uuid, results):
    """Create one justification row per anomaly date per employee."""
    db = get_db()
    for r in results:
        for detail in r.get('anomaly_details', []):
            d = detail['date']
            date_str = d.isoformat() if isinstance(d, date) else d
            types_str = ', '.join(detail.get('types', []))
            db.execute('''
                INSERT OR IGNORE INTO justifications
                    (session_uuid, emp_code, anomaly_date, anomaly_types, status)
                VALUES (?, ?, ?, ?, 'pending')
            ''', (session_uuid, r['emp_code'], date_str, types_str))
    db.commit()


def auto_create_departments(results):
    """Auto-create department records from XLS data."""
    db = get_db()
    depts = set()
    for r in results:
        dept = r.get('department', '').strip()
        if dept and dept != 'Unknown':
            depts.add(dept)
    for dept in depts:
        db.execute('INSERT OR IGNORE INTO departments (name) VALUES (?)', (dept,))
    db.commit()


# ================================================================
#  AUTH ROUTES
# ================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_id = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        db = get_db()
        # Try username first, then emp_code as fallback
        user = db.execute(
            'SELECT * FROM users WHERE (LOWER(username) = ? OR emp_code = ?) AND is_active = 1',
            (login_id, login_id)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['emp_code'] = user['emp_code']
            session['user_name'] = user['name']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        flash('Invalid Username or Password')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def dashboard():
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'head':
        return redirect(url_for('head_dashboard'))
    else:
        return redirect(url_for('employee_dashboard'))


# ================================================================
#  ADMIN ROUTES
# ================================================================

@app.route('/admin')
@role_required('admin')
def admin_dashboard():
    db = get_db()
    sessions = db.execute(
        'SELECT * FROM upload_sessions ORDER BY created_at DESC').fetchall()
    users = db.execute('SELECT * FROM users ORDER BY role, name').fetchall()
    departments = db.execute('SELECT * FROM departments ORDER BY name').fetchall()
    return render_template('admin_dashboard.html',
                           sessions=sessions, users=users, departments=departments)


@app.route('/admin/upload', methods=['POST'])
@role_required('admin')
def admin_upload():
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        flash('No file uploaded')
        return redirect(url_for('admin_dashboard'))

    try:
        late_h, late_m = map(int, request.form.get('late_time', '10:00').split(':'))
        early_h, early_m = map(int, request.form.get('early_time', '17:00').split(':'))
        min_hours = float(request.form.get('min_hours', '8'))
        allowed_anomalies = int(request.form.get('allowed_anomalies', '2'))
    except (ValueError, TypeError):
        flash('Invalid parameter values')
        return redirect(url_for('admin_dashboard'))

    file_results = []
    saved_paths = []
    for file in files:
        if file.filename == '':
            continue
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ('.xls', '.xlsx'):
            flash(f'Skipped {file.filename} — not an .xls/.xlsx file')
            continue
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        saved_paths.append(filepath)
        try:
            emps, sd, ed = parse_biometric_xls(filepath)
            if emps and sd and ed:
                file_results.append((emps, sd, ed))
        except Exception as e:
            flash(f'Error parsing {file.filename}: {str(e)}')

    for fp in saved_paths:
        try:
            os.remove(fp)
        except OSError:
            pass

    if not file_results:
        flash('No valid employee data found in the uploaded file(s)')
        return redirect(url_for('admin_dashboard'))

    employees, start_date, end_date = merge_multi_month(file_results)

    params = {
        'late_time': f"{late_h:02d}:{late_m:02d}",
        'early_time': f"{early_h:02d}:{early_m:02d}",
        'min_hours': min_hours,
        'allowed_anomalies': allowed_anomalies,
    }

    results = []
    for emp in employees:
        result = analyze_employee(emp, start_date, end_date,
                                  (late_h, late_m), (early_h, early_m),
                                  min_hours, allowed_anomalies)
        results.append(result)

    session_id = str(uuid.uuid4())
    serialized = serialize_results(results, start_date, end_date, params)
    raw_employees = []
    for emp in employees:
        raw_emp = dict(emp)
        raw_emp['daily_data'] = {d.isoformat(): v for d, v in emp['daily_data'].items()}
        raw_employees.append(raw_emp)
    serialized['raw_employees'] = raw_employees

    data_path = os.path.join(app.config['DATA_FOLDER'], f"{session_id}.json")
    with open(data_path, 'w') as f:
        json.dump(serialized, f)

    # Save to database
    db = get_db()
    db.execute('''
        INSERT INTO upload_sessions (session_uuid, start_date, end_date, params_json)
        VALUES (?, ?, ?, ?)
    ''', (session_id, start_date.isoformat(), end_date.isoformat(), json.dumps(params)))
    db.commit()

    # Auto-create departments and justification rows
    auto_create_departments(results)
    populate_justifications(session_id, results)

    flash(f'Analysis complete! {len(results)} employees across {len(group_by_department(results))} departments.')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/report/<session_uuid>')
@role_required('admin')
def admin_report(session_uuid):
    """View the full printable report (same as before)."""
    data_path = os.path.join(app.config['DATA_FOLDER'], f"{session_uuid}.json")
    if not os.path.exists(data_path):
        flash('Session not found.')
        return redirect(url_for('admin_dashboard'))

    with open(data_path) as f:
        data = json.load(f)

    results, start_date, end_date, params = deserialize_results(data)

    # Apply finalized decisions: excluded anomalies act as permitted dates
    db = get_db()
    for r in results:
        excluded = db.execute('''
            SELECT anomaly_date FROM justifications
            WHERE session_uuid = ? AND emp_code = ? AND finalized = 1
                  AND final_decision = 'excluded'
        ''', (session_uuid, r['emp_code'])).fetchall()
        excluded_dates = {date.fromisoformat(row['anomaly_date']) for row in excluded}
        if excluded_dates:
            r['permitted_dates'] = sorted(excluded_dates & set(r['all_anomaly_dates']))
            r['permitted_count'] = len(r['permitted_dates'])
            effective = set(r['all_anomaly_dates']) - excluded_dates
            r['effective_anomaly_count'] = len(effective)
            r['effective_anomaly_dates'] = sorted(effective)
            r['leave_deduction'] = max(0, (len(effective) - r['allowed_anomalies']) * 0.5)

    holidays = get_holidays_for_range(start_date, end_date)
    holiday_names = get_holiday_names(start_date, end_date)
    dept_groups = group_by_department(results)

    return render_template('report.html',
                           dept_groups=dept_groups, results=results,
                           start_date=start_date, end_date=end_date,
                           params=params, holidays=sorted(holidays),
                           holiday_names=holiday_names,
                           session_id=session_uuid, stage='final')


@app.route('/admin/review/<session_uuid>')
@role_required('admin')
def admin_review(session_uuid):
    """Admin reviews Head decisions and finalizes."""
    data_path = os.path.join(app.config['DATA_FOLDER'], f"{session_uuid}.json")
    if not os.path.exists(data_path):
        flash('Session not found.')
        return redirect(url_for('admin_dashboard'))

    with open(data_path) as f:
        data = json.load(f)

    results, start_date, end_date, params = deserialize_results(data)
    dept_groups = group_by_department(results)

    db = get_db()
    justifications = db.execute(
        'SELECT * FROM justifications WHERE session_uuid = ? ORDER BY emp_code, anomaly_date',
        (session_uuid,)).fetchall()

    # Build lookup: emp_code -> date_str -> justification row
    just_map = {}
    for j in justifications:
        key = j['emp_code']
        if key not in just_map:
            just_map[key] = {}
        just_map[key][j['anomaly_date']] = dict(j)

    return render_template('admin_review.html',
                           dept_groups=dept_groups, results=results,
                           start_date=start_date, end_date=end_date,
                           params=params, session_uuid=session_uuid,
                           just_map=just_map)


@app.route('/admin/finalize/<session_uuid>', methods=['POST'])
@role_required('admin')
def admin_finalize(session_uuid):
    """Admin finalizes decisions."""
    db = get_db()
    # Process form: decision_EMPCODE_DATE = excluded|counted
    for key, value in request.form.items():
        if key.startswith('decision_'):
            parts = key.split('_', 2)
            if len(parts) == 3:
                emp_code = parts[1]
                anomaly_date = parts[2]
                admin_remark = request.form.get(f'admin_remark_{emp_code}_{anomaly_date}', '')
                db.execute('''
                    UPDATE justifications
                    SET finalized = 1, final_decision = ?, admin_remark = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE session_uuid = ? AND emp_code = ? AND anomaly_date = ?
                ''', (value, admin_remark, session_uuid, emp_code, anomaly_date))
        elif key.startswith('query_head_'):
            # Admin queries head: reset status to query
            parts = key.split('_', 3)
            if len(parts) == 4:
                emp_code = parts[2]
                anomaly_date = parts[3]
                admin_remark = request.form.get(f'admin_remark_{emp_code}_{anomaly_date}', '')
                db.execute('''
                    UPDATE justifications
                    SET status = 'query', admin_remark = ?, finalized = 0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE session_uuid = ? AND emp_code = ? AND anomaly_date = ?
                ''', (admin_remark, session_uuid, emp_code, anomaly_date))
    db.commit()
    flash('Decisions finalized successfully.')
    return redirect(url_for('admin_review', session_uuid=session_uuid))


@app.route('/admin/users', methods=['GET'])
@role_required('admin')
def admin_users():
    db = get_db()
    users = db.execute('SELECT * FROM users ORDER BY role, name').fetchall()
    departments = db.execute('SELECT * FROM departments ORDER BY name').fetchall()
    # Get head-department mappings
    head_depts = {}
    rows = db.execute('''
        SELECT hd.user_id, d.name FROM head_departments hd
        JOIN departments d ON d.id = hd.dept_id
    ''').fetchall()
    for row in rows:
        head_depts.setdefault(row['user_id'], []).append(row['name'])
    return render_template('admin_users.html',
                           users=users, departments=departments,
                           head_depts=head_depts)


def generate_username(name, db):
    """Generate a unique username from a person's name."""
    clean = name.strip()
    for prefix in ['Mr. ', 'Mr ', 'Mrs. ', 'Mrs ', 'Ms. ', 'Dr. ', 'Sh. ', 'Smt. ']:
        if clean.lower().startswith(prefix.lower()):
            clean = clean[len(prefix):]
    parts = [p.strip().lower().replace('.', '').replace(',', '') for p in clean.split() if p.strip()]
    parts = [p for p in parts if p]
    if not parts:
        return name.lower().replace(' ', '')
    if len(parts) == 1:
        base = parts[0]
    else:
        base = f'{parts[0]}.{parts[-1]}'
    # Ensure uniqueness
    uname = base
    counter = 2
    while db.execute('SELECT id FROM users WHERE username = ?', (uname,)).fetchone():
        uname = f'{base}{counter}'
        counter += 1
    return uname


@app.route('/admin/users/add', methods=['POST'])
@role_required('admin')
def admin_add_user():
    emp_code = request.form.get('emp_code', '').strip()
    name = request.form.get('name', '').strip()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', 'employee')
    dept_ids = request.form.getlist('departments')

    if not emp_code or not name or not password:
        flash('All fields are required.')
        return redirect(url_for('admin_users'))

    if role not in ('employee', 'head', 'admin'):
        role = 'employee'

    db = get_db()
    try:
        username = generate_username(name, db)
        db.execute(
            'INSERT INTO users (emp_code, name, password_hash, role, username) VALUES (?, ?, ?, ?, ?)',
            (emp_code, name, generate_password_hash(password), role, username))
        user_id = db.execute('SELECT id FROM users WHERE emp_code = ?', (emp_code,)).fetchone()['id']

        if role == 'head' and dept_ids:
            for did in dept_ids:
                db.execute('INSERT OR IGNORE INTO head_departments (user_id, dept_id) VALUES (?, ?)',
                           (user_id, int(did)))
        db.commit()
        flash(f'User {name} added. Username: {username} ({role})')
    except sqlite3.IntegrityError:
        flash(f'Employee code "{emp_code}" already exists.')

    return redirect(url_for('admin_users'))


@app.route('/admin/users/edit/<int:user_id>', methods=['POST'])
@role_required('admin')
def admin_edit_user(user_id):
    name = request.form.get('name', '').strip()
    role = request.form.get('role', 'employee')
    password = request.form.get('password', '').strip()
    dept_ids = request.form.getlist('departments')
    is_active = 1 if request.form.get('is_active') else 0

    db = get_db()
    if password:
        db.execute('UPDATE users SET name=?, role=?, password_hash=?, is_active=? WHERE id=?',
                   (name, role, generate_password_hash(password), is_active, user_id))
    else:
        db.execute('UPDATE users SET name=?, role=?, is_active=? WHERE id=?',
                   (name, role, is_active, user_id))

    # Update head-department mappings
    db.execute('DELETE FROM head_departments WHERE user_id = ?', (user_id,))
    if role == 'head' and dept_ids:
        for did in dept_ids:
            db.execute('INSERT INTO head_departments (user_id, dept_id) VALUES (?, ?)',
                       (user_id, int(did)))
    db.commit()
    flash('User updated successfully.')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@role_required('admin')
def admin_delete_user(user_id):
    db = get_db()
    db.execute('DELETE FROM users WHERE id = ? AND emp_code != ?', (user_id, 'admin'))
    db.commit()
    flash('User deleted.')
    return redirect(url_for('admin_users'))


@app.route('/admin/departments/add', methods=['POST'])
@role_required('admin')
def admin_add_dept():
    name = request.form.get('dept_name', '').strip()
    if name:
        db = get_db()
        try:
            db.execute('INSERT INTO departments (name) VALUES (?)', (name,))
            db.commit()
            flash(f'Department "{name}" added.')
        except sqlite3.IntegrityError:
            flash(f'Department "{name}" already exists.')
    return redirect(url_for('admin_users'))


# ================================================================
#  EMPLOYEE ROUTES
# ================================================================

@app.route('/employee')
@role_required('employee', 'head', 'admin')
def employee_dashboard():
    emp_code = session.get('emp_code')
    db = get_db()

    # Get all sessions where this employee has anomalies
    sessions_with_data = db.execute('''
        SELECT DISTINCT us.session_uuid, us.start_date, us.end_date, us.created_at
        FROM upload_sessions us
        JOIN justifications j ON j.session_uuid = us.session_uuid
        WHERE j.emp_code = ?
        ORDER BY us.created_at DESC
    ''', (emp_code,)).fetchall()

    # For each session, get justification summary
    session_data = []
    for s in sessions_with_data:
        justs = db.execute('''
            SELECT * FROM justifications
            WHERE session_uuid = ? AND emp_code = ?
            ORDER BY anomaly_date
        ''', (s['session_uuid'], emp_code)).fetchall()

        total = len(justs)
        pending = sum(1 for j in justs if j['status'] == 'pending')
        submitted = sum(1 for j in justs if j['status'] == 'submitted')
        query = sum(1 for j in justs if j['status'] in ('query', 'query_by_admin'))
        accepted = sum(1 for j in justs if j['status'] == 'accepted')
        declined = sum(1 for j in justs if j['status'] == 'declined')

        session_data.append({
            'session_uuid': s['session_uuid'],
            'start_date': s['start_date'],
            'end_date': s['end_date'],
            'created_at': s['created_at'],
            'total': total,
            'pending': pending,
            'submitted': submitted,
            'query': query,
            'accepted': accepted,
            'declined': declined,
        })

    return render_template('employee_dashboard.html', session_data=session_data)


@app.route('/employee/report/<session_uuid>')
@role_required('employee', 'head', 'admin')
def employee_report(session_uuid):
    """Employee views own anomalies and submits justifications."""
    emp_code = session.get('emp_code')
    db = get_db()

    # Load analysis data
    data_path = os.path.join(app.config['DATA_FOLDER'], f"{session_uuid}.json")
    if not os.path.exists(data_path):
        flash('Session not found.')
        return redirect(url_for('employee_dashboard'))

    with open(data_path) as f:
        data = json.load(f)

    results, start_date, end_date, params = deserialize_results(data)

    # Find this employee's results
    emp_result = None
    for r in results:
        if r['emp_code'] == emp_code:
            emp_result = r
            break

    if not emp_result:
        flash('No attendance data found for your employee code.')
        return redirect(url_for('employee_dashboard'))

    # Get justification rows
    justs = db.execute('''
        SELECT * FROM justifications
        WHERE session_uuid = ? AND emp_code = ?
        ORDER BY anomaly_date
    ''', (session_uuid, emp_code)).fetchall()

    just_map = {j['anomaly_date']: dict(j) for j in justs}

    holidays = get_holidays_for_range(start_date, end_date)
    holiday_names = get_holiday_names(start_date, end_date)

    return render_template('employee_report.html',
                           emp=emp_result, start_date=start_date,
                           end_date=end_date, params=params,
                           holidays=sorted(holidays),
                           holiday_names=holiday_names,
                           session_uuid=session_uuid,
                           just_map=just_map)


@app.route('/employee/justify/<session_uuid>', methods=['POST'])
@role_required('employee', 'head', 'admin')
def employee_justify(session_uuid):
    """Employee submits justifications for anomalies."""
    emp_code = session.get('emp_code')
    db = get_db()

    for key, value in request.form.items():
        if key.startswith('justification_'):
            anomaly_date = key.replace('justification_', '')
            value = value.strip()
            if value:
                db.execute('''
                    UPDATE justifications
                    SET justification = ?, status = 'submitted',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE session_uuid = ? AND emp_code = ? AND anomaly_date = ?
                          AND status IN ('pending', 'query')
                ''', (value, session_uuid, emp_code, anomaly_date))
    db.commit()
    flash('Justifications submitted to your Department Head.')
    return redirect(url_for('employee_report', session_uuid=session_uuid))


# ================================================================
#  HEAD ROUTES
# ================================================================

@app.route('/head')
@role_required('head', 'admin')
def head_dashboard():
    db = get_db()
    user_id = session.get('user_id')

    # Get departments managed by this head
    if session.get('role') == 'admin':
        managed_depts = [row['name'] for row in
                         db.execute('SELECT name FROM departments ORDER BY name').fetchall()]
    else:
        managed_depts = [row['name'] for row in db.execute('''
            SELECT d.name FROM head_departments hd
            JOIN departments d ON d.id = hd.dept_id
            WHERE hd.user_id = ?
            ORDER BY d.name
        ''', (user_id,)).fetchall()]

    if not managed_depts:
        flash('No departments assigned to you. Please contact Admin.')
        return render_template('head_dashboard.html',
                               managed_depts=[], dept_groups={},
                               session_uuid=None, start_date=None, end_date=None,
                               params=None, just_summary={}, active_dept='')

    # Department filter for DG/DDG (many departments)
    active_dept = request.args.get('dept', '')
    if active_dept and active_dept not in managed_depts:
        active_dept = ''

    # Get latest session
    latest = db.execute(
        'SELECT * FROM upload_sessions ORDER BY created_at DESC LIMIT 1').fetchone()

    empty_ctx = dict(managed_depts=managed_depts, dept_groups={},
                     session_uuid=None, start_date=None, end_date=None,
                     params=None, just_summary={}, active_dept=active_dept)

    if not latest:
        return render_template('head_dashboard.html', **empty_ctx)

    data_path = os.path.join(app.config['DATA_FOLDER'], f"{latest['session_uuid']}.json")
    if not os.path.exists(data_path):
        return render_template('head_dashboard.html', **empty_ctx)

    with open(data_path) as f:
        data = json.load(f)

    results, start_date, end_date, params = deserialize_results(data)

    # If many departments and a specific one is selected, show only that
    # If many departments and none selected, show only dept list (no table)
    show_depts = managed_depts
    if len(managed_depts) > 3:
        if active_dept:
            show_depts = [active_dept]
        else:
            # Show just the dept chips, no employee tables yet
            return render_template('head_dashboard.html',
                                   managed_depts=managed_depts, dept_groups={},
                                   session_uuid=latest['session_uuid'],
                                   start_date=start_date, end_date=end_date,
                                   params=params, just_summary={},
                                   active_dept=active_dept,
                                   pick_dept=True)

    dept_results = [r for r in results if r['department'] in show_depts]
    dept_groups = group_by_department(dept_results)

    # Get justification summary per employee
    emp_codes = [r['emp_code'] for r in dept_results]
    just_summary = {}  # emp_code -> {pending, submitted, query, accepted, declined}
    if emp_codes:
        placeholders = ','.join('?' * len(emp_codes))
        justs = db.execute(f'''
            SELECT emp_code, status FROM justifications
            WHERE session_uuid = ? AND emp_code IN ({placeholders})
        ''', [latest['session_uuid']] + emp_codes).fetchall()
        for j in justs:
            code = j['emp_code']
            if code not in just_summary:
                just_summary[code] = {'pending': 0, 'submitted': 0, 'query': 0,
                                      'accepted': 0, 'declined': 0}
            st = j['status']
            if st in just_summary[code]:
                just_summary[code][st] += 1
            elif st == 'resubmitted':
                just_summary[code]['submitted'] += 1

    return render_template('head_dashboard.html',
                           managed_depts=managed_depts,
                           dept_groups=dept_groups,
                           session_uuid=latest['session_uuid'],
                           start_date=start_date,
                           end_date=end_date,
                           params=params,
                           just_summary=just_summary,
                           active_dept=active_dept)


@app.route('/head/employee/<session_uuid>/<emp_code>')
@role_required('head', 'admin')
def head_employee_detail(session_uuid, emp_code):
    """Head views detailed anomaly report for a single employee."""
    db = get_db()

    data_path = os.path.join(app.config['DATA_FOLDER'], f"{session_uuid}.json")
    if not os.path.exists(data_path):
        flash('Session not found.')
        return redirect(url_for('head_dashboard'))

    with open(data_path) as f:
        data = json.load(f)

    results, start_date, end_date, params = deserialize_results(data)

    emp_result = None
    for r in results:
        if r['emp_code'] == emp_code:
            emp_result = r
            break

    if not emp_result:
        flash('Employee not found in this session.')
        return redirect(url_for('head_dashboard'))

    justs = db.execute('''
        SELECT * FROM justifications
        WHERE session_uuid = ? AND emp_code = ?
        ORDER BY anomaly_date
    ''', (session_uuid, emp_code)).fetchall()

    just_map = {j['anomaly_date']: dict(j) for j in justs}

    holidays = get_holidays_for_range(start_date, end_date)
    holiday_names = get_holiday_names(start_date, end_date)

    return render_template('head_employee_detail.html',
                           emp=emp_result, start_date=start_date,
                           end_date=end_date, params=params,
                           holidays=sorted(holidays),
                           holiday_names=holiday_names,
                           session_uuid=session_uuid,
                           just_map=just_map)


@app.route('/head/review/<session_uuid>')
@role_required('head', 'admin')
def head_review(session_uuid):
    """Head reviews justifications from their departments."""
    db = get_db()
    user_id = session.get('user_id')

    if session.get('role') == 'admin':
        managed_depts = [row['name'] for row in
                         db.execute('SELECT name FROM departments ORDER BY name').fetchall()]
    else:
        managed_depts = [row['name'] for row in db.execute('''
            SELECT d.name FROM head_departments hd
            JOIN departments d ON d.id = hd.dept_id
            WHERE hd.user_id = ?
        ''', (user_id,)).fetchall()]

    data_path = os.path.join(app.config['DATA_FOLDER'], f"{session_uuid}.json")
    if not os.path.exists(data_path):
        flash('Session not found.')
        return redirect(url_for('head_dashboard'))

    with open(data_path) as f:
        data = json.load(f)

    results, start_date, end_date, params = deserialize_results(data)
    dept_results = [r for r in results if r['department'] in managed_depts]
    dept_groups = group_by_department(dept_results)

    # Get justifications for these employees
    emp_codes = [r['emp_code'] for r in dept_results]
    if emp_codes:
        placeholders = ','.join('?' * len(emp_codes))
        justs = db.execute(f'''
            SELECT * FROM justifications
            WHERE session_uuid = ? AND emp_code IN ({placeholders})
            ORDER BY emp_code, anomaly_date
        ''', [session_uuid] + emp_codes).fetchall()
    else:
        justs = []

    just_map = {}
    for j in justs:
        just_map.setdefault(j['emp_code'], {})[j['anomaly_date']] = dict(j)

    holidays = get_holidays_for_range(start_date, end_date)
    holiday_names = get_holiday_names(start_date, end_date)

    return render_template('head_review.html',
                           dept_groups=dept_groups, results=dept_results,
                           start_date=start_date, end_date=end_date,
                           params=params, session_uuid=session_uuid,
                           just_map=just_map,
                           holidays=sorted(holidays),
                           holiday_names=holiday_names)


@app.route('/head/submit/<session_uuid>', methods=['POST'])
@role_required('head', 'admin')
def head_submit(session_uuid):
    """Head submits accept/decline/query decisions."""
    db = get_db()

    for key, value in request.form.items():
        if key.startswith('action_'):
            # action_EMPCODE_DATE = accepted|declined|query
            parts = key.split('_', 2)
            if len(parts) == 3:
                emp_code = parts[1]
                anomaly_date = parts[2]
                head_remark = request.form.get(f'remark_{emp_code}_{anomaly_date}', '')
                new_status = value  # accepted, declined, or query

                db.execute('''
                    UPDATE justifications
                    SET status = ?, head_action = ?, head_remark = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE session_uuid = ? AND emp_code = ? AND anomaly_date = ?
                          AND status IN ('submitted', 'resubmitted', 'query')
                ''', (new_status, value, head_remark,
                      session_uuid, emp_code, anomaly_date))
    db.commit()
    flash('Decisions submitted successfully.')
    return redirect(url_for('head_review', session_uuid=session_uuid))


# ================================================================
#  LEGACY ROUTES (keep for backward compatibility with report.html)
# ================================================================

@app.route('/analyze', methods=['POST'])
def analyze():
    """Legacy analyze route - redirects to admin upload if logged in."""
    if 'user_id' in session and session.get('role') == 'admin':
        return admin_upload()
    return redirect(url_for('login'))


@app.route('/dept-report/<session_id>/<dept_name>')
@login_required
def dept_report(session_id, dept_name):
    data_path = os.path.join(app.config['DATA_FOLDER'], f"{session_id}.json")
    if not os.path.exists(data_path):
        flash('Session expired or not found.')
        return redirect(url_for('dashboard'))

    with open(data_path) as f:
        data = json.load(f)

    results, start_date, end_date, params = deserialize_results(data)
    dept_results = [r for r in results if r['department'] == dept_name]

    holidays = get_holidays_for_range(start_date, end_date)
    holiday_names = get_holiday_names(start_date, end_date)

    return render_template('dept_report.html',
                           dept_name=dept_name, results=dept_results,
                           start_date=start_date, end_date=end_date,
                           params=params, holidays=sorted(holidays),
                           holiday_names=holiday_names, session_id=session_id)


# ================================================================
#  PASSWORD CHANGE
# ================================================================

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_pw = request.form.get('old_password', '')
        new_pw = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')

        if new_pw != confirm:
            flash('New passwords do not match.')
            return redirect(url_for('change_password'))

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE id = ?',
                          (session['user_id'],)).fetchone()
        if not check_password_hash(user['password_hash'], old_pw):
            flash('Current password is incorrect.')
            return redirect(url_for('change_password'))

        db.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                   (generate_password_hash(new_pw), session['user_id']))
        db.commit()
        flash('Password changed successfully.')
        return redirect(url_for('dashboard'))

    return render_template('change_password.html')


# ================================================================
#  INIT & RUN
# ================================================================

init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)
