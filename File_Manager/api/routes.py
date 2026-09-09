# this program is about exposing the file management features to Fox!

# importing the nessary modules
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import scanner, search
from .. import modify_files

# initialising the router
router = APIRouter(
    prefix = "/files",
    tags = ["File Manager"]
)

# creating a class for move request of file
class MoveRequest(BaseModel):
    source:str
    destination:str

# creating a class for to rename request
class CopyRequest(BaseModel):
    source:str
    destination:str

# createing a class for to rename the file 
class RenameRequest(BaseModel):
    source:str
    new_name:str

# creating a class for to Delete a request
class DeleteRequest(BaseModel):
    path:str

# creating a class to creae a folder in File manager
class CreateFolderRequest(BaseModel):
    path:str

@router.get("/health")
# this function is used to check health
def health():
    return{
        "status":"ok",
        "service":"file-manager"
    }

@router.post("/scan")
# this function is used to call the scan function to scan the file and store
def scan_files():
    return scanner.scan()

@router.get("/search")
# this function is used to call the search function and search the file
def search_files( q: str, limit:int = 10,):
    return{
        "query": q,
        "results": search.search(q, limit)
    }

@router.get("/")
# this function used to call a function to give the list of files stored in file manager.....
def list_files(category:str |None = None, limit:int = 100):
    return{
        "result":search.list_files (category, limit)
    }

@router.post("/move")
# this function is used to call a function to move a file
def move_file(req: MoveRequest):
    try:
        result = modify_files.move_file(
            req.source, 
            req.destination
        )
        return{
            "success": True,
            "path": str(result)
        }
    except (FileNotFoundError, ValueError, IsADirectoryError) as e:
        raise HTTPException(
            status_code = 400,
            detailwe  = str(e)
        )

@router.post("/copy")
# this function ahhh, call the copy funtion to create a copy mechanism!
def copy_files(req: CopyRequest):
    try:
        result = modify_files.copy_file(
            req.source,
            req.destination
        )
        return {
            "success": True,
            "path": str(result)
        }
    except (FileNotFoundError, ValueError, IsADirectoryError) as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post("/rename")
# this function calls the function to rename a file.....
def rename_file(req: RenameRequest):
    try:
        result = modify_files.rename_file(
            req.source,
            req.new_name
        )
        return {
            "success":True,
            "path": str(result)
        }
    except (FileNotFoundError, ValueError, IsADirectoryError) as e:
        raise HTTPException(
            status_code = 400,
            detail = str(e)
        )

@router.post("/delete")
# this function calls the function to delete a file in file manager
def delete_file(req: DeleteRequest):
    try:
        deleted = modify_files.delete_file(req.path)
        return {
            "success": deleted,
        }
    except (FileNotFoundError, ValueError, IsADirectoryError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

@router.post("/folder")
# this function calls the function to create a file in file manager
def create_folder(req: CreateFolderRequest):
    try:
        result = modify_files.create_folder(req.path)
        return {
            "success": True,
            "path": str(result)
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )
