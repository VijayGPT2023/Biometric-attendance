"""CLI management commands for seeding data, creating admin, etc."""
import click
from werkzeug.security import generate_password_hash
from app import create_app
from app.extensions import db
from app.models import *


app = create_app()


@app.cli.command('init-db')
def init_db_cmd():
    """Create all database tables."""
    with app.app_context():
        db.create_all()
        click.echo('Database tables created.')


@app.cli.command('seed')
def seed_cmd():
    """Seed default data: admin user, HQ office, departments, employees, holidays."""
    with app.app_context():
        db.create_all()
        _seed_offices()
        _seed_admin()
        _seed_departments()
        _seed_head_accounts()
        _seed_employees()
        _seed_holidays_2026()
        click.echo('Seed complete.')


def _seed_offices():
    if not Office.query.filter_by(code='HQ').first():
        db.session.add(Office(name='NPC Headquarters', code='HQ', location='New Delhi',
                              state='Delhi', work_start_time='09:00', work_end_time='17:30'))
        db.session.commit()
        click.echo('  Office: NPC Headquarters created')


def _seed_admin():
    if not User.query.filter_by(username='admin').first():
        admin = User(emp_code='admin', username='admin', name='Administrator',
                     role='super_admin', must_change_password=True)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        click.echo('  Admin user created (admin / admin123)')


def _seed_departments():
    hq = Office.query.filter_by(code='HQ').first()
    if not hq:
        return
    depts = ['AB Group', 'Admin', 'DG Sectt', 'ECA Group', 'EM Group',
             'ES Group', 'Finance', 'HQ', 'HRM Group', 'IE Group', 'IS Group', 'IT Group']
    for name in depts:
        if not Department.query.filter_by(name=name, office_id=hq.id).first():
            db.session.add(Department(name=name, office_id=hq.id))
    db.session.commit()
    click.echo(f'  {len(depts)} departments created')


def _seed_head_accounts():
    hq = Office.query.filter_by(code='HQ').first()
    if not hq:
        return
    pw = generate_password_hash('npc123')
    all_dept_ids = [d.id for d in Department.query.filter_by(office_id=hq.id).all()]

    # Position-based head accounts
    top_roles = [
        ('DG', 'Director General', 'dg', all_dept_ids),
        ('DDG-I', 'DDG-I', 'ddg1', all_dept_ids),
        ('DDG-II', 'DDG-II', 'ddg2', all_dept_ids),
    ]
    gh_accounts = [
        ('GH-AB', 'GH AB Group', 'gh.abgroup', ['AB Group']),
        ('GH-ADMIN', 'GH Admin', 'gh.admin', ['Admin', 'DG Sectt', 'HQ']),
        ('GH-ECA', 'GH ECA Group', 'gh.ecagroup', ['ECA Group', 'IS Group']),
        ('GH-EM', 'GH EM Group', 'gh.emgroup', ['EM Group']),
        ('GH-ES', 'GH ES Group', 'gh.esgroup', ['ES Group']),
        ('GH-FIN', 'GH Finance', 'gh.finance', ['Finance']),
        ('GH-HRM', 'GH HRM Group', 'gh.hrmgroup', ['HRM Group']),
        ('GH-IE', 'GH IE Group', 'gh.iegroup', ['IE Group']),
        ('GH-IT', 'GH IT Group', 'gh.itgroup', ['IT Group']),
    ]

    count = 0
    for emp_code, name, username, dept_ids_or_names in top_roles:
        if not User.query.filter_by(username=username).first():
            u = User(emp_code=emp_code, username=username, name=name,
                     role='head', office_id=hq.id, must_change_password=True)
            u.set_password('npc123')
            db.session.add(u)
            db.session.flush()
            for did in dept_ids_or_names:
                dept = Department.query.get(did)
                if dept:
                    u.head_departments.append(dept)
            count += 1

    for emp_code, name, username, dept_names in gh_accounts:
        if not User.query.filter_by(username=username).first():
            u = User(emp_code=emp_code, username=username, name=name,
                     role='head', office_id=hq.id, must_change_password=True)
            u.set_password('npc123')
            db.session.add(u)
            db.session.flush()
            for dn in dept_names:
                dept = Department.query.filter_by(name=dn, office_id=hq.id).first()
                if dept:
                    u.head_departments.append(dept)
            count += 1

    db.session.commit()
    click.echo(f'  {count} head accounts created')


def _seed_employees():
    from app.utils.helpers import generate_username
    hq = Office.query.filter_by(code='HQ').first()
    if not hq:
        return

    EMPLOYEES = [
        ('00000097', 'Aman Gulati'), ('00000099', 'Nakul'), ('00000101', 'Md. Khalid Anwar'),
        ('00000103', 'Mahotsav Priya'), ('00000105', 'Raj Kumar'), ('00000111', 'Amit Dabas'),
        ('00000113', 'Raj Kumar Rawat'), ('00000116', 'M.M. Senghal'), ('00000120', 'Nand Kishor'),
        ('00000123', 'Tukeshwar Yadav'), ('00000124', 'Chadra Prakash'), ('00000130', 'Shivani Maurya'),
        ('00000132', 'Shivam Kumar'), ('00000133', 'Sai Shankar G Nair'), ('00000135', 'Deepika Goswami'),
        ('00000136', 'Sankriti Thakur'), ('00000138', 'Shukla Pal Maitra'), ('00000139', 'Saurabh Singh'),
        ('00000140', 'Sandeep Aka'), ('00000141', 'Pradeep Kumar'), ('00000142', 'Vikas'),
        ('00000143', 'Mahender'), ('00000144', 'Shashank Srivastava'), ('00000145', 'Rachna'),
        ('00000146', 'S N Rao'), ('00000147', 'Ramesh Kumar'), ('00000148', 'K K Sharma'),
        ('00000149', 'Diwakar'), ('00000152', 'Mohd Asim'), ('00000153', 'C N Dubey'),
        ('00000158', 'Uday Bhan Yadav'), ('00000159', 'Chaman Kumar Shukla'),
        ('00000160', 'Vijay Kumar'), ('00000161', 'Akash Bhartiya'), ('00000162', 'Ronak'),
        ('00000163', 'Dr Rajat Sharma'), ('00000164', 'Geetika Sharma'),
        ('00000165', 'Rachana Shalini'), ('00000166', 'Kritika Garg'),
        ('00000167', 'Tanaya Kapila'), ('00000168', 'Dipti Rawat'),
        ('00000169', 'Durgesh Verma'), ('00000170', 'Purnika'),
        ('00000181', 'Naveen'), ('00000182', 'Yatish'), ('00000183', 'Bikash Kumar'),
        ('00000184', 'P Ganesh Patro'), ('00000185', 'Chanchal Soni'),
        ('00000186', 'Anita Singh'), ('00000187', 'Shahzad'),
        ('00000188', 'Ayushman Shukla'), ('00000189', 'Mayank Mishra'),
        ('1', 'Malkhan Singh'), ('2', 'Nidhi'), ('3', 'Sandeep Kumar Gupta'),
        ('5', 'Pooja Nag'), ('6', 'Yadu Kumar Yadav'),
        ('S007', 'Abhishek'), ('S008', 'Rohtas'), ('S009', 'Gushneer'),
        ('S010', 'Om Pal'), ('S011', 'Bijender'), ('S012', 'Vikas Kumar Nehra'),
        ('S013', 'Sourabh Yadav'), ('S014', 'Deepak'), ('S015', 'Ganesh Deen'),
        ('S016', 'Abhishek'), ('S017', 'Vijay Kr. Nehra'), ('S018', 'Sourabh Mittal'),
        ('S019', 'Ashok Kr.'), ('S020', 'Shurveer Singh'), ('S021', 'Arun Kaushik'),
        ('S022', 'Nitin'), ('S023', 'Suraj Bhan'), ('S024', 'Rajiv Bihari'),
        ('S025', 'Shashi Ranjan'), ('S026', 'Amitava Ray'), ('S027', 'Anup'),
        ('S028', 'Neeraj'), ('S029', 'Rekha Kumari'), ('S030', 'Heeralal Mehto'),
        ('S031', 'T.D Pandey'), ('S032', 'Gopi Nath'), ('S033', 'Sweta'),
        ('S034', 'Moh. Kadir'), ('S035', 'Mahender Deep Kaur'), ('S036', 'Dharam Veer'),
        ('S037', 'Pinky'), ('S038', 'Jai Karan'), ('S039', 'Ashutosh Makup'),
        ('S040', 'Makan Singh Negi'), ('S041', 'Saroj'), ('S042', 'Dayavati'),
        ('S043', 'Sanjeev Bhatia'), ('S044', 'Sunil Kumar Jha'), ('S045', 'Rashid'),
        ('S046', 'Sidharth Pal'), ('S047', 'S.P Singh'), ('S048', 'Kumud Jacob'),
        ('S049', 'Sunil Kr.'), ('S050', 'Om Prakash'), ('S051', 'Ashish'),
        ('S052', 'Binko'), ('S053', 'Hemant Kr.'), ('S054', 'Bajrang'),
        ('S055', 'D.K Rahul'), ('S056', 'Rajesh Chand Katoch'), ('S057', 'Urmila'),
        ('S058', 'Lalit Shankar Kamde'), ('S059', 'Abhinav Mishra'),
        ('S060', 'Anand Verma'), ('S061', 'Asmita Raj'), ('S062', 'Rajendra Paswan'),
        ('S063', 'Tribhuvan'), ('S064', 'B. Prabhakar'), ('S065', 'Hemant'),
        ('S066', 'Nikita'), ('S067', 'Rajesh Sund'), ('S068', 'Santosh Kumar'),
        ('S069', 'Shabnam'), ('S070', 'Anupam Saini'), ('S071', 'Nikhil Negi'),
        ('S072', 'Rajiv Gupta'), ('S073', 'Devender Laun'), ('S074', 'Sita Sharan Jha'),
        ('S075', 'Jitendra Kr. Srivastava'), ('S076', 'Naman Upadhyay'),
        ('S077', 'S.P Tripathi'), ('S078', 'Ashish Prabhash Bhandwalkar'),
        ('S079', 'Sanjay Kr. Triwedi'), ('S080', 'Ashmita'), ('S081', 'Manoj Kr. Acharya'),
        ('S082', 'Samdhani'), ('S083', 'Saurabh Sharma'), ('S084', 'Kritika Shukla'),
        ('S085', 'Bhuvan'), ('S086', 'Nitin Agarwal'), ('S087', 'Nisha'),
        ('S088', 'Vinod Kr. Singh'), ('S089', 'Manish Meena'),
        ('S090', 'Prashant Srivastava'), ('S091', 'Abhishek'),
        ('S092', 'Harsh Thukral'), ('S093', 'N.H Panchbhai'),
        ('S094', 'Shirish Paliwal'), ('S095', 'K.D Bhardwaj'), ('S106', 'Suresh Kumar'),
    ]

    existing_usernames = {u.username for u in User.query.all()}
    count = 0
    for emp_code, name in EMPLOYEES:
        if User.query.filter_by(emp_code=emp_code, office_id=hq.id).first():
            continue
        uname = generate_username(name, existing_usernames)
        existing_usernames.add(uname)
        u = User(emp_code=emp_code, username=uname, name=name,
                 role='employee', office_id=hq.id, must_change_password=True)
        u.set_password('npc123')
        db.session.add(u)
        count += 1

    db.session.commit()
    click.echo(f'  {count} employees created')


def _seed_holidays_2026():
    from datetime import date
    hq = Office.query.filter_by(code='HQ').first()

    holidays_2026 = [
        (date(2026, 1, 26), 'Republic Day', 'गणतंत्र दिवस'),
        (date(2026, 2, 16), 'Maha Shivaratri', 'महा शिवरात्रि'),
        (date(2026, 3, 3), 'Holi', 'होली'),
        (date(2026, 3, 20), 'Id-ul-Fitr', 'ईद-उल-फितर'),
        (date(2026, 3, 26), 'Ram Navami', 'रामनवमी'),
        (date(2026, 3, 30), 'Mahavir Jayanti', 'महावीर जयंती'),
        (date(2026, 4, 3), 'Good Friday', 'गुड फ्राइडे'),
        (date(2026, 4, 14), 'Dr. Ambedkar Jayanti', 'डॉ. अम्बेडकर जयंती'),
        (date(2026, 5, 1), 'Buddha Purnima', 'बुद्ध पूर्णिमा'),
        (date(2026, 5, 27), 'Eid ul-Adha', 'ईद-उल-अज़हा'),
        (date(2026, 6, 25), 'Muharram', 'मुहर्रम'),
        (date(2026, 8, 15), 'Independence Day', 'स्वतंत्रता दिवस'),
        (date(2026, 8, 25), 'Milad-un-Nabi', 'मिलाद-उन-नबी'),
        (date(2026, 10, 2), 'Mahatma Gandhi Jayanti', 'महात्मा गांधी जयंती'),
        (date(2026, 10, 9), 'Diwali', 'दीपावली'),
        (date(2026, 10, 19), 'Dussehra', 'दशहरा'),
        (date(2026, 10, 25), 'Guru Nanak Jayanti', 'गुरु नानक जयंती'),
        (date(2026, 12, 25), 'Christmas', 'क्रिसमस'),
    ]

    count = 0
    for h_date, name, name_hi in holidays_2026:
        if not Holiday.query.filter_by(holiday_date=h_date).first():
            db.session.add(Holiday(
                holiday_date=h_date, name=name, name_hi=name_hi,
                holiday_type='gazetted', year=2026,
                office_id=hq.id if hq else None
            ))
            count += 1
    db.session.commit()
    click.echo(f'  {count} holidays for 2026 created')


if __name__ == '__main__':
    app.run()
