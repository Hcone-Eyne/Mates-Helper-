# this part stores all the previous finance bot operations and results......

# imoprting necessary modules
from rich.console import Console
from rich.panel import Panel
import pandas as pd
import plotext as plt2

console = Console()
# ading a variable to store the previous operations and results
memory_log = []

# creating a function to store the previous operations and results also it gets called after every operation is performed
def memory_catcher(expression, result):
    memory_log.append({"expression": expression, "result": result})

# this function handles the memmory log / eraser!
def memory_eraser():
    memory_log.clear()
    console.print("[Fox]: Memory erased.")

# this function is going to be used to pandas dataframe, so pandas and plotting tools can be used.....
def memory_dataframe():
    return pd.DataFrame(memory_log)

# creating a function after when user successfully performs an operation, this function will be called to ask user wheather to see the previous operations in grapg format and reveals a new menu!
def memory_lister():
    # fetching data from the memory_log and storing it in a pandas dataframe
    df = memory_dataframe()

    # adding condition to check if "df" is empty or not
    if df.empty:
        console.print("[Fox]: No previous operations found.")
        return

    # showing the menu!
    console.print(
    Panel.fit(
        "[bold blue]1.[/bold blue] Line graph (trend across entries)\n"
        "[bold blue]2.[/bold blue] Bar chart (each expression vs its result)\n"
        "[bold blue]3.[/bold blue] Histogram (distribution of results)\n"
        "[bold blue]4.[/bold blue] Erase memory\n"
        "[bold blue]0.[/bold blue] Skip",
        title="[Fox]: Visualization Options"
    )
)

    # asking user for choice
    choice = input("[Fox]: Enter your choice: ").strip()

    # conditions based on choice
    if choice == "1":
        # it will plot the line graph of the previous operations and results
        plot_line_line(df)
    elif choice == "2":
        # it will plot the bar chart of the previous operations and results
        plot_bar(df)
    elif choice == "3":
        # it will plot the histogram of the previous operations and results
        plot_histogram(df)
    elif choice == "4":
        # it will erase the memory of the previous operations and results
        memory_log.clear()
        return
    elif choice == "0":
        # it will skip the graphing of the previous operations and results
        console.print("[Fox]: Skipping the graphing of previous operations.")
        return
    else:
        # if user enters an invalid choice
        console.print("[Fox]: Invalid choice. Please try again.")

    # adding memory eraser feature
    memory_log.clear()
    console.print("[Fox]: Memory erased.")

# this function is going to show off the graph in line and rest is all we know1
def plot_line_line(df):
    plt2.plot(df.index.tolist(), df["result"].tolist())
    plt2.title("Results over Sessions")
    plt2.xlabel("Entry Number")
    plt2.ylabel("Result")
    plt2.grid(True, True)
    plt2.show()

# this function is going to show off the graph in bar chart
def plot_bar(df):
    plt2.bar(df["expression"].tolist(), df["result"].tolist())
    plt2.title("Results over Expressions")
    plt2.xlabel("Expression")
    plt2.ylabel("Result")
    plt2.tight_layout()
    plt2.show()

# this function is going to show off the graph in histogram
def plot_histogram(df): 
    plt2.hist(df["result"].tolist(), bins=10)
    plt2.title("Distribution of Results")
    plt2.xlabel("Result")
    plt2.ylabel("Frequency")
    plt2.grid(False, True)
    plt2.show()

if __name__ == "__main__":
    console.print("[bold green]Populating sample finance log data...[/bold green]\n")

    sample_data = [
        ("100 + 50", 150.0),
        ("200 * 1.05", 210.0),
        ("150 - 30", 120.0),
        ("500 / 2", 250.0),
        ("250 + 100", 350.0),
        ("120 * 1.2", 144.0),
        ("350 - 200", 150.0),
        ("150 + 100", 250.0),
    ]

    for expr, res in sample_data:
        memory_catcher(expr, res)

    memory_lister()