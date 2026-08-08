# importing the nessary modules
import pandas as pd
from datetime import datetime
from Path_mapper import SCHEDULE_CSV

# adding days
Days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# adding function to check today's date
def fetchstatus_today():
    return datetime.now().strftime("%A")

# adding function to load the schedule
def load_schedule():
    return pd.read_csv(SCHEDULE_CSV)

# adding function to handle the query
def query_handler(keyword, data):
    # defining what is keyword
    keyword = keyword.lower().strip()

    # this part is used when user is specifically asked question about the weekdays
    for day in Days:
        # checking days in keyword condition
        if day.lower() in keyword:
            result = data[data["day"].str.lower() == day.lower()]
            # if schedule didn't have anything
            if result.empty:
                return f"[Fox]: No Classes found for {day}"
            return result

    # query : If user asked about book needed question
    for book in keyword:
        # fetching about toda status via fetchstatus_today()
        today = fetchstatus_today()
        result = data[data["day"].str.lower() == today.lower()]
        # if schedule didn't have anything
        if result.empty:
            return f"[Fox]: No classes today ({today}), no books needed."
        books = result["books_needed"].dropna().tolist()
        return f"[Fox]: Books for {today}: {', '.join(books) if books else 'none listed'}"

    # query : if keyword is releated today
    if "today" in keyword:
        # again fetching today's statsu via fetchstatus_today()
        today = fetchstatus_today()
        result = data[data["day"].str.lower() == today.lower()]
        #  again if schedule didn't have anything
        if result.empty:
            return f"[Fox]: No classes today ({today})"
        return result
    # if no match found 
    return "[Fox]: No match found — try a day name, 'today', or 'book'."

if __name__ == "__main__":
    data = load_schedule()
    while True:
        print("Activating Scheduler:")
        keyword = input("Scheduler: ")
        if keyword.lower() == "exit":
            break
        result = query_handler(keyword, data)
        print(result)
        print()
