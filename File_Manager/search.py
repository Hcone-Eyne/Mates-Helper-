# this program is used to search files in the vault like a file manager in cli version!

# importing the nessary modules!
from File_Manager import db

# this function is going to be used to searrch the required file from the user!
def search(query, limit = 10):

    # checking if the input is query or not
    if not query or not query.strip():
        return []

    # applying limit to prevent overload
    limit = max(1, min(int(limit), 100))

    return db.search_files(
        query.strip(), 
        limit
    )

# this function going to handle the files category!
def search_category(category, limit = 100):

    # return what it found.. (the category of the file belongs!)
    result = db.list_all(category)

    # return the result!
    return result[:limit]

# this function is going to handle the list_file!
def list_files(category = None, limit = 100):

    # return the indexed file!
    results = db.list_all(category)

    # return the value
    return results[:limit]
