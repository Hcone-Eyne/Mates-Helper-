# this program is use to run the python test.. 
# I CAN"T RUN EVERYTHING / KEEP CHECKING FOR ENTERNITY!!!!!

# importing nessary modules
import pandas as pd
from Schedule_Bot.schedule_pharaser import reshape_to_long

# creating the test function.....
def for_reshaper_to_long(): 

    # building a fake input (purpose!)
    df = pd.DataFrame({
        "Days / Hour": ["Monday"],
        "(8.30-9.20)": ["CA"]
    }) 

    result = reshape_to_long(df) 

    # assert shows if someething fails or not.....
    assert len(result) == 1
    assert result.iloc[0]["day"] == "Monday" # this is like, give me the first row and check if its monday and that is checked for below conditions!
    assert result.iloc[0]["subject"] == "CA" 
    assert result.iloc[0]["time_start"] == "8.30" 
    assert result.iloc[0]["time_end"] == "9.20"


# this is used to test empty cell 
def test_reshape_skips_empty_cells():
    # again fake data
    df = pd.DataFrame({
        "Days / Hour": ["Monday"],
        "(8.30-9.20)": [None]   # empty class slot.....
    })
    result = reshape_to_long(df)

    # output should be empty!
    assert len(result) == 0   # nothing should be added for empty cells..

