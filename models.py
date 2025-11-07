from sqlalchemy import Column, Integer, String, JSON, Float, Date, ForeignKey, Table, DateTime
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from datetime import datetime
from db import Base

# Association tables for many-to-many relationships
school_programs = Table('school_programs', Base.metadata,
    Column('school_id', Integer, ForeignKey('schools.id')),
    Column('program_id', Integer, ForeignKey('programs.id'))
)

class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    code = Column(String(20), unique=True)  # Unique school identifier
    school_type = Column(String)  # Primary, Secondary, etc.
    properties = Column(JSON, nullable=True)
    geom = Column(Geometry(geometry_type='GEOMETRY', srid=4326))
    
    # Administrative details
    county = Column(String)
    sub_county = Column(String)
    ward = Column(String)
    
    # Capacity and enrollment
    student_capacity = Column(Integer)
    current_enrollment = Column(Integer)
    teacher_count = Column(Integer)
    staff_count = Column(Integer)
    
    # Infrastructure
    classrooms = Column(Integer)
    labs = Column(Integer)
    libraries = Column(Integer)
    computer_labs = Column(Integer)
    
    # Performance metrics
    mean_score = Column(Float)
    performance_index = Column(Float)
    
    # Timestamps
    established_date = Column(Date)
    last_inspection_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    programs = relationship('Program', secondary=school_programs, back_populates='schools')
    facilities = relationship('Facility', back_populates='school')
    staff = relationship('Staff', back_populates='school')
    incidents = relationship('Incident', back_populates='school')

    def __repr__(self):
        return f"<School id={self.id} name={self.name} type={self.school_type}>"

class Program(Base):
    __tablename__ = "programs"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    level = Column(String)  # e.g., Primary, Secondary, Tertiary
    schools = relationship('School', secondary=school_programs, back_populates='programs')

class Facility(Base):
    __tablename__ = "facilities"
    
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey('schools.id'))
    name = Column(String, nullable=False)
    type = Column(String)  # Classroom, Laboratory, Library, etc.
    condition = Column(String)  # Good, Fair, Needs Repair
    last_maintenance = Column(Date)
    school = relationship('School', back_populates='facilities')

class Staff(Base):
    __tablename__ = "staff"
    
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey('schools.id'))
    name = Column(String, nullable=False)
    role = Column(String)  # Teacher, Administrator, Support Staff
    qualifications = Column(JSON)
    joining_date = Column(Date)
    school = relationship('School', back_populates='staff')

class Incident(Base):
    __tablename__ = "incidents"
    
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey('schools.id'))
    type = Column(String)  # Safety, Maintenance, Emergency, etc.
    description = Column(String)
    severity = Column(String)  # Low, Medium, High
    status = Column(String)  # Open, In Progress, Resolved
    reported_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)
    school = relationship('School', back_populates='incidents')


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String)
    email = Column(String, unique=True)
    active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # simple role field for now; can be expanded to many-to-many
    role = Column(String, default='viewer')  # roles: admin, inspector, manager, viewer

    def is_active(self):
        return bool(self.active)

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f"<User id={self.id} username={self.username} role={self.role}>"
