import uvicorn
from fastapi import Request, FastAPI, Body, Depends, HTTPException, Header
from src.Utils.log import logger
from src.Beta.beta_processor import allocate_routes_for_beta
from src.Mongo_Manager.schemas.beta.bestfit_schema import BestFitRequest
from src.Mongo_Manager.db_repos.travel_data import TravelDataRepository
from src.Mongo_Manager.db_repos.routing_task import RoutingTaskRepository
from src.CommonCode.dependencies import (get_travel_data_repository,
                                         get_routing_task_repository)
from src.Mongo_Manager.db_connections.connection import DatabaseConnectionManager, cleanup_db_connections
from fastapi.templating import Jinja2Templates
from pathlib import Path
from fastapi.responses import HTMLResponse, FileResponse
from datetime import datetime, timedelta
import re, subprocess
from typing import Optional
from contextlib import asynccontextmanager
from fastapi.concurrency import run_in_threadpool
import warnings
import pandas as pd


warnings.filterwarnings(
    "ignore",
    message="Could not infer format*"
)

warnings.simplefilter(
    action='ignore',
    category=pd.errors.SettingWithCopyWarning
)

warnings.simplefilter(
    action='ignore',
    category=FutureWarning
)

db_connection_manager = DatabaseConnectionManager()

with db_connection_manager.connect_to_db():
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    with db_connection_manager.connect_to_db():
        pass

    yield

    # Shutdown
    cleanup_db_connections()


app = FastAPI(lifespan=lifespan)


@app.post("/bestfit")
async def bestfit(
        request: BestFitRequest = Body(...),
        travel_repo: TravelDataRepository = Depends(get_travel_data_repository),
        routing_task_repository: RoutingTaskRepository = Depends(get_routing_task_repository),
        MultiTenantCompanyKey : str = Header(None)
):
    logger.info(
        "BestFit Begin For Request %s",
        request.model_dump_json()
    )
    if MultiTenantCompanyKey:
        company_key = MultiTenantCompanyKey
    else:
        company_key = ''

    result = await run_in_threadpool(
        allocate_routes_for_beta,
        request,
        travel_repo,
        routing_task_repository,
        company_key

    )

    return result


def get_last_commit():
    git_path = "/usr/bin/git"  # Absolute path to Git
    try:
        commit_message = subprocess.check_output(
            [git_path, 'log', '-1', '--pretty=%B'],
            stderr=subprocess.STDOUT
        ).decode('utf-8').strip()

        commit_date = subprocess.check_output(
            [git_path, 'log', '-1', '--pretty=%cd', '--date=short'],
            stderr=subprocess.STDOUT
        ).decode('utf-8').strip()

        return f"Latest changes applied: {commit_message} ({commit_date})"

    except subprocess.CalledProcessError as e:
        logger.info(f"Git command failed: {e.output.decode('utf-8')}")
    except FileNotFoundError:
        logger.info("Git is not installed on this system.")
    except Exception as e:
        logger.info(f"Unexpected error: {e}")

    return "Git info not available"


commit_message = get_last_commit()

templates = Jinja2Templates(directory="src/templates")

LOG_DIR = Path(".")  # Where your logs are stored
LOG_BASENAME = "app.log"


def format_log_name(filename, all_files):
    # Sort all log files by date (ignoring 'app.log')
    dated_logs = sorted(
        [f for f in all_files if f != "app.log"],
        key=lambda x: datetime.strptime(x.split('.')[-1], "%Y-%m-%d")
    )

    # If current log
    if filename == "app.log":
        if dated_logs:
            last_date_str = dated_logs[-1].split('.')[-1]
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d") + timedelta(days=7)
            return f"Logs from {last_date.strftime('%b %d')} - Present"
        else:
            return "Logs - Present"

    # If old log
    else:
        date_part = filename.split('.')[-1]
        end_date = datetime.strptime(date_part, "%Y-%m-%d")
        start_date = end_date + timedelta(days=6)
        return f"Logs from {end_date.strftime('%b %d')} - {start_date.strftime('%b %d')}"


@app.get("/", response_class=HTMLResponse)
async def list_logs(request: Request):
    log_files = sorted(LOG_DIR.glob(f"{LOG_BASENAME}*"), reverse=True)
    filenames = [f.name for f in log_files]
    filenames.insert(0, filenames.pop())
    filenames = [[format_log_name(f, filenames), f] for f in filenames]
    return templates.TemplateResponse("list_logs.html", {"request": request, "log_files": filenames,
                                                         "commit_message": commit_message})


@app.get("/logs/view/{log_filename}", response_class=HTMLResponse)
async def display_logs(
        request: Request,
        log_filename: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
):
    log_path = LOG_DIR / log_filename

    if not log_path.exists() or not log_path.is_file():
        raise HTTPException(status_code=404, detail="Log file not found")

    try:
        with log_path.open("r", encoding="utf-8") as file:
            content = file.read()
    except Exception as e:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "all_logs": f"Error reading log file: {e}",
                "log_filename": log_filename,
                "start_time": start_time or "",
                "end_time": end_time or "",
                "commit_message": commit_message
            },
        )

    # Split logs by __SPLIT__ or newlines
    logs = content.split("__SPLIT__") if "__SPLIT__" in content else content.splitlines()

    # Pattern to match timestamp at the beginning of a log line
    log_datetime_pattern = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}")

    filtered_logs = []

    if start_time and end_time:
        try:
            start_dt = datetime.fromisoformat(start_time)
            end_dt = datetime.fromisoformat(end_time)

            for log in logs:
                match = log_datetime_pattern.search(log)
                if not match:
                    continue
                try:
                    log_time = datetime.strptime(match.group(), "%Y-%m-%d %H:%M:%S,%f")
                    if start_dt <= log_time <= end_dt:
                        filtered_logs.append(log)
                except ValueError:
                    continue
        except ValueError:
            filtered_logs = ["Invalid date format. Please use ISO format (e.g. 2025-01-07T10:00:00)"]

    displayed_logs = filtered_logs if filtered_logs else logs[-100:]

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "all_logs": "__SPLIT__".join(displayed_logs),
            "log_filename": log_filename,
            "start_time": start_time or "",
            "end_time": end_time or "",
            "commit_message": commit_message
        },
    )


@app.get("/logs/download/{log_filename}")
async def download_log_file(log_filename: str):
    log_path = LOG_DIR / log_filename

    if not log_path.exists() or not log_path.is_file():
        raise HTTPException(status_code=404, detail="Log file not found")

    return FileResponse(
        path=str(log_path),
        filename=log_filename,
        media_type="text/plain"
    )


# Required for testing in local
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
