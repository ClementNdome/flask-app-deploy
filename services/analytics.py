from sqlalchemy import func, and_, or_, text
from datetime import datetime, timedelta
from models import School, Staff, Incident, Facility
from db import get_session
from typing import Dict, List, Any

class EducationAnalytics:
    """Service class for education system analytics and reporting."""
    
    @staticmethod
    def get_enrollment_statistics(county: str = None) -> Dict[str, Any]:
        """Get enrollment statistics with optional county filter."""
        session = get_session()
        try:
            # Prefer deriving totals from enrollment_history where present
            res = session.execute(text(
                "SELECT SUM(enrollment) as total_enrollment, AVG(enrollment) as avg_enrollment, AVG(capacity) as avg_capacity "
                "FROM enrollment_history eh JOIN schools s ON eh.school_id = s.id "
                + ("WHERE s.county = :county" if county else "")
            ), {"county": county} if county else {}).fetchone()

            if res and res.total_enrollment is not None:
                return {
                    'total_enrollment': int(res.total_enrollment),
                    'average_enrollment': round(res.avg_enrollment or 0, 2),
                    'total_capacity': None,
                    'capacity_utilization': round(((res.avg_enrollment or 0) * 100.0 / (res.avg_capacity or 1)), 2) if res.avg_capacity else 0
                }

            # Fallback to current fields
            query = session.query(
                func.sum(School.current_enrollment).label('total_enrollment'),
                func.avg(School.current_enrollment).label('avg_enrollment'),
                func.sum(School.student_capacity).label('total_capacity'),
                func.avg(
                    (School.current_enrollment * 100.0 / School.student_capacity)
                ).label('avg_capacity_utilization')
            )
            if county:
                query = query.filter(School.county == county)
            stats = query.first()
            return {
                'total_enrollment': int(stats.total_enrollment or 0),
                'average_enrollment': round(stats.avg_enrollment or 0, 2),
                'total_capacity': int(stats.total_capacity or 0),
                'capacity_utilization': round(stats.avg_capacity_utilization or 0, 2)
            }
        finally:
            session.close()
    
    @staticmethod
    def get_performance_metrics(school_type: str = None) -> Dict[str, Any]:
        """Get academic performance metrics with optional school type filter."""
        session = get_session()
        try:
            query = session.query(
                func.avg(School.mean_score).label('avg_score'),
                func.avg(School.performance_index).label('avg_performance'),
                func.count(School.id).label('school_count')
            )
            
            if school_type:
                query = query.filter(School.school_type == school_type)
            
            stats = query.first()
            
            return {
                'average_score': round(stats.avg_score or 0, 2),
                'average_performance_index': round(stats.avg_performance or 0, 2),
                'total_schools': stats.school_count
            }
        finally:
            session.close()
    
    @staticmethod
    def get_resource_distribution() -> Dict[str, Any]:
        """Analyze resource distribution across schools."""
        session = get_session()
        try:
            stats = session.query(
                func.avg(School.teacher_count).label('avg_teachers'),
                func.avg(School.staff_count).label('avg_staff'),
                func.avg(School.classrooms).label('avg_classrooms'),
                func.avg(School.labs).label('avg_labs'),
                func.avg(School.libraries).label('avg_libraries'),
                func.avg(School.computer_labs).label('avg_computer_labs'),
                func.avg(
                    (School.teacher_count * 1.0 / School.current_enrollment)
                ).label('teacher_student_ratio')
            ).first()
            
            return {
                'average_teachers': round(stats.avg_teachers or 0, 2),
                'average_staff': round(stats.avg_staff or 0, 2),
                'average_classrooms': round(stats.avg_classrooms or 0, 2),
                'average_labs': round(stats.avg_labs or 0, 2),
                'average_libraries': round(stats.avg_libraries or 0, 2),
                'average_computer_labs': round(stats.avg_computer_labs or 0, 2),
                'teacher_student_ratio': round(stats.teacher_student_ratio or 0, 2)
            }
        finally:
            session.close()
    
    @staticmethod
    def get_facility_status() -> Dict[str, Any]:
        """Analyze facility conditions and maintenance status."""
        session = get_session()
        try:
            # Get counts by condition
            condition_counts = dict(
                session.query(
                    Facility.condition,
                    func.count(Facility.id)
                ).group_by(Facility.condition).all()
            )
            
            # Get facilities needing maintenance
            maintenance_needed = session.query(func.count(Facility.id)).filter(
                or_(
                    Facility.condition == 'Needs Repair',
                    Facility.last_maintenance < datetime.now() - timedelta(days=365)
                )
            ).scalar()
            
            return {
                'condition_summary': condition_counts,
                'maintenance_needed': maintenance_needed,
                'total_facilities': sum(condition_counts.values())
            }
        finally:
            session.close()
    
    @staticmethod
    def get_incident_summary(days: int = 30) -> Dict[str, Any]:
        """Get summary of incidents in the last n days."""
        session = get_session()
        try:
            since = datetime.now() - timedelta(days=days)
            # Combine recent incidents and inspection_history for timeline
            type_counts = dict(
                session.query(
                    Incident.type,
                    func.count(Incident.id)
                ).filter(
                    Incident.reported_at >= since
                ).group_by(Incident.type).all()
            )

            severity_counts = dict(
                session.query(
                    Incident.severity,
                    func.count(Incident.id)
                ).filter(
                    Incident.reported_at >= since
                ).group_by(Incident.severity).all()
            )

            open_incidents = session.query(func.count(Incident.id)).filter(
                Incident.status != 'Resolved',
                Incident.reported_at >= since
            ).scalar()

            # Also include inspection_history counts
            insp_rows = session.execute(text(
                "SELECT COUNT(*) as cnt, AVG(score) as avg_score FROM inspection_history WHERE inspected_at >= :since"
            ), {"since": since}).fetchone()

            return {
                'by_type': type_counts,
                'by_severity': severity_counts,
                'open_incidents': open_incidents,
                'total_incidents': sum(type_counts.values()),
                'recent_inspections_count': int(insp_rows.cnt or 0),
                'recent_inspections_avg_score': round(float(insp_rows.avg_score or 0), 2)
            }
        finally:
            session.close()
    
    @staticmethod
    def get_staff_qualifications() -> Dict[str, Any]:
        """Analyze staff qualifications and distribution."""
        session = get_session()
        try:
            # Get counts by role
            role_counts = dict(
                session.query(
                    Staff.role,
                    func.count(Staff.id)
                ).group_by(Staff.role).all()
            )
            
            # Count staff by qualification level
            # Note: This assumes qualifications are stored in a consistent format
            qualified_staff = session.query(func.count(Staff.id)).filter(
                Staff.qualifications.op('?')('degree')
            ).scalar()
            
            return {
                'role_distribution': role_counts,
                'total_staff': sum(role_counts.values()),
                'qualified_staff': qualified_staff
            }
        finally:
            session.close()

    @staticmethod
    def get_school_coverage_analysis() -> Dict[str, Any]:
        """Analyze school coverage and accessibility."""
        session = get_session()
        try:
            # Get average distance between schools
            avg_distance = session.query(
                func.avg(
                    func.ST_Distance(
                        School.geom,
                        func.ST_Transform(
                            func.ST_SetSRID(
                                func.ST_MakePoint(36.817223, -1.286389),
                                4326
                            ),
                            3857
                        )
                    )
                )
            ).scalar()
            
            # Get schools per county
            schools_per_county = dict(
                session.query(
                    School.county,
                    func.count(School.id)
                ).group_by(School.county).all()
            )
            
            return {
                'average_distance_km': round(avg_distance / 1000, 2),
                'schools_per_county': schools_per_county,
                'total_counties': len(schools_per_county)
            }
        finally:
            session.close()