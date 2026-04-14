import sqlite3

class SQL:
    def __init__(self, database):
        self.connection = sqlite3.connect(database)
        self.cursor = self.connection.cursor()
        self._migrate()

    def _migrate(self):
        """Добавляет недостающие колонки если их нет"""
        existing = {row[1] for row in self.cursor.execute("PRAGMA table_info(users)").fetchall()}
        migrations = {
            "day":    "ALTER TABLE users ADD COLUMN day INTEGER DEFAULT 0",
            "mes":    "ALTER TABLE users ADD COLUMN mes INTEGER DEFAULT 0",
            "notify": "ALTER TABLE users ADD COLUMN notify INTEGER DEFAULT 1",
        }
        for col, sql in migrations.items():
            if col not in existing:
                self.cursor.execute(sql)
        self.connection.commit()

    # Добавление пользователя в БД
    def add_user(self, id):
        query = "INSERT INTO users (id) VALUES(?)"
        with self.connection:
            return self.cursor.execute(query, (id,))

    # Проверка, есть ли пользователь в БД
    def user_exist(self, id):
        query = "SELECT * FROM users WHERE id = ?"
        with self.connection:
            result = self.cursor.execute(query, (id,)).fetchall()
            return bool(len(result))

    # Получить значение поля
    def get_field(self, table, id, field):
        query = f"SELECT {field} FROM {table} WHERE id = ?"
        with self.connection:
            result = self.cursor.execute(query, (id,)).fetchone()
            if result:
                return result[0]

    # Обновить значение поля
    def update_field(self, table, id, field, value):
        query = f"UPDATE {table} SET {field} = ? WHERE id = ?"
        with self.connection:
            self.cursor.execute(query, (value, id))

    # Получить всех пользователей у которых включена рассылка и сохранён знак
    def get_notify_users(self):
        query = "SELECT id, zod FROM users WHERE notify = 1 AND zod IS NOT NULL AND zod != ''"
        with self.connection:
            return self.cursor.execute(query).fetchall()

    def close(self):
        self.connection.close()
