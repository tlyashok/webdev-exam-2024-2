import mysql.connector
from flask import g


class DBConnector:
    def __init__(self, app) -> None:
        self.app = app
        self.db_config = {
            'user': app.config['MYSQL_USER'],
            'password': app.config['MYSQL_PASSWORD'],
            'host': app.config['MYSQL_HOST'],
            'database': app.config['MYSQL_DATABASE'],
        }

        self.app.teardown_appcontext(self.close)

    def connect(self):
        if 'db' not in g or g.db.is_closed():
            g.db = mysql.connector.connect(**self.db_config)
        return g.db

    def close(self, e=None):
        db = g.pop('db', None)
        if db is not None:
            db.close()