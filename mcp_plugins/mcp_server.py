# this program is going to connect powerfull ai to local!

# importing nessary modules
import pandas as pd
import websockets
from fastmcp import FastMCP

# now importing from created python modules
from bot import load_schedule, query_handler
from Finance_bot.operations_finder import operation_finder
from Memory.memory_storer import memory_catcher, memory_eraser, memory_dataframe

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

if __name__ == "__main__":
    mcp.run()
