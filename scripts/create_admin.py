from services.auth import AuthService

if __name__ == '__main__':
    # default credentials: admin / ChangeMe123!
    u = AuthService.create_user('admin', 'ChangeMe123!', role='admin', full_name='Administrator', email='admin@example.com')
    print('Created admin user: admin')
