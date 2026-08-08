# importing the required libraries
from rich.console import Console
from rich.table import Table
import pandas as pd

# Importing Roots
from Path_mapper import SCHEDULE_CSV, DATA_ROOT

# importing OCR_Extractor and schedule_pharaser modules for CSV
from Schedule_Bot.OCR_Extractor import image_extractor
from Schedule_Bot.schedule_pharaser import day_splitter, time_extractor

# creating a console object
console = Console()

# creating a function to display the data in a table format
def display_table(data):
    # This gives a Big Tittle to the table (seen 1st)
    table = Table(title = "Schedule")

    # creating the columns of the table
    for column in data.columns:
        # adding the columns to the table
        table.add_column(column)

    # adding the rows to the table
    for _ , row in data.iterrows():
        # adding the rows to the table
        table.add_row(*[str(value) for value in row])

    # printing the table to the console
    console.print(table)

if __name__ == "__main__":
    # reading the csv file
    # NEW - using your Path_mapper constant!
    data = pd.read_csv(SCHEDULE_CSV)
    # displaying the data in a table format
    display_table(data)