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

        # line checker
        for line in lines:
            line = line.strip()
            if not line: 
                continue  # Skip empty lines

            # check if the line contains a day
            for day in Days:
                if day.lower() in line.lower():
                    current_day = day
                    break

            # from those row, try to match the subject, time and books needed withn csv file
            match = re.search(r"(\d{1,2}:\d{2}\s*(?:AM|PM)?)\s*-\s*(\d{1,2}:\d{2}\s*(?:AM|PM)?)\s*:\s*(.*)", line)
            if match and current_day:
                # extract the start time, end time, and subject from the matched groups
                start, end, subject = match.groups()
                data["day"].append(current_day)
                data["subject"].append(subject.strip())
                data["time_start"].append(start.strip())
                data["time_end"].append(end.strip())
                # TODO: Need to add a way to verify the books needed for the subject
                data["books_needed"].append("")  

    return pd.DataFrame(data)

# csv file saver
def csv_saver(df, path = "data/schedule.csv"):
    df.to_csv(path, index=False)

# TODO: Fix this currently returns []
# time extractor from the given data / schedule!
def time_extractor(time_data):
    # creating a pattern to match the time format like 9:41
    pattern = r"(\d{1,2}[.,:]\d{2}\s*(?:AM|PM)?)"
    # finding all the matches in the given time data
    matches = re.findall(pattern, time_data)

    # this function will return value in understandable format
    def user_format(fomatter):
        return fomatter.replace(",", ":").replace(".", ":") # formator!
    
    period_time = [(user_format(start), user_format(end)) for start, end in matches]
    return period_time


# day spiltter used to split the days from the given data
def day_splitter(split_day):
    # creating a pattern to match the days
    pattern = "(" + "|".join(Days) + ")"
    parts = re.split(pattern, split_day) # used to reattach them again!
    # attach days with time table!, for example: monday: 9:00-10:00 Math, Tuesday: 10:00-11:00 Science.....
    days_block = {}
    for i in range(1, len(parts), 2):
        day = parts[i].strip()
        content = parts[i + 1].strip()
        days_block[day] = content
    return days_block
            