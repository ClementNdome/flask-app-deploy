"""
Generate historical enrollment and inspection records from current schools.
"""
import random
from datetime import datetime, timedelta
from db import get_session
from models import School
from sqlalchemy import text


def generate_history(months=24):
    session = get_session()
    try:
        schools = session.query(School).all()
        now = datetime.now()
        for school in schools:
            base_enroll = school.current_enrollment or random.randint(300, 1200)
            base_capacity = school.student_capacity or (base_enroll + random.randint(50, 500))
            for m in range(months):
                recorded_at = now - timedelta(days=30 * m)
                # simulate seasonal fluctuation
                fluct = int(base_enroll * (1 + random.uniform(-0.08, 0.08)))
                session.execute(
                    text("INSERT INTO enrollment_history (school_id, recorded_at, enrollment, capacity) VALUES (:sid, :rec, :enr, :cap)"),
                    {"sid": school.id, "rec": recorded_at, "enr": fluct, "cap": base_capacity}
                )
            # inspections: roughly 1 per year
            years = max(1, months // 12)
            for y in range(years):
                inspected_at = now - timedelta(days=365 * y)
                score = round(random.uniform(60, 95), 2)
                session.execute(
                    text("INSERT INTO inspection_history (school_id, inspected_at, inspector, score, notes) VALUES (:sid, :ins, :insp, :score, :notes)"),
                    {"sid": school.id, "ins": inspected_at, "insp": f'Inspector {random.randint(1,20)}', "score": score, "notes": 'Auto-generated sample inspection'}
                )
        session.commit()
        print('Historical data generated')
    except Exception as e:
        session.rollback()
        print('Error generating history:', e)
        raise
    finally:
        session.close()

if __name__ == '__main__':
    generate_history(24)
