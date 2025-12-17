"""
FastAPI server for BrowserFreak - REST API for browser automation
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from .browser_agent import run_agent_workflow
from .browser_manager import health_check
from .config import settings
from .exceptions import BrowserFreakError, ValidationError
from .logging_config import log

# FastAPI app
app = FastAPI(
    title="BrowserFreak API",
    description="AI-powered browser automation API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory task storage (use Redis/database for production)
task_store: Dict[str, Dict[str, Any]] = {}


class TaskRequest(BaseModel):
    """Request model for task execution"""

    task: str = Field(..., description="The task description to execute")
    use_real_browser: Optional[bool] = Field(
        default=None, description="Override default browser setting"
    )
    max_iterations: Optional[int] = Field(
        default=None, description="Maximum iterations for agent workflow (1-20)"
    )
    enable_security: Optional[bool] = Field(
        default=None, description="Enable security checks for destructive actions"
    )

    @field_validator("max_iterations")
    @classmethod
    def validate_max_iterations(cls, v):
        if v is not None and (v < 1 or v > 20):
            raise ValueError("max_iterations must be between 1 and 20")
        return v


class TaskResponse(BaseModel):
    """Response model for task execution"""

    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Status message")


class TaskStatus(BaseModel):
    """Task status response"""

    task_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    logs: List[Dict[str, Any]] = []
    error: Optional[str] = None


@app.get("/health")
async def health_endpoint():
    """Health check endpoint"""
    try:
        health_status = await health_check()
        return {
            "service": "BrowserFreak API",
            "status": health_status["status"],
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "browser_health": health_status,
        }
    except Exception as e:
        log.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")


@app.post("/tasks", response_model=TaskResponse)
async def create_task(
    task_request: TaskRequest, background_tasks: BackgroundTasks, request: Request
):
    """Create and execute a browser automation task"""
    try:
        # Validate input
        if not task_request.task.strip():
            raise ValidationError("Task description cannot be empty")

        # Generate task ID
        task_id = str(uuid.uuid4())

        # Store initial task state
        task_store[task_id] = {
            "task_id": task_id,
            "status": "running",
            "created_at": datetime.now(),
            "task_description": task_request.task,
            "logs": [],
            "result": None,
            "error": None,
        }

        # Override settings if provided
        use_real_browser = (
            task_request.use_real_browser
            if task_request.use_real_browser is not None
            else settings.agent.use_real_browser
        )
        max_iterations = (
            task_request.max_iterations
            if task_request.max_iterations is not None
            else settings.agent.max_iterations
        )
        enable_security = (
            task_request.enable_security
            if task_request.enable_security is not None
            else settings.agent.enable_security_checks
        )

        # Add initial log entry
        task_store[task_id]["logs"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "type": "info",
                "message": f"Task created: {task_request.task[:100]}...",
            }
        )

        # Execute task in background
        background_tasks.add_task(
            execute_task_background,
            task_id,
            task_request.task,
            use_real_browser,
            max_iterations,
            enable_security,
        )

        log.info(f"Task {task_id} created and queued for execution")
        return TaskResponse(
            task_id=task_id, status="running", message="Task created and execution started"
        )

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"Failed to create task: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Get the status of a task"""
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")

    task = task_store[task_id]
    return TaskStatus(**task)


@app.get("/tasks")
async def list_tasks(status: Optional[str] = None, limit: int = 50, offset: int = 0):
    """List all tasks with optional filtering"""
    tasks = list(task_store.values())

    # Filter by status if provided
    if status:
        tasks = [t for t in tasks if t["status"] == status]

    # Apply pagination
    total = len(tasks)
    tasks = tasks[offset : offset + limit]

    return {"tasks": tasks, "total": total, "limit": limit, "offset": offset}


@app.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a running task (if supported)"""
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")

    task = task_store[task_id]
    if task["status"] == "completed":
        raise HTTPException(status_code=400, detail="Cannot cancel completed task")

    # Mark as cancelled
    task["status"] = "cancelled"
    task["completed_at"] = datetime.now()
    task["error"] = "Task cancelled by user"

    log.info(f"Task {task_id} cancelled")
    return {"message": "Task cancelled successfully"}


async def execute_task_background(
    task_id: str,
    task_description: str,
    use_real_browser: bool,
    max_iterations: int,
    enable_security: bool,
):
    """Execute task in background"""
    try:
        log.info(f"Starting background execution for task {task_id}")

        # Execute the agent workflow
        result = await run_agent_workflow(
            task_description, max_iterations=max_iterations, use_real_browser=use_real_browser
        )

        # Update task status
        task_store[task_id]["status"] = "completed"
        task_store[task_id]["completed_at"] = datetime.now()
        task_store[task_id]["result"] = dict(result)

        # Add completion log
        task_store[task_id]["logs"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "type": "success",
                "message": "Task completed successfully",
            }
        )

        log.info(f"Task {task_id} completed successfully")

    except BrowserFreakError as e:
        error_msg = f"BrowserFreak error: {str(e)}"
        log.error(f"Task {task_id} failed: {error_msg}")

        task_store[task_id]["status"] = "failed"
        task_store[task_id]["completed_at"] = datetime.now()
        task_store[task_id]["error"] = error_msg
        task_store[task_id]["logs"].append(
            {"timestamp": datetime.now().isoformat(), "type": "error", "message": error_msg}
        )

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        log.error(f"Task {task_id} failed with unexpected error: {error_msg}", exc_info=True)

        task_store[task_id]["status"] = "failed"
        task_store[task_id]["completed_at"] = datetime.now()
        task_store[task_id]["error"] = error_msg
        task_store[task_id]["logs"].append(
            {"timestamp": datetime.now().isoformat(), "type": "error", "message": error_msg}
        )


@app.exception_handler(BrowserFreakError)
async def browserfreak_exception_handler(request: Request, exc: BrowserFreakError):
    """Handle BrowserFreak-specific exceptions"""
    log.error(f"BrowserFreak error: {exc}")
    return JSONResponse(
        status_code=400, content={"error": "BrowserFreak Error", "detail": str(exc)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    log.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": "An unexpected error occurred"},
    )


@app.on_event("startup")
async def startup_event():
    """Application startup tasks"""
    log.info("BrowserFreak API server starting up")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown tasks"""
    log.info("BrowserFreak API server shutting down")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
