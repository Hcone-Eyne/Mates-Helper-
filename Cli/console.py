# importing the required libraries
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import pandas as pd

# Importing Roots
from Path_mapper import SCHEDULE_CSV, DATA_ROOT

# MOre imports
from Schedule_Bot.OCR_Extractor import extract_table, corrupt_finder, corrupt_fixer, review_edit
from bot import load_schedule, query_handler

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

# linking up console.py with main.py to be used when user called!
# this fuction used to choose what the user want, expanision of Schedule program
def run_scheduler():
    while True:
        # adding failsafe!
        try:
            # print the options
            console.print(Panel.fit(
                "[bold blue]1[/bold blue]. View current schedule\n"
                "[bold blue]2[/bold blue]. Upload new schedule\n"
                "[bold blue]3[/bold blue]. Ask the bot\n"
                "[bold blue]0[/bold blue]. Back to main menu",
                title = "[Fox]: Schedule"
            )
            )
            # letting user to choose
            choice = input("\n[Fox]: Choose: ").strip()

            # choice condition starts here
            if choice == "1":
                df = pd.read_csv(SCHEDULE_CSV)
                display_table(df)
            elif choice == "2":
                # update user a hint?
                console.print("[Fox]: Drag and Drop Works Too")
                image_path = input("\n[Fox]: Path to new schedule image: ").strip()

                # extracting the table
                df = extract_table(image_path)
                # find the corrupted details
                df = corrupt_finder(df)
                # fix the corrupted details
                df = corrupt_fixer(df)
                # let user review and edit the corrupted file
                df = review_edit(df)

                # reshape the long format
                long_df = text_counter(df)
                # save the file using saver function
                csv_saver(long_df, SCHEDULE_CSV)
                # update it to user
                console.print("[Fox]: Schedule updated!.")
            elif choice == "3":
                # load the scheduler
                df = load_schedule()
                # ask Fox about the schedule 
                keyword = input("[Fox]: Ask: ").strip()
                # it displays the schedule
                print(query_handler(keyword, df))
            # adding this to prevent infinte loop!
            elif choice == "0":
                break
        except Exception as e:
            console.print(f"[Fox]: Error Occured: {e}")
        # this catch the file not found error
        except FileNotFoundError:
            console.print(f"[Fox]: Couldn't find a file at '{image_path}' - Check the path and try again....")
            pass
            # this catch value not found error
        except ValueError:
            console.print("[Fox]: Invalid Input, Try again.....")
            pass


if __name__ == "__main__":
    # reading the csv file
    # NEW - using your Path_mapper constant!
    data = pd.read_csv(SCHEDULE_CSV)
    # displaying the data in a table format
    display_table(data)
    run_scheduler()