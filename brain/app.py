# this program is going to be like messaging app for the agents!

# importing the nessary modules
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field # this module is used for data validation
from brain import task_store
from brain import worker as task_worker
from brain.auth import require_api_token
from brain.orchestrator import run_task

# this import for api route exposure
from File_Manager.api.routes import router as file_manager_router
from File_Manager.api.routes import mutations as file_manager_mutations

# lifespan: reconcile tasks orphaned by a previous process on startup,
# and detach background workers promptly on shutdown (daemon threads, so
# shutdown never hangs; in-flight rows are reconciled on the next boot).
@asynccontextmanager
async def lifespan(app: FastAPI):
    task_worker.startup(run_task)
    yield
    task_worker.shutdown()

# initialising the APP!
app = FastAPI(lifespan=lifespan)

# initialising the exposure of those routes created
app.include_router(file_manager_router)
app.include_router(file_manager_mutations)

# creating a blueprint of the APp!
class TaskRequest(BaseModel):
    # descriptions are queued in memory, so bound their size: an unbounded
    # string per submission would let queued tasks exhaust memory.
    description: str = Field(max_length=4000)
    provider: str = "anthropic"

# @app is a way to trigger like, to do a specific function in app!

@app.post("/submit_task", dependencies=[Depends(require_api_token)], status_code=202)
# this function validates the request, persists the task, and hands it to
# the background worker - the HTTP request never waits for the agent run.
def submit_task (req: TaskRequest):
    task_id = task_store.add_task(req.description, req.provider)
    task_worker.enqueue(task_id, req.description, req.provider, run_task)
    return {"id": task_id, "status": "queued"}

@app.post("/tasks/{task_id}/cancel", dependencies=[Depends(require_api_token)])
# this function cancels a task that has not started yet. running tasks keep
# running to completion or timeout - threads are never force-killed, so a
# cancel that loses the race honestly reports 409 instead of lying.
def cancel_task (task_id: int):
    current = task_store.get_task(task_id)
    if current is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
    if task_store.cancel_task(task_id):
        return {"id": task_id, "status": "cancelled"}
    raise HTTPException(
        status_code=409,
        detail=f"Task {task_id} is {current['status']} and cannot be cancelled.",
    )

@app.get("/tasks", dependencies=[Depends(require_api_token)])
# this function will fetch the task in app
def get_task():
    return task_store.list_task()

@app.get("/health")
# this function is all about checking the task status
# (public on purpose: liveness only, no data, no writes)
def health():
    return {"status": "ok"}
