# importing required modules
import re
import pandas as pd

# Counting Days
Days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# csv file saver
def csv_saver(df, path = "data/schedule.csv"):
    df.to_csv(path, index=False)