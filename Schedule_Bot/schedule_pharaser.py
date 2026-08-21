# importing required modules
import re
import pandas as pd

# Counting Days
Days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# csv file saver
def csv_saver(df, path = "data/schedule.csv"):
    df.to_csv(path, index=False)

# this function shapes the output to long_format
def reshape_to_long(data):
    # this is data format
    long_data = {"day": [], "subject": [], "time_start": [], "time_end": [], "books_needed": []}

    # adding colums data for day and period
    day_column = data.colums[0]
    period_colums = data.column[1:]

    # adding loop to iterate throught the schedule
    for _, row in data.iterrows(): # iteration through day column!
        day = row [day_column]
        # for itrating through period column
        for period in period_colums:
            subject = row[period]
            # developing codition for check
            if pd.isna(subject) or str(subject).strip() == "":
                continue

            # asusual adding things to format and add/remove data to the schedule
            times = str(period).replace("(", "").replace(")", "").split("-")
            time_start = times[0].strip() if len(times) > 0 else ""
            time_end = times[1].strip() if len(times) > 1 else ""

            long_data["day"].append(day)
            long_data["subject"].append(str(subject).strip())
            long_data["time_start"].append(time_start)
            long_data["time_end"].append(time_end)
            long_data["books_needed"].append("")

    # returning the data
    return pd.DataFrame(long_data)
