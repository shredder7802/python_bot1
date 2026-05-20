# ========== РАБОТА С БАЗОЙ SQLite (файл db.db) ==========
# Таблицы: users (черновик при создании), events (события), reminders (когда напомнить)

import sqlite3
import threading

from config import FMT, now_local


class SQL:
    def __init__(self, database):
        self.connection = sqlite3.connect(database, check_same_thread=False)
        # Блокировка: бот и schedule.py не ломают друг другу запросы
        self.lock = threading.Lock()

    # --- Пользователь (временные поля пока создаёт событие) ---

    def add_user(self, user_id):
        with self.lock, self.connection:
            self.connection.execute("INSERT INTO users (id) VALUES (?)", (user_id,))

    def user_exist(self, user_id):
        with self.lock:
            row = self.connection.execute(
                "SELECT id FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return row is not None

    def get_field(self, user_id, field):
        """Читает поле из users: status, name, comment, event_time, type_remind."""
        with self.lock:
            row = self.connection.execute(
                f"SELECT {field} FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return row[0] if row else None

    def update_field(self, user_id, field, value):
        with self.lock, self.connection:
            self.connection.execute(
                f"UPDATE users SET {field} = ? WHERE id = ?", (value, user_id)
            )

    # --- События ---

    def add_event(self, user_id, name, comment, event_time):
        """Сохраняет готовое событие. Возвращает event_id."""
        created = now_local().strftime(FMT)
        with self.lock, self.connection:
            cur = self.connection.execute(
                "INSERT INTO events (id, name, comment, time, current_time) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, name, comment, event_time, created),
            )
            return cur.lastrowid

    def get_user_events(self, user_id):
        self._remove_duplicate_events(user_id)
        with self.lock:
            return self.connection.execute(
                "SELECT event_id, name, time, current_time FROM events "
                "WHERE id = ? ORDER BY time",
                (user_id,),
            ).fetchall()

    def get_event_by_id(self, event_id):
        with self.lock:
            return self.connection.execute(
                "SELECT event_id, name, comment, time, current_time "
                "FROM events WHERE event_id = ?",
                (event_id,),
            ).fetchone()

    def delete_event(self, event_id):
        """Удаляет событие и все его напоминания."""
        with self.lock, self.connection:
            self.connection.execute(
                "DELETE FROM reminders WHERE event_id = ?", (event_id,)
            )
            self.connection.execute(
                "DELETE FROM events WHERE event_id = ?", (event_id,)
            )

    # --- Напоминания ---

    def add_reminder(self, event_id, remind_at, type_remind):
        """remind_at — когда отправить сообщение; type_remind — once/daily/weekly/monthly."""
        with self.lock, self.connection:
            cur = self.connection.execute(
                "INSERT INTO reminders (event_id, remind_at, type_remind, is_sent) "
                "VALUES (?, ?, ?, 0)",
                (event_id, remind_at, type_remind),
            )
            return cur.lastrowid

    def get_pending_reminders(self, now_str):
        """Все напоминания, которые ещё не отправлены (is_sent = 0)."""
        with self.lock:
            return self.connection.execute("""
                SELECT r.id, r.event_id, r.remind_at, r.type_remind,
                       e.name, e.comment, e.time, e.id
                FROM reminders r
                JOIN events e ON r.event_id = e.event_id
                WHERE r.is_sent = 0
            """).fetchall()

    def mark_sent(self, reminder_id):
        with self.lock, self.connection:
            self.connection.execute(
                "UPDATE reminders SET is_sent = 1 WHERE id = ?", (reminder_id,)
            )

    def _remove_duplicate_events(self, user_id):
        """Если одно и то же событие записалось несколько раз — оставляем одну копию."""
        with self.lock, self.connection:
            dup_groups = self.connection.execute("""
                SELECT id, name, comment, time, MIN(event_id) AS keep_id
                FROM events WHERE id = ?
                GROUP BY id, name, comment, time
                HAVING COUNT(*) > 1
            """, (user_id,)).fetchall()

            for uid, name, comment, ev_time, keep_id in dup_groups:
                rows = self.connection.execute(
                    "SELECT event_id FROM events "
                    "WHERE id = ? AND name = ? AND comment = ? AND time = ?",
                    (uid, name, comment, ev_time),
                ).fetchall()
                for (eid,) in rows:
                    if eid != keep_id:
                        self.connection.execute(
                            "DELETE FROM reminders WHERE event_id = ?", (eid,)
                        )
                        self.connection.execute(
                            "DELETE FROM events WHERE event_id = ?", (eid,)
                        )

    def close(self):
        self.connection.close()
