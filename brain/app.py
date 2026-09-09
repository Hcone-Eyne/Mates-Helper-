# this program is going to be like messaging app for the agents!

# importing the nessary modules
from fastapi import FastAPI
from pydantic import BaseModel # this module is used for data validation
from brain import task_store
from brain.orchestrator import run_task

# this import for api route exposure
from File_Manager.api.routes import router as file_manager_router

# initialising the APP!
app = FastAPI()

# initialising the exposure of those routes created
app.include_router(file_manager_router)

# creating a blueprint of the APp!
class TaskRequest(BaseModel):
    description: str
    provider: str = "anthropic"

# @app is a way to trigger like, to do a specific function in app!

@app.post("/submit_task")
# this function is going to handle the process of submiting the task
def submit_task (req: TaskRequest):
    task_id = task_store.add_task(req.description)
    result = run_task(req.description, req.provider)
    task_store.complete_task(task_id, result)
    return {"id": task_id, "result": result}

@app.get("/tasks")
# this function will fetch the task in app
def get_task():
    return task_store.list_task()

@app.get("/health")
# this function is all about checking the task status
def health():
    return {"status": "ok"}
