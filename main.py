# importing nessary library
from rich.console import Console
from rich.panel import Panel
from Cli.console import run_scheduler
import pandas as pd
from Path_mapper import SCHEDULE_CSV


# imports from finance_bot!
from Cli.console import run_finance_bot

# adding console variable
console = Console()

# adding Menu Bar so it can be shown in the console!
def menu_bar():
    # adding options!
    console.print(Panel.fit(
    "[bold blue]1[/bold blue].Schedule\n"
    "[bold blue]2[/bold blue].Finance\n"
    "[bold blue]3[/bold blue].[On Progress...]\n"
    "[bold blue]4[/bold blue].Exit\n",
    title = "[Fox]: Main Menu"))

# this function let the user to choose and run program within menubar
def run():
    # adding loop to ask it repeatively
    while True:
        # showing the menu_bar
        menu_bar()
        # leting user to choose option
        console.print("[Fox]: Enter option.....")
        choice = input("\n<:=:>").strip()

        # choice based execution
        if choice == "1":
            print("[Fox]: Entering Schedule")
            run_scheduler()
        elif choice == "2":
            console.print("[Fox]: Preparing Finance Bot")
            run_finance_bot()
        elif choice == "3":
            console.print("[Fox]: Haptics module not built yet")
        elif choice == "4":
            console.print("[Fox]: See you Soon Boss.....")
            break
        else:
            console.print("[Fox]: Invalid option, try again.")


        
if __name__ == "__main__":
    run()