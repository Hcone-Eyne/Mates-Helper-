# this part stores all the previous finance bot operations and results......

# imoprting necessary modules
from rich.console import Console
from rich.panel import Panel
import pandas as pd
from Cli import console
import matplotlib.pyplot as plt

# ading a variable to store the previous operations and results
memory_log = []

# creating a function to store the previous operations and results also it gets called after every operation is performed
def memory_catcher(expression, result):
    memory_log.append((expression, result))

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
        "[bold cyan]1.[/bold cyan] Line graph (trend across entries)\n"
        "[bold cyan]2.[/bold cyan] Bar chart (each expression vs its result)\n"
        "[bold cyan]3.[/bold cyan] Histogram (distribution of results)\n"
        "[bold cyan]0.[/bold cyan] Skip",
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
    elif choice == "0":
        # it will skip the graphing of the previous operations and results
        console.print("[Fox]: Skipping the graphing of previous operations.")
        return
    else:
        # if user enters an invalid choice
        console.print("[Fox]: Invalid choice. Please try again.")

# this function is going to show off the graph in line and rest is all we know1
def plot_line_line(df):
    plt.plot(df.index, df["result"], marker='o')
    plt.title("Results over Sessions")
    plt.xlabel("Entry Number")
    plt.ylabel("Result")
    plt.grid()
    plt.show()

# this function is going to show off the graph in bar chart
def plot_bar(df):
    plt.bar(df["expression"], df["result"])
    plt.title("Results over Expressions")
    plt.xlabel("Expression")
    plt.ylabel("Result")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.show()

# this function is going to show off the graph in histogram
def plot_histogram(df):
    plt.hist(df["result"], bins=10, edgecolor='black')
    plt.title("Distribution of Results")
    plt.xlabel("Result")
    plt.ylabel("Frequency")
    plt.grid(axis='y')
    plt.show()

