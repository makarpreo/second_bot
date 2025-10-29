import mysql.connector
from mysql.connector import Error
from typing import Optional, List, Tuple, Any, Union

from mysql.connector.abstracts import MySQLConnectionAbstract
from mysql.connector.pooling import PooledMySQLConnection

from config import *
from pyvin import *
import datetime


def vin_info(vin):
    try:
        vehicle = VIN(str(vin))
        return vehicle.Make, vehicle.Model, vehicle.ModelYear
    finally:
        return ' '


class Table:
    """Родительский класс для работы с таблицами БД"""

    def __init__(self):
        self.table_name = 'main'

    @staticmethod
    def get_db_connection() -> None | PooledMySQLConnection | MySQLConnectionAbstract:
        """Создает и возвращает соединение с MySQL"""
        try:
            return mysql.connector.connect(**DB_CONFIG)
        except Error as e:
            print(f"Ошибка подключения к MySQL: {e}")
            return None

    @staticmethod
    def print_row(row: Tuple) -> None:
        """Форматированный вывод строки"""
        print('| ' + ' | '.join(map(str, row)) + ' |')

    def execute_query(self, query: str, params: Tuple = None,
                      fetch: bool = False) -> Optional[Union[List[Tuple], int]]:
        """Универсальный метод выполнения запросов"""
        conn = self.get_db_connection()
        if not conn or not conn.is_connected():
            return None

        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())

            if fetch:
                result = cursor.fetchall()
            else:
                conn.commit()
                result = cursor.rowcount

            return result

        except Exception as ex:
            if not fetch:
                conn.rollback()
            print(f'Ошибка при выполнении запроса: {ex}')
            return None
        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()

    def check_day(self, date):
        query = f'select date, time, duration from main where date=%s and status <> 0;'
        results = self.execute_query(query, (date,), fetch=True)
        clear_time = {'10': 1, '11': 1, '12': 1, '13': 1, '14': 1, '15': 1, '16': 1, '17': 1, '18': 1, }
        if results:
            for row in results:
                for i in range(row[2]):
                    clear_time[str(row[1] + i)] = 0
            print(clear_time)
        else:
            print(f"ошибка")
        return clear_time

    def print_rows(self) -> None:
        """Выводит все строки таблицы"""
        query = f'SELECT * FROM {self.table_name};'
        results = self.execute_query(query, fetch=True)

        if results:
            for row in results:
                self.print_row(row)
        else:
            print(f"Таблица {self.table_name} пуста или произошла ошибка")

    def add(self, data):
        print(data)
        query = f'INSERT INTO second.main (date, time, user_id, problem, parts, mechanic, status) VALUES (%s, %s, %s, %s, %s, %s, 1)'
        result = self.execute_query(query, (data[0], data[1], data[2], data[3], data[5], data[6],))
        print(data[0], data[1], data[2], data[3], data[5], data[6])
        query = f'INSERT INTO second.cars (model, VIN) VALUES (%s, %s)'
        result1 = self.execute_query(query, (data[7], data[4]))
        query = f'INSERT INTO user (user_id, phone, username) VALUES (%s, %s)'
        result2 = self.execute_query(query, (data[2], data[8], data[9]))
        return (f"запись добавлена"
                if result and result1 and result2 else f'Ошибка')

    def change_column_by_id(self, id, column_name, data):
        # Добавить валидацию имени колонки
        allowed_columns = ['date', 'time', 'problem', 'mechanic', 'status', 'confirmed', 'duration', 'lift']
        if column_name not in allowed_columns:
            raise ValueError(f"Недопустимое имя колонки: {column_name}")
        query = 'UPDATE main SET {} = %s WHERE id = %s'.format(column_name)
        result = self.execute_query(query, (data, id,))
        return (f"поле изменено"
                if result else f'Ошибка')

    def today_appointments(self):
        query = 'SELECT time, problem, mechanic, duration, lift FROM second.main WHERE date = %s and status <> 0;'
        result = self.execute_query(query, (str(datetime.date.today()),), fetch=True)
        print(result)
        return result

    def appointments_by_date(self, date):
        query = 'SELECT time, problem, mechanic, duration, lift FROM second.main WHERE date = %s ORDER BY time;'
        result = self.execute_query(query, (date,), fetch=True)
        return result

    def not_confirmed_appointments(self):
        query = 'SELECT id, date, time, problem FROM second.main WHERE confirmed = 0;'
        result = self.execute_query(query, fetch=True)
        return result

    def show_mech_list(self):
        query = 'SELECT time, problem, mechanic FROM second.main WHERE mechanic = %s;'
        result = self.execute_query(query, fetch=True)
        return result

    def get_workload_by_date(self, target_date):
        """
        Проверяет загруженность на конкретную дату по часам (с 10 до 18)
        Возвращает словарь вида {'10': 3, '11': 2, '12': 3, '13': 0, ...}
        где значения: 0 - нет данных, 1 - низкая, 2 - средняя, 3 - высокая загруженность
        """
        query = '''
        SELECT time, duration 
        FROM main 
        WHERE date = %s AND time IS NOT NULL AND duration IS NOT NULL;
        '''

        results = self.execute_query(query, (target_date,), fetch=True)

        # Инициализируем словарь только для рабочих часов (10-18)
        workload = {str(hour).zfill(2): 0 for hour in range(10, 19)}

        # Словарь для подсчета количества записей по часам (только 10-18)
        hour_count = {str(hour).zfill(2): 0 for hour in range(10, 19)}

        # Обрабатываем результаты запроса
        for result in results:
            time_str = str(result[0]).zfill(2)  # Время в формате '10', '17' и т.д.
            duration = result[1] or 0  # Продолжительность, если NULL то 0

            # Преобразуем время в число
            try:
                start_hour = int(time_str)
            except (ValueError, TypeError):
                continue

            # Учитываем продолжительность работы только в пределах рабочего дня (10-18)
            for hour_offset in range(duration):
                current_hour = start_hour + hour_offset
                hour_key = str(current_hour).zfill(2)

                # Учитываем только часы с 10 до 18 включительно
                if hour_key in hour_count:
                    hour_count[hour_key] += 1

        # Определяем уровень загруженности для каждого часа
        for hour, count in hour_count.items():
            if count == 0:
                workload[hour] = 0  # Нет записей
            elif count == 1:
                workload[hour] = 1  # Низкая загруженность
            elif count == 2:
                workload[hour] = 2  # Средняя загруженность
            else:
                workload[hour] = 3  # Высокая загруженность

        return workload


class Appointment(Table):

    def __init__(self, id):
        self.table_name = 'main'
        self.id = id

    def change_date_time(self, time, date):
        query = 'UPDATE second.main SET date = %s, time = %s WHERE id = %s;'
        result = self.execute_query(query, (date, time, self.id,))
        return result, 'correct'

    def set_mechanic(self, mechanic):
        query = 'UPDATE second.main SET mechanic = %s WHERE id = %s;'
        result = self.execute_query(query, (mechanic, self.id,))
        print(result)
        return result

    def delete_app(self):
        query = 'UPDATE main SET status = 0 WHERE id = %s;'
        result = self.execute_query(query, (self.id,))
        return 'Запись удалена' if result == 1 else 'Ошибка, запись не удалена'

    def confirm_appointment(self):
        query = 'UPDATE second.main SET confirmed = 1 WHERE id = %s;'
        result = self.execute_query(query, (self.id,))
        return result

    def set_duration(self, duration):
        query = f'UPDATE second.main SET duration = %s WHERE id = %s;'
        result = self.execute_query(query, (duration, self.id,))
        return result

    def set_problem(self, problem):
        query = f'UPDATE main SET problem = %s WHERE id = %s;'
        result = self.execute_query(query, (problem, self.id,))
        return result

    def set_lift(self, lift):
        query = f'UPDATE second.main SET lift = %s WHERE id = %s;'
        result = self.execute_query(query, (lift, self.id,))
        return result

    def info(self):
        query = 'SELECT date, time, problem, mechanic, duration, lift, user_id FROM main WHERE id = %s;'
        result = self.execute_query(query, (self.id,), fetch=True)
        return result

    def info_by_user(self, user_id):
        query = 'SELECT date, time, problem, mechanic, duration, lift, VIN FROM main WHERE user_id = %s ORDER BY id DESC LIMIT 1;' #phone, username,JOIN user using(user_id)
        result = self.execute_query(query, (user_id,), fetch=True)
        print(result)
        date, time, problem, mechanic, duration, lift, vin = result[0]
        return date, time, problem, mechanic, duration, lift, vin


# Пример использования
if __name__ == '__main__':
    table = Table()
    ap = Appointment(0)
    # table.add(['test', 15, 'test', 'test', 'test', 'test', 'test'])
    # table.change_column_by_id(1, 'time', 14)
    # cars.print_note(7)
    print(ap.info_by_user(5506674973))
    # cars.show_active_list()
    print('success')
