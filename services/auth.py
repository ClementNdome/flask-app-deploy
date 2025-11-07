from passlib.hash import pbkdf2_sha256
from db import get_session
from models import User

class AuthService:
    @staticmethod
    def verify_password(user: User, password: str) -> bool:
        try:
            return pbkdf2_sha256.verify(password, user.password_hash)
        except Exception:
            return False

    @staticmethod
    def hash_password(password: str) -> str:
        return pbkdf2_sha256.hash(password)

    @staticmethod
    def create_user(username: str, password: str, role: str = 'viewer', full_name: str = None, email: str = None):
        session = get_session()
        try:
            u = User(username=username, password_hash=AuthService.hash_password(password), role=role, full_name=full_name, email=email)
            session.add(u)
            session.commit()
            return u
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
