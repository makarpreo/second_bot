import mysql.connector
from mysql.connector import Error
from typing import Optional, List, Tuple, Any, Union
from config import *


class Table:
    """Родительский класс для работы с таблицами БД"""

    def __init__(self):
        self.table_name = 'main'

    @staticmethod
    def get_db_connection() -> Optional[mysql.connector.connection.MySQLConnection]:
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
        query = f'INSERT INTO main (date, time, user_id, problem, vin, parts, mechanic) VALUES (%s, %s, %s, %s, %s, %s, %s)'
        result = self.execute_query(query, (data[0], data[1], data[2], data[3], data[4], data[5], data[6],))
        return (f"запись добавлена"
                if result else f'Ошибка')

    def change_column_by_id(self, id, column_name, data):
        query = f'UPDATE main SET {column_name} = %s where id = %s'
        result = self.execute_query(query, (data, id,))
        return (f"поле изменено"
                if result else f'Ошибка')

# Пример использования
if __name__ == '__main__':
    table = Table()
    table.add(['test', 15, 'test', 'test', 'test', 'test', 'test'])
    # table.change_column_by_id(1, 'time', 14)
    # cars.print_note(7)
    # cars.show_active_list()
    print('success')
