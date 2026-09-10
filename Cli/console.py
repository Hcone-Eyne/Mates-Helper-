# importing the required libraries
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import pandas as pd
from Schedule_Bot.schedule_pharaser import csv_saver, reshape_to_long

# Importing Roots
from Path_mapper import SCHEDULE_CSV, DATA_ROOT

# MOre imports
from Schedule_Bot.OCR_Extractor import extract_table, corrupt_finder, corrupt_fixer, review_edit
from bot import load_schedule, query_handler
from Finance_bot.Expense_analyzer import run_expense_analyzer
from agent.ollama.ollama_agent import FoxAgent

# from Finance_bot
from Finance_bot.operations_finder import operation_finder
from Memory.memory_storer import memory_lister, memory_catcher

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
            # this prevent reprint
            os.system('clear')
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
                input("\nPress Enter to continue...")
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
                long_df = reshape_to_long(df)
                # save the file using saver function
                csv_saver(long_df, SCHEDULE_CSV)
                # update it to user
                console.print("[Fox]: Schedule updated!.")
                input("\nPress Enter to continue...")
            elif choice == "3":
                # load the scheduler
                df = load_schedule()
                # ask Fox about the schedule
                keyword = input("[Fox]: Ask: ").strip()
                # it displays the schedule
                print(query_handler(keyword, df))
                input("\nPress Enter to continue...")
            # adding this to prevent infinte loop!
            elif choice == "0":
                break
        except Exception as e:
            console.print(f"[Fox]: Error Occured: {e}")
            input("\nPress Enter to continue...")
        except FileNotFoundError:
            console.print(f"[Fox]: Couldn't find a file at '{image_path}' - Check the path and try again....")
            input("\nPress Enter to continue...")
        except ValueError:
            console.print("[Fox]: Invalid Input, Try again.....")
            input("\nPress Enter to continue...")

def run_finance_bot():
    # this loops the finance bot until user wants to exit
    while True:
        # this try-except block is used to catch any errors that may occur during the execution of the finance bot
        try:
            # this prevents the reprint issue!
            os.system('clear')
            # print the options
            console.print(Panel.fit(
                "[bold blue]1[/bold blue]. Perform an operation\n"
                "[bold blue]2[/bold blue]. Analyze expense statement (PDF/CSV)\n"
                "[bold blue]0[/bold blue]. Back to main menu",
                title = "[Fox]: Finance Bot"
            )
            )
            # letting user to choose
            choice = input("\n[Fox]: Choose: ").strip()

            # choice condition starts here
            if choice == "1":
                # to get expression from user
                expression = input("[Fox]: Enter the operation (or type Finished to exit): ").strip()
                # checking if user wants to exit the finance bot
                if expression.lower() == "finished":
                    console.print("[Fox]: Exiting Finance Bot.....")
                    memory_lister()  # call memory_lister to display previous operations
                    break

                # using the operation_finder function to perform the operation
                result = operation_finder(expression)
                # printing the result to the console
                console.print(f"[Fox]: Result: {result}")
                # this stores the expression and result in memory_log for future reference
                memory_catcher(expression, result)
                input("\nPress Enter to continue...")
            # if choice is 2, run the Expense_analyser!
            elif choice == "2":
                run_expense_analyzer()
                input("\nPress Enter to continue...")
            # adding this to prevent infinte loop!
            elif choice == "0":
                console.print("[Fox]: Exiting Finance Bot.....")
                break
        # this catch the file not found error
        except Exception as e:
            console.print(f"[Fox]: Error Occured: {e}")
            input("\nPress Enter to continue...")
        # this catch value not found error
        except ValueError:
            console.print("[Fox]: Invalid Input, Try again.....")
            input("\nPress Enter to continue...")
        # this catches the keyboard interrupt error to exit the finance bot.....
        except KeyboardInterrupt:
            console.print("[Fox]: Exiting Finance Bot.....")
            memory_lister()  # calls the memory_lister to display previous operations

def run_file_manager():
    from File_Manager import organizer, db
    from pathlib import Path
    organizer.ensure_vault()
    while True:
        try:
            os.system('clear')
            console.print(Panel.fit(
                "[bold blue]scan[/bold blue]                 - pull in anything new from Inbox\n"
                "[bold blue]find <term>[/bold blue]          - search the vault by keyword\n"
                "[bold blue]ls [category][/bold blue]        - list everything (or one category)\n"
                "[bold blue]move <name> <category>[/bold blue] - re-file a result and teach Fox\n"
                "[bold blue]0[/bold blue] - back to main menu",
                title="[Fox]: File Manager"
            ))
            console.print(f"[Fox]: Drop files into {organizer.INBOX} anytime.")
            cmd = input("\n[Fox]: > ").strip()

            if cmd == "0":
                break
            elif cmd == "scan":
                new_files = [p for p in organizer.INBOX.iterdir() if p.is_file()]
                if not new_files:
                    console.print("[Fox]: Inbox is empty, nothing to file.")
                for path in new_files:
                    dest, category = organizer.organize_file(path)
                    console.print(f"[Fox]: Filed '{dest.name}' -> {category}")
                input("\nPress Enter to continue...")
            elif cmd.startswith("find "):
                query = cmd[len("find "):].strip()
                results = db.search_files(query)
                if not results:
                    console.print(f"[Fox]: Nothing matching '{query}'.")
                for r in results:
                    console.print(f"[Fox]: {r['name']}  ({r['category']})  -> {r['path']}")
                input("\nPress Enter to continue...")
            elif cmd == "ls" or cmd.startswith("ls "):
                category = cmd[3:].strip() or None
                results = db.list_all(category)
                if not results:
                    console.print("[Fox]: Nothing indexed yet — try 'scan' first.")
                for r in results:
                    console.print(f"[Fox]: [{r['category']}] {r['name']}")
                input("\nPress Enter to continue...")
            elif cmd.startswith("move "):
                parts = cmd[len("move "):].split()
                if len(parts) != 2:
                    console.print("[Fox]: Usage: move <filename> <category>")
                else:
                    name, new_category = parts
                    matches = [r for r in db.list_all() if r["name"] == name]
                    if not matches:
                        console.print(f"[Fox]: Couldn't find '{name}' in the vault.")
                    else:
                        dest = organizer.move_and_learn(Path(matches[0]["path"]), new_category)
                        console.print(f"[Fox]: Moved to {dest} — I'll remember that for next time.")
                input("\nPress Enter to continue...")
            else:
                console.print("[Fox]: Didn't catch that — try scan, find, ls, or move.")
                input("\nPress Enter to continue...")
        except KeyboardInterrupt:
            console.print("[Fox]: Exiting File Manager.....")
            break
        except Exception as e:
            console.print(f"[Fox]: Error Occured: {e}")
            input("\nPress Enter to continue...")

# this function is ment for to run the fox agent, which performs a agentic tasks
def run_fox_agent():

    os.system("clear")

    # Import tool list so we can show it in the panel
    from agent.ollama.tools import TOOLS

    try:
        agent = FoxAgent()
        tool_names = ", ".join(TOOLS.keys()) if TOOLS else "(none)"
        console.print(
            Panel.fit(
                "\n".join(
                    [
                        "[bold green]Connected[/bold green]",
                        f"Model: [cyan]{agent.model}[/cyan]",
                        f"Tools: [yellow]{tool_names}[/yellow]",
                        "Type [bold]exit[/bold] to return.",
                    ]
                ),
                title = "[Fox]: Local Agent"
            )
        )
        while True:
                try:
                    # getting input / cmd
                    user_input = input("\n[You]: ").strip()

                    # valaditaing the input
                    if not user_input:
                        continue

                    # makin the input lower and checking for required keybord to exit
                    if user_input.lower() in {
                        "exit",
                        "quit",
                        "0"
                    }:
                        break

                    response = agent.ask(user_input)

                    console.print(f"\n[Fox]: {response}")

                except KeyboardInterrupt:
                    break

    except Exception as e:
        console.print(
            f"[red][Fox]: Agent error: {e}[/red]")

        input("\nPress Enter to continue...")

if __name__ == "__main__":
    # reading the csv file
    # NEW - using your Path_mapper constant!
    data = pd.read_csv(SCHEDULE_CSV)
    # displaying the data in a table format
    display_table(data)
    run_scheduler()