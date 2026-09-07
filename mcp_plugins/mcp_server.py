# this program is going to connect powerfull ai to local!

# importing nessary modules
import pandas as pd
from fastmcp import FastMCP

# now importing from created python modules
from bot import load_schedule, query_handler
from Finance_bot.operations_finder import operation_finder
from Memory.memory_storer import memory_catcher, memory_eraser, memory_dataframe
from Finance_bot.Expense_analyzer import load_statement, build_summary
from File_Manager import db as file_db

# setting up mcp!
mcp = FastMCP("Fox-Helper")

# this function will handle the dataframe strings!
def _df_to_text(df: pd.DataFrame) -> str:
    # returns Dataframe into String format and If something there, it'll show the strinh else, prints Nothin
    return df.to_string(index = False) if not df.empty else "[Fox]: Nothin To Show."

# Making Schedule tools to MCP
@mcp.tool() # a special way to call the plugin
# this function returns detailes about the stored schedule!
def schedule_ask(input:str) -> str:
    """Search or ask questions about the stored schedule."""
    # ask fox about schedule it gives
    # load the schedule
    data = load_schedule()

    # fetching result in DataFrame Format
    result = query_handler(input, data)

    # this conditions make sure that output is returned as string..
    if isinstance(result, pd.DataFrame):
        # this gives the upper function to turn into text DataFrame -> Text
        return _df_to_text(result)
    # if not result in DataFrame Format Convert into str and return!
    return str(result)

@mcp.tool()
# this function is used to view the schedule!
def schedule_view():
    """View the full schedule."""
    # return the full schedule
    return _df_to_text(load_schedule())

# Now Making Finance Tool to Mcp TooL!
@mcp.tool()
    # this asusual do the financ calculator operatiosn!
def finance_calculate(expression:str):
    """Perform basic financial calculations (+, -, *, /) and save to history."""
    result = operation_finder(expression)
    # this condition checks for input
    if result is None:
        return "[Fox]: Invalid expression. Use digits!"
    # calling the memory catcher to store results!
    memory_catcher(expression, result)
    return f"[Fox]: Result ->{result}"

# calling plugin again!
@mcp.tool()
# this function show the history of calcuation!
def finance_history():
    """View the history of past financial calculations."""
    # return the operation performed by far..
    return _df_to_text(memory_dataframe())

@mcp.tool()
# this function clears the history of those oprration performed
def finance_clear_history():
    """Clear the stored calculation history."""
    # erase memory!
    memory_eraser()
    return "[Fox]: Memory erased."

@mcp.tool()
# this function uses Expense_analyser.py to do operations such as read PDF/CSV, Analysis them etc.....
def expense_summary(path:str):
    """Analyze a bank/GPay statement (CSV or PDF) and return this month's
    category breakdown, total spend, and comparison to last month."""

    # conditions starts here
    try:
        # this condition loads the file
        df = load_statement(path)
    # if error occurs show them!
    except Exception as e:
        return f"[Fox]: {e}"
    
    # build a summary so user can see that
    summary = build_summary(df)

    # this condition checks if the summary has context or not!
    if summary is None:
        # if not say No transactions found in file!
        return "[Fox]: No transactions found."

    # this line tels about current month status fetched from file!
    lines = [f"This Month Track ({summary['month']})"]

    # this loops through the file and gets those data!
    for category, amount in summary["by_category"].items():
        # in simple term calculation to obtain current status.....
        sign = "+" if amount >= 0 else "-"
        lines.append(f"{category}: {sign}{abs(amount):.0f}")
    lines.append(f"Total spend = {summary['total_spend']:.0f}")

    # this condition compares with previous month data and shows that to user!
    if summary["prev_spend"] not in (None, 0):
        # in simple term calculation to obtain how much money is spent!!!!!
        diff = summary["total_spend"] - summary["prev_spend"]
        pct = (diff / summary["prev_spend"]) * 100
        direction = "extra" if diff >= 0 else "less"
        lines.append(f"that's {pct:+.0f}% which is {direction} \u20b9{abs(diff):.0f} compared to previous month")
    # shows this to user!
    return "\n".join(lines)

@mcp.tool()
def file_find(query: str) -> str:
    """Search the Vault for a file by keyword (filename or content snippet)."""
    results = file_db.search_files(query)
    if not results:
        return f"[Fox]: Nothing matching '{query}' in the vault."
    return "\n".join(f"{r['name']} ({r['category']}) -> {r['path']}" for r in results)

if __name__ == "__main__":
    mcp.run()
