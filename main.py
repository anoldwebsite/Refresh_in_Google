import datetime
import pprint
import time
import re
import hashlib
import random
import string
import getpass
import atexit
import signal
import gspread

from google.oauth2.service_account import Credentials
from oauth2client.service_account import ServiceAccountCredentials
from tabulate import tabulate

inventory = {}
users = {}

SHEET_ID = '1BhESPsCZcAoH3QsztBco9-qCFkuRBNI2rcxRmgyD4SM'
CREDENTIALS_FILE = "credentials.json"


def get_worksheet(sheet_name):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SHEET_ID)
    return spreadsheet.worksheet(sheet_name)


# Define a function to generate a random salt value
def generate_salt(length=16):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


# Define a function to hash a password with a salt value
def hash_password(password, salt):
    hash_obj = hashlib.sha256()
    hash_obj.update(password.encode() + salt.encode())
    return hash_obj.hexdigest()


# Define a function to check if a password matches a hashed password
def check_password(password, username):
    hashed_password = users[username]['password']
    salt = users[username]['salt']
    # salt = hashed_password[:32]
    return hashed_password == hash_password(password, salt)


# This function first deletes all data from the Google sheet Users and then write new data to it from users dictionary.
def update_users_sheet2():
    worksheet = get_worksheet('Users')
    # Get the list of existing users (excluding the header row)
    existing_users = worksheet.get_all_records()[1:]

    # Delete all the rows (excluding the header row)
    if existing_users:
        worksheet.delete_rows(2, len(existing_users))

    # Add the updated user information to the worksheet
    new_user_data = []
    for username, user_info in users.items():
        new_user_data.append([username, user_info['email'], user_info['password'], user_info['salt']])
    worksheet.append_rows(new_user_data)


def update_users_sheet():
    worksheet = get_worksheet('Users')
    # Get all user data from the worksheet
    users_sheet = worksheet.get_all_records()

    # Update or append each user's data in the worksheet
    for username, data in users.items():
        # Check if the user already exists in the worksheet
        user_found = False
        for i, user_data in enumerate(users_sheet):
            if user_data['username'] == username:
                user_found = True
                # Update the user's email and hashed password
                salt = data['salt']
                hashed_password = data['password']
                # hashed_password = hash_password(data['password'], salt)  # hashing the hash or hashing the password?

                # Encode the password and salt as hex strings before saving to Google sheet
                encoded_password = hashed_password.encode().hex()
                encoded_salt = salt.encode().hex()

                worksheet.update_cell(i + 2, 2, data['email'])
                worksheet.update_cell(i + 2, 3, encoded_password)
                worksheet.update_cell(i + 2, 4, encoded_salt)
                break

        # If the user doesn't exist in the worksheet, append a new row
        if not user_found:
            salt = generate_salt()
            hashed_password = hash_password(data['password'], salt)
            new_row = [username, data['email'], hashed_password.encode().hex(), salt.encode().hex()]
            worksheet.append_row(new_row)

    print("Users Google sheet updated successfully.")
    download_fresh_data()


# Define a function to reset a user's password
def reset_password():
    username = input("Enter your username: ")
    # Check if the username exists
    if username not in users:
        print("Username not found.")
        return False

    current_password = input("Enter your current password: ")
    # current_password = getpass.getpass(prompt='Enter your current password: ')
    # Check if the current password is correct
    if not check_password(current_password, username):
        print("Incorrect password.")
        return False

    new_password = input("Enter your new password: ")
    # new_password = getpass.getpass(prompt='Enter your new password: ')
    # Generate a new salt value
    salt = generate_salt()
    # Hash the new password with the new salt value
    hashed_password = hash_password(new_password, salt)
    # hashed_password = hash_password(new_password, salt=salt)
    # Update the user information with the new salt and password
    users[username]['salt'] = salt
    users[username]['password'] = hashed_password
    update_users_sheet()
    print("Password reset successful.")
    return True


# Define a function to register a new user
def register():
    worksheet = get_worksheet('Users')
    username = input("Enter your username: ")
    # Check if the username already exists
    if username in users:
        print("Username already exists.")
        return False

    email = input("Enter your E-mail: ")
    # Check if the E-mail already exists.
    if email in users:
        print("E-mail already exists.")
        return False

    password = input('Enter your password: ')

    # Generate a random salt value
    salt = generate_salt()
    # Hash the password with the salt
    hashed_password = hash_password(password, salt)
    # Store the user information in the dictionary
    users[username] = {
        'email': email,
        'password': hashed_password,
        'salt': salt
    }

    # Encode the password and salt as hex strings before saving to Google sheet
    encoded_password = hashed_password.encode().hex()
    encoded_salt = salt.encode().hex()

    # Append the new user data to the users worksheet
    worksheet.append_row([username, email, encoded_password, encoded_salt])
    load_users_from_google()
    print(f"User with username {username} registered successfully.")
    return True


def login():
    username = input("Enter your username: ")

    # Check if the username exists in the users dictionary
    if username not in users:
        print(f"{username} is not registered in our database. Please register first.")
        return False

    password = input("Enter your password: ")
    download_fresh_data()
    # Get the user's salt and password from the users dictionary
    salt = users[username]['salt']
    hashed_password = users[username]['password']

    # Hash the entered password with the user's salt value
    entered_password_hashed = hash_password(password, salt)

    # Check if the entered password matches the stored password hash
    if entered_password_hashed == hashed_password:
        print("Login successful.")
        return username
    else:
        print("Incorrect password.")
        return False


def load_users_from_google():
    worksheet_users = get_worksheet("Users")
    users_list = worksheet_users.get_all_records()
    users_local = {}
    for row in users_list:
        username = row['username']
        email = row['email']
        encoded_password = str(row['password'])
        encoded_salt = row['salt']
        # Decode the password and salt from hex strings
        password = bytes.fromhex(encoded_password).decode()
        salt = bytes.fromhex(encoded_salt).decode()
        users_local[username] = {
            'email': email,
            'password': password,
            'salt': salt
        }
        global users
        users = users_local
    return users_local


def load_history_from_google():
    return get_worksheet("History")


def load_inventory_from_google():
    return get_worksheet("Inventory")


def load_from_google_sheet():
    worksheet_inventory = load_inventory_from_google()
    worksheet_history = load_history_from_google()
    worksheet_users = load_users_from_google()

    # Get inventory from the Google Sheet and store it in the local dictionary.
    inventory_temp = {}
    invent_data = worksheet_inventory.get_all_values()
    for row in invent_data[1:]:
        serial_number, count = row
        inventory_temp[serial_number] = {"count": count, "history": []}

    # Get history from the Google Sheet and store it in the local dictionary's entry "history".
    hist_data = worksheet_history.get_all_values()
    for row in hist_data[1:]:
        serial_number, userName, type_, time_str = row
        t = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        entry = {"user_name": userName, "type": type_, "time": t}
        inventory_temp[serial_number]["history"].append(entry)

    return inventory_temp, worksheet_users


def print_inventory(invent):
    headers = ["Serial Number", "Count", "Last User", "Last Type", "Last Time"]
    rows = []
    for serial_number, data in invent.items():
        count = data["count"]
        history = data["history"]
        if history:
            last_entry = history[-1]
            last_user = last_entry.get("user_name", "")
            last_type = last_entry.get("type", "")
            last_time = last_entry.get("time", "")
            last_time_str = datetime.datetime.strftime(last_time, "%Y-%m-%d %H:%M:%S")
        else:
            last_user = ""
            last_type = ""
            last_time_str = ""

        rows.append([serial_number, count, last_user, last_type, last_time_str])

    print("{:<15} {:5} {:<10} {:<10} {:<30}".format(*headers))
    print("-" * 90)
    for row in rows:
        print("{:<15} {:<5} {:<10} {:<10} {:<30}".format(*row))


def print_all_users():
    worksheet_users = get_worksheet('Users')
    users_list = worksheet_users.get_all_records()
    print("{:<15} {:<30} {:<30}".format('Username', 'Email', 'Password'))
    for user in users_list:
        print("{:<15} {:<30} {:<30}".format(user['username'], user['email'], len(str(user['password'])) * '@'))


def is_valid_ritm_number(serial_number):
    if serial_number.startswith("LS.") and len(serial_number) == 15:
        return True
    if "RITM" in serial_number:
        if re.match("^(?=.*[a-zA-Z])(?=.*\d)[a-zA-Z\d]{11}$", serial_number):
            return True
        return False
    else:
        if re.match("^(?=.*[a-zA-Z])(?=.*\d)[a-zA-Z\d]{10}$", serial_number):
            return True
        return False


def check_in():
    """
    We first check if the serial number is valid and then check if it is present in the inventory.
    If the serial number is not present in the inventory, we inform the user that the item has already been check in.
    Otherwise, we add a new object to the local inventory and then insert a new row in the Google Inventory worksheet.
    We also insert one row in the worksheet History of the Google sheet to record the checkin.
    :return: Does not return anything.
    """
    print("================================")
    userName = login()
    if userName and userName == 'admin':
        print("To stop checking in assets, type the word stop and hit the enter button on the keyboard.\n")
        while True:
            ritm_number = input("Enter the RITM for check-in: ")
            if ritm_number == "stop":
                print("You have been logged out!")
                return
            if is_valid_ritm_number(ritm_number):
                if ritm_number in inventory:
                    print(f"Asset {ritm_number} has already been checked in!")
                    continue
                else:  # ritm_number is not in the inventory. New case. Adding a new item to inventory.
                    inventory[ritm_number] = {
                        "count": "1",
                        "history": [{
                            "user_name": userName,
                            "type": "Check-in",
                            "time": datetime.datetime.now()
                        }]
                    }
                    print(f"{ritm_number} added to inventory by {userName}.")
                invent = get_worksheet('Inventory')
                hist = get_worksheet('History')
                # Update row in Inventory worksheet in Google Sheet
                cell = invent.find(ritm_number)
                if cell:
                    row = cell.row
                    # The number 2 in the line below refers to the second column, which is where the count value should be updated for the specified ritm_number.
                    invent.update_cell(row, 2, inventory[ritm_number]["count"])
                else:
                    # If the cell is None, then the serial number does not exist in the worksheet yet. We add a new row for it.
                    invent.append_row([ritm_number, inventory[ritm_number]["count"]])

                # Add row to History worksheet in Google Sheet
                new_row = [ritm_number, userName, "checkin", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                hist.append_row(new_row)
            else:
                print("Error: ============> Invalid RITM number.")
                print("If you think the RITM is valid, please contact the admin.")
    else:
        print("Error: ============> You are not authorized to check in assets! Please contact the Admin")


def check_out():
    """
    We first check if the RITM number is valid and then check if it is present in the inventory. If the RITM number is present in the inventory and the count is greater than 0, we decrement the count by 1.
    :return: The function does not return anything.
    """
    print("================================")
    userName = login()
    if userName:
        print(
            "To stop checking out assets, type the word 'stop' in lower case, and hit the enter button on the keyboard.\n")
        while True:
            ritm_number = input("Enter the RITM number for check-out: ")
            if ritm_number == "stop":
                print("You have been logged out!")
                return
            if is_valid_ritm_number(ritm_number):
                if ritm_number in inventory:
                    count = int(inventory[ritm_number]["count"])
                    if count > 0:
                        count -= 1
                        inventory[ritm_number]["count"] = str(count)
                        obj = {
                            "user_name": userName,
                            "type": "Check-out",
                            "time": datetime.datetime.now()
                        }
                        inventory[ritm_number]["history"].append(obj)
                        print(f"{ritm_number} checked out by {userName}.")

                        # Update the Google sheet.
                        invent = get_worksheet('Inventory')
                        hist = get_worksheet('History')

                        # Add row to History worksheet in Google Sheet
                        new_row = [ritm_number, obj["user_name"], obj["type"],
                                   obj["time"].strftime("%Y-%m-%d %H:%M:%S")]
                        hist.append_row(new_row)  # At position 1 are the column headers.
                        # Update row in Inventory worksheet in Google Sheet
                        cell = invent.find(ritm_number)
                        row = cell.row
                        # The number 2 in the line below refers to the second column, which is where the count value should be updated for the specified ritm_number.
                        invent.update_cell(row, 2, count)
                    else:
                        print(
                            f"Error: ============> {ritm_number} has been checked out. You can check the history for this item from the main menu.")
                else:
                    print(
                        f"Error: ============> {ritm_number} is not in the inventory. This asset has not been checked in yet!")
            else:
                print("Error: ============> Invalid RITM number.")
    else:
        print("Error: ============> You are not authorized to check out assets! Please contact the admin")


# get_asset_history retrieves data directly from the local dictionary 'inventory' and nt from the Google sheet.
def get_asset_history(ritm_number):
    if not is_valid_ritm_number(ritm_number):
        print("Error: ===============> Invalid RITM number!")
        return

    if ritm_number not in inventory:
        print("No asset found with RITM number:", ritm_number)
        print("Either the RITM is invalid or an asset with this RITM number has not been checked in yet!")
        return

    download_fresh_data()  # This makes sure that new data is fetched to populate inventory and users dictionaries.
    asset_history = inventory[ritm_number]["history"]
    count = inventory[ritm_number]["count"]

    if not asset_history:
        print("No history found for the asset with RITM number:", ritm_number)
        return

    # Print asset history in a tabular form
    print(f"Asset History for RITM Number: {ritm_number}")
    print(f"Current Count: {count}")
    print("+------------------+----------------+---------------------+")
    print("| User Name        | Type           | Time                |")
    print("+------------------+----------------+---------------------+")
    for entry in asset_history:
        user_name = entry["user_name"]
        type_ = entry["type"]
        t_str = entry["time"].strftime("%Y-%m-%d %H:%M:%S")
        print(f"| {user_name:<16} | {type_:<14} | {t_str:<19} |")
    print("+------------------+----------------+---------------------+")

    return {"history": asset_history, "count": count}


# get_asset_history2 retrieves data directly from Google sheet and not from the local dictionary 'inventory'.
def get_asset_history2(ritm_number):
    if not is_valid_ritm_number(ritm_number):
        print("Error: Invalid RITM number.")
        return

    inventory_worksheet = get_worksheet('Inventory')
    history_worksheet = get_worksheet('History')

    history_data = history_worksheet.get_all_values()
    asset_history = []
    # The first row has headers, so starting the slice from row 1 to the end of rows below.
    for row in history_data[1:]:
        if row[0] == ritm_number:  # row[0] is the cell in column A in the Google Sheet in a particular row.
            asset_history.append({
                "user_name": row[1],
                "type": row[2],
                "time": datetime.datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S")
            })

    inventory_data = inventory_worksheet.get_all_values()

    for row in inventory_data[1:]:
        if row[0] == ritm_number:
            count = int(row[1])
            break
    else:
        print("No asset found with serial number:", ritm_number)
        return

    if not asset_history:
        print("No history found for the asset with serial number:", ritm_number)
        return

    # Print asset history in a tabular form
    print(f"Asset History for Serial Number: {ritm_number}")
    print(f"Current Count: {count}")
    print("+------------------+----------------+---------------------+")
    print("| User Name        | Type           | Time                |")
    print("+------------------+----------------+---------------------+")
    for entry in asset_history:
        user_name = entry["user_name"]
        type_ = entry["type"]
        t_str = entry["time"].strftime("%Y-%m-%d %H:%M:%S")
        print(f"| {user_name:<16} | {type_:<14} | {t_str:<19} |")
    print("+------------------+----------------+---------------------+")

    return {"history": asset_history, "count": count}


def search_asset(ritm_number):
    asset_data = get_asset_history(ritm_number)
    if not asset_data:
        print(f"No history found for {ritm_number}! This asset has never been checked in!")
        return
    asset_history = asset_data["history"]
    count = asset_data["count"]
    if asset_history:
        last_transaction = asset_history[-1]
        table = [["Current Count:", last_transaction.get('count', count)],
                 ["Last User:", last_transaction['user_name']],
                 ["Last Transaction Type:", last_transaction['type']],
                 ["Last Transaction Time:", last_transaction['time']]]
        print(f"\nDetails for Asset with Serial Number: {ritm_number}")
        print(tabulate(table, headers=["", ""], tablefmt="pipe"))


def download_fresh_data():
    inventory_local, users_local = load_from_google_sheet()
    global inventory
    global users
    inventory = inventory_local
    users = users_local


download_fresh_data()

while True:
    print("------------------------------")
    action = input("Type 1 to check in an asset, \n"
                   "Type 2 to check out an asset, \n"
                   "Type 3 to search an asset, \n"
                   "Type 4 to see the history of an asset, \n"
                   "Type 5 to print the inventory, \n"
                   "Type 6 to exit, \n"
                   "Type 7 to register an account, \n"
                   "Type 8 to change your password, \n"
                   "Type 9 to see all existing users' information, \n"
                   ">: ")
    if action == "1":
        user_name = login()
        if user_name and user_name == "admin":
            check_in()
        elif user_name:
            print("You are not authorized to check in assets! Please contact the admin to help you with checking in assets.")
        else:
            print("You are probably not a registered user. You can register an account from the main menu.")
    elif action == "2":
        check_out()
    elif action == "3":
        search_asset(input("Please type or scan the RITM of the asset: "))
    elif action == "4":
        get_asset_history(input("Please type the RITM of the asset: "))
    elif action == "5":
        print_inventory(inventory)
    elif action == "6":
        user_name = login()
        if user_name and user_name == "admin":
            print("You chose to shut down the application. Bye Bye!")
            break
        else:
            print("You are not authorized to stop this program!")
            print("You have been logged out!")
    elif action == "7":
        register()
        print_all_users()
    elif action == "8":
        reset_password()
    elif action == "9":
        print_all_users()
    else:
        print("Error: ===============> Invalid action. \n You need to select an option between 1 to 8\n\n")
        pprint.pprint(inventory)
