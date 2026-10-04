# this program is going to be like messaging app for the agents!

# importing the nessary modules
from fastapi import Depends, FastAPI
from pydantic import BaseModel # this module is used for data validation
from brain import task_store
from brain.auth import require_api_token
from brain.orchestrator import run_task

# this import for api route exposure
from File_Manager.api.routes import router as file_manager_router
from File_Manager.api.routes import mutations as file_manager_mutations

# initialising the APP!
app = FastAPI()

# initialising the exposure of those routes created
app.include_router(file_manager_router)
app.include_router(file_manager_mutations)

# creating a blueprint of the APp!
class TaskRequest(BaseModel):
    description: str
    provider: str = "anthropic"

# @app is a way to trigger like, to do a specific function in app!

@app.post("/submit_task", dependencies=[Depends(require_api_token)])
# this function is going to handle the process of submiting the task
def submit_task (req: TaskRequest):
    task_id = task_store.add_task(req.description)
    try:
        result = run_task(req.description, req.provider)
    except Exception as exc:
        # A raised run_task must still reach a terminal state - otherwise the
        # row sits at "pending" forever with no error recorded.
        task_store.fail_task(task_id, f"[Fox]: Task failed: {exc}")
        raise
    task_store.complete_task(task_id, result)
    return {"id": task_id, "result": result}

@app.get("/tasks", dependencies=[Depends(require_api_token)])
# this function will fetch the task in app
def get_task():
    return task_store.list_task()

@app.get("/health")
# this function is all about checking the task status
# (public on purpose: liveness only, no data, no writes)
def health():
    return {"status": "ok"}
