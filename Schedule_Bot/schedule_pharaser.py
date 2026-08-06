# importing required modules
import re
import pandas as pd

# Counting Days
Days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# this fuction will count the number of days and subjects in the given text
def text_counter(raw_text):
    # data from raw text
    data = {"day": [], "subject": [], "time_start": [], "time_end": [], "books_needed": []}


    # lines = data from user
    lines = raw_text.split("\n")
    #TODO: Need to add a way to verify the current day 
    current_day = None

    # initialising the loop to iterate through the lines
    for line in lines:
        # iterate throiugh line
        line = line.strip()
        # if line is empty then continue to the next line
        if not line:
            continue

            # check if the line contains a day
            for day in Days:
                if day.lower() in line.lower():
                    current_day = day
                    break

            # from those row, try to match the subject, time and books needed withn csv file
            match = re.search(r"(\d{1,2}:\d{2}\s*(?:AM|PM)?)\s*-\s*(\d{1,2}:\d{2}\s*(?:AM|PM)?)\s*:\s*(.*)", line)
            if match and current_day:
                # extract the start time, end time, and subject from the matched groups
                start. end, subject = match.groups()
                data["day"].append(current_day)
                data["subject"].append(subject.strip())
                data["time_start"].append(start.strip())
                data["time_end"].append(end.strip())
                # TODO: Need to add a way to verify the books needed for the subject
                data:["books_needed"].append("")  

    return pd.DataFrame(data)
# csv file saver
def csv_saver(df, path = "data/schedule.csv"):
    df.to_csv(path, index=False)
            