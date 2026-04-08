"""Serialize/deserialize attendance analysis results to/from JSON."""
from datetime import date


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
