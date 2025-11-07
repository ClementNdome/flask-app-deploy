"""
Script to generate sample education data for testing.
"""

from datetime import datetime, timedelta
import random
from sqlalchemy.sql import text
from db import get_session
from models import School, Staff, Facility, Incident, Program

def generate_sample_data():
    session = get_session()
    try:
        # First get existing schools
        schools = session.query(School).all()
        
        # Add school types and other basic info
        school_types = ['Primary', 'Secondary', 'Mixed', 'Special Needs']
        conditions = ['Good', 'Fair', 'Needs Repair']
        roles = ['Teacher', 'Administrator', 'Support Staff']
        qualifications = [
            {'degree': 'B.Ed', 'experience': '5-10 years'},
            {'degree': 'M.Ed', 'experience': '10+ years'},
            {'degree': 'PhD', 'experience': '15+ years'}
        ]
        
        for school in schools:
            # Update school details
            school.school_type = random.choice(school_types)
            school.student_capacity = random.randint(500, 2000)
            school.current_enrollment = random.randint(300, school.student_capacity)
            school.teacher_count = max(10, school.current_enrollment // 30)
            school.staff_count = max(5, school.teacher_count // 4)
            school.classrooms = max(10, school.current_enrollment // 40)
            school.labs = random.randint(1, 4)
            school.libraries = random.randint(1, 2)
            school.computer_labs = random.randint(1, 3)
            school.mean_score = round(random.uniform(250, 400), 2)
            school.performance_index = round(random.uniform(0.6, 0.95), 2)
            school.established_date = datetime(random.randint(1950, 2010), 
                                            random.randint(1, 12), 
                                            random.randint(1, 28))
            school.last_inspection_date = datetime.now() - timedelta(days=random.randint(30, 365))
            
            # Add facilities
            for _ in range(random.randint(5, 10)):
                facility = Facility(
                    school=school,
                    name=f"Building {random.randint(1,5)}",
                    type=random.choice(['Classroom Block', 'Laboratory', 'Library', 'Admin Block']),
                    condition=random.choice(conditions),
                    last_maintenance=datetime.now() - timedelta(days=random.randint(30, 730))
                )
                session.add(facility)
            
            # Add staff
            for _ in range(school.teacher_count + school.staff_count):
                staff = Staff(
                    school=school,
                    name=f"Staff Member {random.randint(1000,9999)}",
                    role=random.choice(roles),
                    qualifications=random.choice(qualifications),
                    joining_date=datetime.now() - timedelta(days=random.randint(30, 3650))
                )
                session.add(staff)
            
            # Add some incidents
            for _ in range(random.randint(0, 5)):
                days_ago = random.randint(1, 365)
                reported = datetime.now() - timedelta(days=days_ago)
                resolved = reported + timedelta(days=random.randint(1, 30)) if random.random() > 0.3 else None
                
                incident = Incident(
                    school=school,
                    type=random.choice(['Safety', 'Maintenance', 'Discipline', 'Emergency']),
                    description=f"Sample incident from {reported.strftime('%Y-%m-%d')}",
                    severity=random.choice(['Low', 'Medium', 'High']),
                    status='Resolved' if resolved else random.choice(['Open', 'In Progress']),
                    reported_at=reported,
                    resolved_at=resolved
                )
                session.add(incident)
        
        # Create some programs
        programs = [
            Program(name="Standard Curriculum", description="Basic education program", level="Primary"),
            Program(name="Advanced Sciences", description="Enhanced STEM focus", level="Secondary"),
            Program(name="Special Education", description="Inclusive education program", level="Special Needs"),
            Program(name="Arts & Culture", description="Enhanced creative arts program", level="Mixed")
        ]
        for program in programs:
            session.add(program)
            # Assign to random schools
            for school in random.sample(schools, k=len(schools)//3):
                school.programs.append(program)
        
        session.commit()
        print("Sample data generated successfully")
        
    except Exception as e:
        print(f"Error generating sample data: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    generate_sample_data()