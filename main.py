# importing nessary library
import os
from rich.console import Console
from rich.panel import Panel
from Cli.console import run_scheduler

# imports from finance_bot!
from Cli.console import run_finance_bot

# imports from fox agent
from Cli.console import run_fox_agent

# imports from file_manager
from Cli.console import run_file_manager

# imports from phone hub
from Cli.console import run_phone_hub

# adding console variable
console = Console()

# adding Menu Bar so it can be shown in the console!
def menu_bar():
    # adding options!
    console.print(Panel.fit(
        "[bold blue]1[/bold blue]. Schedule\n"
        "[bold blue]2[/bold blue]. Finance\n"
        "[bold blue]3[/bold blue]. Fox Agent\n"
        "[bold blue]4[/bold blue]. Files\n"
        "[bold blue]5[/bold blue]. Phone\n"
        "[bold blue]6[/bold blue]. Exit",
        title="[Fox]: Main Menu"
    ))

# this function let the user to choose and run program within menubar
def run():
    # adding loop to ask it repeatively
    while True:
        try:
            os.system('clear')
            # showing the menu_bar
            menu_bar()
            # leting user to choose option
            console.print("[Fox]: Enter option.....")
            choice = input("\n<:=:").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[Fox]: Session ended. Goodbye.")
            break

        # choice based execution
        if choice == "1":
            run_scheduler()
        elif choice == "2":
            run_finance_bot()
        elif choice == "3":
            run_fox_agent()
        elif choice == "4":
            run_file_manager()
        elif choice == "5":
            run_phone_hub()
        elif choice == "6":
            console.print("[Fox]: See you Soon Boss.....")
            break
        else:
            console.print("[Fox]: Invalid option, try again.")
            try:
                input("\nPress Enter to continue...")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[Fox]: Session ended. Goodbye.")
                break


        
if __name__ == "__main__":
    run()