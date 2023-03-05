import datetime
import pprint
import time
import re
import getpass
import atexit
import signal
import gspread
from google.oauth2.service_account import Credentials
from oauth2client.service_account import ServiceAccountCredentials
from tabulate import tabulate

inventory = {}
users = {"cristian": "cristianpass", "ali": "alipass", "admin": "adminpass"}

SHEET_ID = '1BhESPsCZcAoH3QsztBco9-qCFkuRBNI2rcxRmgyD4SM'
CREDENTIALS_FILE = "credentials.json"


def get_worksheets(sheet_id, credentials_file):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(sheet_id)
    worksheet_inventory = spreadsheet.worksheet("Inventory")
    worksheet_history = spreadsheet.worksheet("History")
    return worksheet_inventory, worksheet_history


def load_from_google_sheet():
    worksheet_inventory, worksheet_history = get_worksheets(SHEET_ID, CREDENTIALS_FILE)
    invent_data = worksheet_inventory.get_all_values()
    headers = invent_data[0]
    inventory_from_googlesheet = {}
    for row in invent_data[1:]:
        serial_number, count = row
        inventory_from_googlesheet[serial_number] = {"count": count, "history": []}

    hist_data = worksheet_history.get_all_values()
    headers = hist_data[0]
    for row in hist_data[1:]:
        serial_number, userName, type_, time_str = row
        t = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        entry = {"user_name": userName, "type": type_, "time": t}
        inventory_from_googlesheet[serial_number]["history"].append(entry)
    return inventory_from_googlesheet  # return the dictionary as a Python object


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


def is_valid_serial_number(serial_number):
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


def save_to_google_sheet(inventory_edited):
    invent, history = get_worksheets(SHEET_ID, CREDENTIALS_FILE)
    # Worksheet Inventory
    invent.clear()  # clear the existing contents of the sheet
    # write the headers
    headers = ["Serial Number", "Count"]
    invent.append_row(headers)
    # write the inventory data
    for serial_number, data in inventory_edited.items():
        count = data["count"]
        row = [serial_number, count]
        invent.append_row(row)
    # Worksheet History
    history.clear()  # clear the existing contents of the sheet
    headers = ["Serial Number", "Name", "Type", "Time"]
    history.append_row(headers)
    for serial_number, data in inventory_edited.items():
        for entry in data["history"]:
            user_name = entry["user_name"]
            t = entry["time"]
            t_str = t.strftime("%Y-%m-%d %H:%M:%S")
            type_ = entry["type"]
            row = [serial_number, user_name, type_, t_str]
            history.append_row(row)
    print("*********************************")
    print("Saving inventory to Google Sheet...")
    time.sleep(2)
    print("Inventory saved to Google Sheet")
    print("*********************************")


def login():
    while True:
        username = input("Enter your username: ")
        password = getpass.getpass(prompt='Enter your password: ')
        if username in users and users[username] == password:
            print("Login successful.")
            return username
        else:
            print("Invalid username or password.")
            return None


def is_valid_serial_number(serial_number):
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
    We first check if the serial number is valid and then check if it is present in the inventory. If the serial number is present in the inventory, we increment the count by 1. After updating the count in the inventory, we update the respective row in the Google sheet in the worksheet Inventory to represent the new count. We also insert one row in the worksheet History of the Google sheet to record the check-in.
    :return:
    """
    print("================================")
    userName = login()
    if userName:
        print("To stop checking in assets, type the word stop and hit the enter button on the keyboard.\n")
        while True:
            serial_number = input("Enter the serial number for check-in: ")
            if serial_number == "stop":
                print("You have been logged out!")
                return
            if is_valid_serial_number(serial_number):
                if serial_number not in inventory or (
                        serial_number in inventory and int(inventory[serial_number]["count"]) < 1):
                    count = 1
                    inventory[serial_number]["count"] = str(count)
                    obj = {
                        "user_name": userName,
                        "type": "Check-in",
                        "time": datetime.datetime.now()
                    }
                    inventory[serial_number]["history"].append(obj)
                    print(f"{serial_number} checked in by {userName}.")
                    invent, hist = get_worksheets(SHEET_ID, CREDENTIALS_FILE)
                    # Add row to History worksheet in Google Sheet
                    new_row = [serial_number, obj["user_name"], obj["type"], obj["time"].strftime("%Y-%m-%d %H:%M:%S")]
                    hist.append_row(new_row)
                    # Update row in Inventory worksheet in Google Sheet
                    cell = invent.find(serial_number)
                    row = cell.row
                    # The number 2 in the line below refers to the second column, which is where the count value should be updated for the specified serial_number.
                    invent.update_cell(row, 2, count)
                else:
                    print(f"Error: ============> {serial_number} is already in the inventory.")
            else:
                print("Error: ============> Invalid serial number.")
    else:
        print("Error: ============> You are not authorized to check in assets! Please contact the Admin")


def check_out():
    """
    We first check if the serial number is valid and then check if it is present in the inventory. If the serial number is present in the inventory and the count is greater than 0, we decrement the count by 1. If the count becomes 0, we remove the serial number from the inventory. After updating the count or removing the entry from the inventory, we update the respective row in the Google sheet in the worksheet Inventory to represent the new count. We also insert one row in the worksheet History of the Google sheet to record the checkout.
    :return:
    """
    print("================================")
    userName = login()
    if userName:
        print("To stop checking out assets, type the word stop and hit the enter button on the keyboard.\n")
        while True:
            serial_number = input("Enter the serial number for check-out: ")
            if serial_number == "stop":
                print("You have been logged out!")
                return
            if is_valid_serial_number(serial_number):
                if serial_number in inventory:
                    count = int(inventory[serial_number]["count"])
                    if count > 0:
                        count -= 1
                        inventory[serial_number]["count"] = str(count)
                        obj = {
                            "user_name": userName,
                            "type": "Check-out",
                            "time": datetime.datetime.now()
                        }
                        inventory[serial_number]["history"].append(obj)
                        print(f"{serial_number} checked out by {userName}.")
                        invent, hist = get_worksheets(SHEET_ID, CREDENTIALS_FILE)
                        # Add row to History worksheet in Google Sheet
                        new_row = [serial_number, obj["user_name"], obj["type"],
                                   obj["time"].strftime("%Y-%m-%d %H:%M:%S")]
                        # new_row = [serial_number, obj["user_name"], obj["type"], obj["type"].strftime("%Y-%m-%d %H:%M:%S")]
                        hist.append_row(new_row)  # At position 1 are the column headers.
                        # Update row in Inventory worksheet in Google Sheet
                        cell = invent.find(serial_number)
                        row = cell.row
                        # The number 2 in the line below refers to the second column, which is where the count value should be updated for the specified serial_number.
                        invent.update_cell(row, 2, count)
                    else:
                        print(f"Error: ============> {serial_number} is out of stock.")
                else:
                    print(f"Error: ============> {serial_number} is not in the inventory.")
            else:
                print("Error: ============> Invalid serial number.")
    else:
        print("Error: ============> You are not authorized to check out assets! Please contact the Admin")


# get_asset_history retrieves data directly from the local dictionary 'inventory' and nt from the Google sheet.
def get_asset_history(serial_number):
    if not is_valid_serial_number(serial_number):
        print("Error: Invalid serial number.")
        return

    if serial_number not in inventory:
        print("No asset found with serial number:", serial_number)
        return

    asset_history = inventory[serial_number]["history"]
    count = inventory[serial_number]["count"]

    if not asset_history:
        print("No history found for the asset with serial number:", serial_number)
        return

    # Print asset history in a tabular form
    print(f"Asset History for Serial Number: {serial_number}")
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
def get_asset_history2(serial_number):
    if not is_valid_serial_number(serial_number):
        print("Error: Invalid serial number.")
        return
    inventory_worksheet, history_worksheet = get_worksheets(SHEET_ID, CREDENTIALS_FILE)
    history_data = history_worksheet.get_all_values()

    asset_history = []
    # The first row has headers, so starting the slice from row 1 to the end of rows below.
    for row in history_data[1:]:
        if row[0] == serial_number:  # row[0] is the cell in column A in the Google Sheet in a particular row.
            asset_history.append({
                "user_name": row[1],
                "type": row[2],
                "time": datetime.datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S")
            })

    inventory_data = inventory_worksheet.get_all_values()

    for row in inventory_data[1:]:
        if row[0] == serial_number:
            count = int(row[1])
            break
    else:
        print("No asset found with serial number:", serial_number)
        return

    if not asset_history:
        print("No history found for the asset with serial number:", serial_number)
        return

    # Print asset history in a tabular form
    print(f"Asset History for Serial Number: {serial_number}")
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


def search_asset(serial_number):
    asset_data = get_asset_history(serial_number)
    if not asset_data:
        return
    asset_history = asset_data["history"]
    count = asset_data["count"]
    if asset_history:
        last_transaction = asset_history[-1]
        table = [["Current Count:", last_transaction.get('count', count)],
                 ["Last User:", last_transaction['user_name']],
                 ["Last Transaction Type:", last_transaction['type']],
                 ["Last Transaction Time:", last_transaction['time']]]
        print(f"\nDetails for Asset with Serial Number: {serial_number}")
        print(tabulate(table, headers=["", ""], tablefmt="pipe"))


inventory = load_from_google_sheet()

while True:
    print("------------------------------")
    action = input("Type 1 to check in an asset, \n"
                   "Type 2 to check out an asset, \n"
                   "Type 3 to search an asset, \n"
                   "Type 4 to see the history of an asset, \n"
                   "Type 5 to print the inventory, \n"
                   "or Type 6 to exit \n"
                   ">: ")
    if action == "1":
        check_in()
    elif action == "2":
        check_out()
    elif action == "3":
        search_asset(input("Write the RITM, Serial number or LS_ID of an asset: "))
    elif action == "4":
        get_asset_history(input("Write the RITM, Serial number or LS_ID of an asset: "))
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
    else:
        print("Error: ===============> Invalid action. \n You need to select an option between 1 to 6\n\n")
        pprint.pprint(inventory)
