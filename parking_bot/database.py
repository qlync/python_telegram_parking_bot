import sqlite3
import time
import datetime


def init_db():
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()
    cursor.execute(
        """ 
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            place TEXT NOT NULL,
            user TEXT NOT NULL,
            day TEXT NOT NULL,
            is_temp BOOLEAN DEFAULT FALSE,
            manually_deleted BOOLEAN DEFAULT 0
        )
    """
    )
    connection.commit()
    connection.close()


def create_temp_bookings_table():
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()
    cursor.execute(
        """ 
        CREATE TABLE IF NOT EXISTS temp_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            place TEXT NOT NULL,
            user TEXT NOT NULL,
            day TEXT NOT NULL,
            original_user TEXT,
            reservation_date DATE NOT NULL,
            restore_date DATE NOT NULL
        )
    """
    )
    connection.commit()
    connection.close()


def get_permanent_booking_for_day(username, day):
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        query = """
            SELECT place 
            FROM bookings 
            WHERE user = ? AND day = ? AND is_temp = 0
        """
        cursor.execute(query, (username, day))
        result = cursor.fetchone()

        if result:
            return {"place": result["place"]}
        return None

    except sqlite3.Error as e:
        print(f"Ошибка при выполнении запроса: {e}")
        return None

    finally:
        cursor.close()
        conn.close()


def get_user_temp_booking_for_day(username, day):
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        query = """
            SELECT place 
            FROM bookings 
            WHERE user = ? AND day = ? AND is_temp = 1
        """
        cursor.execute(query, (username, day))
        result = cursor.fetchone()

        if result:
            return {"place": result["place"]}
        return None

    except sqlite3.Error as e:
        print(f"Ошибка при выполнении запроса: {e}")
        return None

    finally:
        cursor.close()
        conn.close()


def create_booking(place, user, day):
    if not user:
        raise ValueError("User cannot be empty.")

    for attempt in range(5):
        try:
            connection = sqlite3.connect("database.db")
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO bookings (place, user, day, is_temp) VALUES (?, ?, ?, ?)",
                (place, user, day, False),
            )
            connection.commit()
            connection.close()
            break
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                time.sleep(1)
            else:
                raise e


def remove_booking(place, user, day, manually_deleted=False):
    for attempt in range(5):
        try:
            connection = sqlite3.connect("database.db")
            cursor = connection.cursor()

            if manually_deleted:
                cursor.execute(
                    "UPDATE bookings SET manually_deleted = 1 WHERE place = ? AND user = ? AND day = ?",
                    (place, user, day),
                )
            else:
                cursor.execute(
                    "DELETE FROM bookings WHERE place = ? AND user = ? AND day = ?",
                    (place, user, day),
                )

            cursor.execute(
                "SELECT COUNT(*) FROM bookings WHERE place = ? AND day = ? AND is_temp = 0",
                (place, day),
            )
            permanent_booking_exists = cursor.fetchone()[0] > 0

            if permanent_booking_exists:
                cursor.execute(
                    "DELETE FROM bookings WHERE place = ? AND user = ? AND day = ?",
                    (place, user, day),
                )

            cursor.execute(
                "DELETE FROM bookings WHERE place = ? AND day = ? AND is_temp = 1",
                (place, day),
            )
            cursor.execute(
                "DELETE FROM temp_bookings WHERE place = ? AND day = ?", (place, day)
            )

            connection.commit()
            connection.close()
            break
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                time.sleep(1)
            else:
                raise e


def delete_booking(place: str, day: str):
    max_attempts = 5
    attempt = 0

    while attempt < max_attempts:
        try:
            with sqlite3.connect("database.db") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM bookings WHERE place = ? AND day = ?", (place, day)
                )
                conn.commit()
            break
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                time.sleep(1)
                attempt += 1
            else:
                raise e
    else:
        print("Не удалось удалить бронирование после нескольких попыток.")


def check_is_permtemp_status(place: str, user: str, day: str) -> str:
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()

    try:
        while True:
            try:
                cursor.execute(
                    """
                    SELECT is_temp FROM bookings WHERE place = ? AND user = ? AND day = ?
                """,
                    (place, user, day),
                )

                result = cursor.fetchone()
                if result is not None:
                    return "Временная" if result[0] == 1 else "Перманентная"
                else:
                    return "Не забронировано"
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    time.sleep(1)
                else:
                    raise e
    finally:
        cursor.close()
        connection.close()


def delete_temp_booking(place: str, user: str, reservation_date: str):
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()

    try:
        while True:
            try:
                cursor.execute(
                    """ 
                    DELETE FROM temp_bookings 
                    WHERE place = ? AND user = ? AND reservation_date = ?
                """,
                    (place, user, reservation_date),
                )

                connection.commit()
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    time.sleep(1)
                else:
                    raise e
    finally:
        cursor.close()
        connection.close()


def delete_temp_bookings_from_temp_handler(place: str, user: str, day: str):
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()

    try:
        while True:
            try:
                cursor.execute(
                    """ 
                    DELETE FROM bookings 
                    WHERE place = ? AND user = ? AND day = ? AND is_temp = 1
                """,
                    (place, user, day),
                )

                connection.commit()
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    time.sleep(1)
                else:
                    raise e
    finally:
        cursor.close()
        connection.close()


def get_schedule():
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()
    cursor.execute("SELECT day, place, user FROM bookings")
    rows = cursor.fetchall()
    connection.close()

    schedule = {}
    for day, place, user in rows:
        if day not in schedule:
            schedule[day] = {}
        schedule[day][place] = user

    return schedule


def get_booked_places(place, day):
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()
    cursor.execute(
        "SELECT user FROM bookings WHERE place = ? AND day = ?", (place, day)
    )
    result = cursor.fetchone()
    connection.close()

    return result[0] if result else None


def get_booked_places_for_button(username):
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM bookings WHERE user = ? AND is_temp = 0", (username,)
    )
    count = cursor.fetchone()[0]
    connection.close()
    return count


def create_temp_booking(place, user, reservation_date, restore_date, day):
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()

    cursor.execute(
        "SELECT user FROM bookings WHERE place = ? AND day = ? AND is_temp = ?",
        (place, day, False),
    )
    result = cursor.fetchone()

    if result:
        original_user = result[0]
        cursor.execute(
            "INSERT INTO temp_bookings (place, user, day, original_user, reservation_date, restore_date) VALUES (?, ?, ?, ?, ?, ?)",
            (place, user, day, original_user, reservation_date, restore_date),
        )
        cursor.execute(
            "DELETE FROM bookings WHERE place = ? AND day = ? AND is_temp = ?",
            (place, day, False),
        )
    else:
        cursor.execute(
            "INSERT INTO temp_bookings (place, user, day, reservation_date, restore_date) VALUES (?, ?, ?, ?, ?)",
            (place, user, day, reservation_date, restore_date),
        )

    cursor.execute(
        "INSERT OR REPLACE INTO bookings (place, user, day, is_temp) VALUES (?, ?, ?, ?)",
        (place, user, day, True),
    )

    connection.commit()
    connection.close()


def restore_bookings():
    today = datetime.date.today()

    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()

    cursor.execute(
        "SELECT place, day, original_user FROM temp_bookings WHERE restore_date < ?",
        (today,),
    )
    rows = cursor.fetchall()

    for row in rows:
        place, day, original_user = row
        print(f"Restoring booking for {place} on {day} by {original_user}.")

        if original_user:
            cursor.execute(
                "SELECT manually_deleted FROM bookings WHERE place = ? AND day = ? AND user = ?",
                (place, day, original_user),
            )
            result = cursor.fetchone()
            if result and result[0]:
                print(
                    f"Permanent booking for {original_user} was manually deleted. Not restoring."
                )
            else:
                cursor.execute(
                    "INSERT OR REPLACE INTO bookings (place, user, day, is_temp) VALUES (?, ?, ?, ?)",
                    (place, original_user, day, False),
                )

        cursor.execute(
            "DELETE FROM bookings WHERE place = ? AND day = ? AND is_temp = 1",
            (place, day),
        )

        cursor.execute(
            "DELETE FROM temp_bookings WHERE place = ? AND day = ?", (place, day)
        )

    cursor.execute("DELETE FROM temp_bookings WHERE restore_date < ?", (today,))

    connection.commit()
    connection.close()


def restore_bookings_manually(place, day):
    print(f"restore_bookings_manually called for place {place} on day {day}")
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()

    cursor.execute(
        "SELECT original_user FROM temp_bookings WHERE place = ? AND day = ?",
        (place, day),
    )
    result = cursor.fetchone()

    if result and result[0]:
        original_user = result[0]

        cursor.execute(
            "SELECT manually_deleted FROM bookings WHERE place = ? AND day = ? AND user = ?",
            (place, day, original_user),
        )
        result_manual = cursor.fetchone()

        if result_manual and result_manual[0]:
            print(
                f"Permanent booking for {original_user} was manually deleted. Not restoring."
            )
        else:
            cursor.execute(
                "INSERT OR REPLACE INTO bookings (place, user, day, is_temp) VALUES (?, ?, ?, ?)",
                (place, original_user, day, False),
            )
            print(
                f"Booking for {original_user} on {place} for {day} has been restored."
            )

        cursor.execute(
            "DELETE FROM temp_bookings WHERE place = ? AND day = ?", (place, day)
        )
        print(f"Temporary booking on {place} for {day} has been removed.")

    connection.commit()
    connection.close()


def get_temp_booked_info(place, day):
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()

    try:
        cursor.execute(
            "SELECT user, original_user FROM temp_bookings WHERE place = ? AND day = ?",
            (place, day),
        )
        result = cursor.fetchone()

        if result:
            user, original_user = result
            return {"user": user, "original_user": original_user}
        else:
            return {}
    finally:
        connection.close()


def get_temp_booked_places(place, day):
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()

    cursor.execute(
        "SELECT user FROM temp_bookings WHERE place = ? AND day = ?", (place, day)
    )
    temp_user = cursor.fetchone()

    if temp_user:
        connection.close()
        return temp_user[0], True

    cursor.execute(
        "SELECT user FROM bookings WHERE place = ? AND day = ?", (place, day)
    )
    perm_user = cursor.fetchone()

    connection.close()

    if perm_user:
        return perm_user[0], False
    else:
        return None, False
