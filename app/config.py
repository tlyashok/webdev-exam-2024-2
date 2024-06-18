import os

from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY')

MYSQL_USER = 'std_2585_exam'
MYSQL_DATABASE = 'std_2585_exam'
MYSQL_PASSWORD = '12345678'
MYSQL_HOST = 'std-mysql.ist.mospolytech.ru'
ADMIN_ROLE_ID = 1
MODERATOR_ROLE_ID = 2
