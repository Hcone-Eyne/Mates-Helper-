# this part stores all the previous finance bot operations and results......

# imoprting necessary modules
import os
import threading
from rich.console import Console
from rich.panel import Panel
import pandas as pd

try:
    import plotext as plt2
except ModuleNotFoundError:  # pragma: no cover - optional visualization dependency
    plt2 = None

console = Console()
# ading a variable to store the previous operations and results.
# This list is shared across the CLI finance menu, agent tools, MCP tools,
# and concurrent Brain worker threads, so all access goes through the lock
# below and the log is capped instead of growing for the life of the process.
memory_log = []
_memory_lock = threading.Lock()

# Default cap on retained finance entries. Every finance_calculate appends
# and finance_history stringifies the whole log to the model, so without a
# cap a long session grows request/token/cost per call. Oldest-first trim
# keeps the latest calculations. Overridable via
# FOX_FINANCE_HISTORY_MAX_ENTRIES, following the project's env-configuration
# convention (FOX_HISTORY_MAX_MESSAGES, FOX_TASK_TIMEOUT_SECONDS, ...).
FINANCE_HISTORY_MAX_ENTRIES_DEFAULT = 100


def finance_history_max_entries() -> int:
    """Resolve the finance history bound. Invalid values fall back to the
    default; the floor of 1 keeps the feature functional."""
    try:
        return max(1, int(os.environ.get("FOX_FINANCE_HISTORY_MAX_ENTRIES", FINANCE_HISTORY_MAX_ENTRIES_DEFAULT)))
    except (TypeError, ValueError):
        return FINANCE_HISTORY_MAX_ENTRIES_DEFAULT

# creating a function to store the previous operations and results also it gets called after every operation is performed
def memory_catcher(expression, result):
    # Invalid expressions produce result=None (see operation_finder); they
    # must never pollute the history. The agent and MCP paths already guard
    # this, and the CLI path relies on this central check.
    if result is None:
        return
    with _memory_lock:
        memory_log.append({"expression": expression, "result": result})
        limit = finance_history_max_entries()
        if len(memory_log) > limit:
            del memory_log[:len(memory_log) - limit]

# this function handles the memmory log / eraser!
def memory_eraser():
    with _memory_lock:
        memory_log.clear()
    console.print("[Fox]: Memory erased.")

# this function is going to be used to pandas dataframe, so pandas and plotting tools can be used.....
def memory_dataframe():
    with _memory_lock:
        rows = list(memory_log)
    return pd.DataFrame(rows)

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
        with _memory_lock:
            memory_log.clear()
        return
    elif choice == "0":
        # it will skip the graphing of the previous operations and results
        console.print("[Fox]: Skipping the graphing of previous operations.")
        return
    else:
        # if user enters an invalid choice, keep history intact: an invalid
        # menu choice must never erase the user's calculation history.
        console.print("[Fox]: Invalid choice. Please try again.")
        return

    # adding memory eraser feature
    with _memory_lock:
        memory_log.clear()
    console.print("[Fox]: Memory erased.")

# this function is going to show off the graph in line and rest is all we know1
def plot_line_line(df):
    if plt2 is None:
        raise RuntimeError("plotext is required for chart rendering.")
    plt2.plot(df.index.tolist(), df["result"].tolist())
    plt2.title("Results over Sessions")
    plt2.xlabel("Entry Number")
    plt2.ylabel("Result")
    plt2.grid(True, True)
    plt2.show()

# this function is going to show off the graph in bar chart
def plot_bar(df):
    if plt2 is None:
        raise RuntimeError("plotext is required for chart rendering.")
    plt2.bar(df["expression"].tolist(), df["result"].tolist())
    plt2.title("Results over Expressions")
    plt2.xlabel("Expression")
    plt2.ylabel("Result")
    plt2.tight_layout()
    plt2.show()

# this function is going to show off the graph in histogram
def plot_histogram(df): 
    if plt2 is None:
        raise RuntimeError("plotext is required for chart rendering.")
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