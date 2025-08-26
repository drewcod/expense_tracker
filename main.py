import tabulate
import sys
from datetime import date
from typing import Tuple
import csv
import os
from pathlib import Path
import sqlite3

# ----- DB functions, etc -----
DB_PATH = Path("expenses.db")

def get_conn(db_path=DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(conn):
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY,
                amount INTEGER NOT NULL,
                category TEXT NOT NULL,
                desc TEXT DEFAULT 'No description',
                date TEXT NOT NULL                  -- ISO date string
            )
        """)

def add_expense(conn, amount, category, desc, date):
    with conn:
        cur = conn.execute(
            "INSERT INTO expenses (amount, category, desc, date) VALUES (?, ?, ?, ?)",
            (amount, category, desc, date)
        )
    return cur.lastrowid

def list_expenses(conn, category, start, end, desc=None):
    args, params = [], []

    if desc is not None:
        args.append("desc LIKE ?")
        params.append(desc)

    if end is not None:
        args.append("DATE(date) BETWEEN ? AND ?")
        params.append(start)
        params.append(end)
    else:
        if start is not None:
            args.append("DATE(date) = ?")
            params.append(start)

    if category != 'all':
        args.append("category LIKE ?")
        params.append(category)

    sql = "SELECT id, amount, category, desc, date FROM expenses"
    
    if len(args) != 0:
        sql += " WHERE "
    
    for arg in args:
        sql += f"{arg} AND "
    
    if len(args) != 0:
        sql = sql[:len(sql)-4]

    sql += " ORDER BY date DESC"

    return conn.execute(sql, params).fetchall()

# ----------

# class for each expense  
class Expense:
    def __init__(self, amount: int, category: str | None = None, date: date | None = None, desc: str | None = None):
        self.amount = amount
        self.category = category
        self.date = date
        self.desc = desc

# convert a string in the form 'MM/DD/YYYY' to 'YYYYMMDD' so that it can be stored as a datetime.date object
def convert_str_to_date(string: str) -> date:
    try:
        arr = string.split('/')
        if len(arr[0]) < 2:
            arr[0] = f'0{arr[0]}'
        if len(arr[1]) < 2:
            arr[1] = f'0{arr[1]}'
        return date.fromisoformat(f'{arr[2]}{arr[0]}{arr[1]}')
    except IndexError:
        return None

# convert date object to string of the form 'MM/DD/YYYY'
def convert_date_to_string(date1: date) -> str:
    arr = str(date1).split('-')
    return f'{arr[1]}/{arr[2]}/{arr[0]}'

# parse a response given as a string in the format "category startdate enddate" where startdate can be 'all' and enddate can be blank
def parse_response(response: str) -> Tuple[str, date | None, date | None]:
    while True:
        words = response.split(' ')
        if len(words) > 3 or len(words) < 2:
            print('Please try again. Your response must be in the format \"category startdate (enddate)\" or \"category all\". Type 4 to return to the main menu.')
            words = input()
            if words == '4':
                return None
            continue
        category = words[0]
        if words[1] != 'all':
            start = convert_str_to_date(words[1])
            if start == None:
                print('Please enter a proper date in the format \"category startdate (enddate)\" or \"category all\". Type 4 to return to the main menu.')
                words = input()
                if words == '4':
                    return None
                continue
        else:
            start = None
        if len(words) > 2:
            end = convert_str_to_date(words[2])
            if end == None:
                print('Please enter a proper date in the format \"category startdate (enddate)\" or \"category all\". Type 4 to return to the main menu.')
                words = input()
                if words == '4':
                    return None
                continue
        else:
            end = None
        break
    
    return [category, start, end]

# read from the csv and filter according to category and date, then display the results
def view_logged_expenses(category: str, start: date | None, end: date | None, conn):
    headers = ['id', 'amount', 'category', 'date', 'desc']
    table = list_expenses(conn, category, start, end)
    print(tabulate.tabulate(table, headers=headers, tablefmt='github'))

# log expense in the csv
def log_expense(expense: Expense, conn):
    add_expense(conn, expense.amount, expense.category, expense.desc, expense.date)

# calculate total spending or spending by category or by date and display result
def summarize_spending(category: str, start: date | None, end: date | None, conn):
    total = 0
    headers = ['id', 'amount', 'category', 'date', 'desc']
    rows = list_expenses(conn, category, start, end)
    for row in rows:
        row = dict(row)
        total += row['amount']

    cat = f'the {category} category' if category != 'all' else 'all categories'
    if not start:
        daterange = ''
    elif not end:
        daterange = f' on {convert_date_to_string(start)}'
    else:
        daterange = f' from {convert_date_to_string(start)} to {convert_date_to_string(end)}'
    print(f'The total for {cat}{daterange} is: {total}')

# loop through main logic, with checking responses and returning to main menu or quit when 4 is typed
def main():
    conn = get_conn()
    init_db(conn)
    num = 1
    while num != 4:
        try:
            print("Would you like to (1) View logged expenses, (2) Log a new expense, (3) Summarize spending, or (4) quit? Please type the number that corresponds to the option. At any point, type 4 to return to this menu.")
            num = int(input())
            if num == 4:
                break

            if num == 1:
                print("Please specify a category ('all' for all), then a date range ('all' for all, or enter one date for just that day). Example: food 8/20/2025 8/21/2025. Type 4 to return to main menu.")
                response = input()
                if response == '4':
                    continue

                args = parse_response(response)
                if args == None:
                    continue

                view_logged_expenses(args[0], args[1], args[2], conn)
            elif num == 2:
                print("Amount:")
                while True:
                    try:
                        amount = float(input())
                        break
                    except ValueError:
                        print('Please enter a number only')

                print("Category:")
                category = input()
                if category == '4':
                    continue

                print("Date:")
                date = input()
                if date == '4':
                    continue
                
                dateInFormat = convert_str_to_date(date)

                while not dateInFormat:
                    print('Please enter a valid date of the form MM/DD/YYYY.')
                    date = input()
                    if date == '4':
                        break
                    dateInFormat = convert_str_to_date(date)
                if date == '4':
                    continue

                print("Description:")
                desc = input()
                if desc == '4':
                    continue

                expense = Expense(amount, category, dateInFormat, desc)
                log_expense(expense, conn)
            elif num == 3:
                print("Please specify a category ('all' for all), then a date range ('all' for all, or enter one date for just that day). Example: food 8/20/2025 8/21/2025. Type 4 to return to main menu.")
                response = input()
                if response == '4':
                    continue

                args = parse_response(response)
                if args == None:
                    continue
                
                summarize_spending(args[0], args[1], args[2], conn)
            else:
                print('ERROR: Please enter a valid number')
        except ValueError:
            print('ERROR: Please enter a valid number')

main()