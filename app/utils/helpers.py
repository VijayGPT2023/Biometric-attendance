"""Shared utility functions."""
import pandas as pd

# Department name normalization mapping
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
    return DEPT_NAME_MAP.get(name.strip(), name.strip()) if name else 'Unknown'


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


def group_by_department(results):
    groups = {}
    for r in results:
        dept = r['department'] or 'Unknown'
        if dept not in groups:
            groups[dept] = []
        groups[dept].append(r)
    return dict(sorted(groups.items()))


def generate_username(name, existing_usernames=None):
    """Generate a unique username from a person's name."""
    existing_usernames = existing_usernames or set()
    clean = name.strip()
    for prefix in ['Mr. ', 'Mr ', 'Mrs. ', 'Dr. ', 'Dr ', 'Sh. ', 'Sh ', 'Smt. ']:
        if clean.lower().startswith(prefix.lower()):
            clean = clean[len(prefix):]
    parts = [p.strip().lower().replace('.', '').replace(',', '')
             for p in clean.split() if p.strip()]
    parts = [p for p in parts if p]
    if not parts:
        return None
    if len(parts) == 1:
        base = parts[0]
    else:
        first, last = parts[0], parts[-1]
        if len(first) <= 2 and len(parts) > 2:
            first = parts[1]
        base = f'{first}.{last}'
    uname = base
    counter = 2
    while uname in existing_usernames:
        uname = f'{base}{counter}'
        counter += 1
    return uname
