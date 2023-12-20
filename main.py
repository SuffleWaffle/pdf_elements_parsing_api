# >>>> </> STANDARD IMPORTS </>
# >>>> ********************************************************************************
import os
import sys
import logging
import asyncio
from pathlib import Path
# >>>> ********************************************************************************

# >>>> </> EXTERNAL IMPORTS </>
# >>>> ********************************************************************************
from fastapi import FastAPI, Response, status
from fastapi.responses import UJSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import ujson as json
# >>>> ********************************************************************************

# >>>> </> LOCAL IMPORTS </>
# >>>> ********************************************************************************
# ---- CONFIG ----
# import settings
from src_logging import log_config
from src_env import env_config
# ---- FastAPI ROUTERS ----
from src_routers.rtr_parse_sld_table import parse_sld_table_rtr
from src_routers.rtr_special_symbols_parsing import special_symbols_parse_rtr
from src_routers.rtr_parse_text import parse_text_rtr
from src_routers.rtr_panelboard_table_parsing import parse_panelboard_rtr
# >>>> ********************************************************************************


# ________________________________________________________________________________
# --- INIT CONFIG - LOGGER SETUP ---
logger = log_config.setup_logger(logger_name=__name__, logging_level=logging.INFO)

# ________________________________________________________________________________
# --- INIT CONFIG - ENVIRONMENT VARIABLES SETUP ---
# env_files_paths_dict: dict = {
#     "env_general_file_path":    Path(".env"),
#     "env_dev_file_path":        Path("src_env/dev/.env"),
#     "env_prod_file_path":       Path("src_env/prod/.env"),
#     "env_stage_file_path":      Path("src_env/stage/.env")
# }

# ________________________________________________________________________________
# --- INIT CONFIG - EVENT LOOP POLICY SETUP ---
if sys.platform == "linux":
    # --- PROD - uvloop (for Linux) EVENT LOOP POLICY SETUP ---
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logging.info(">>>> EVENT LOOP POLICY SETUP - PROD - | uvloop.EventLoopPolicy | IS ACTIVE <<<<")

elif sys.platform == "win32":
    # --- DEV - win32 (for Windows) EVENT LOOP POLICY SETUP ---
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    logging.info(">>>> EVENT LOOP POLICY SETUP - DEV - | WindowsSelectorEventLoopPolicy | IS ACTIVE <<<<")


# ________________________________________________________________________________
# >>>> </> FastAPI APP CONFIG </>
description = """
**PDF Elements Parsing API - API service for parsing text, tables and other information from PDF**  

## Healthcheck:

- **Healthcheck allows to monitor operational status of the API -> Returns status <HTTP_200_OK> if service instance is running**).

"""

app = FastAPI(
    title="Drawer AI - PDF Elements Parsing API",
    description=description,
    version="0.1.0",)

app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=json.loads(os.getenv("APP_CORS_ORIGINS")),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(router=parse_sld_table_rtr)
app.include_router(router=parse_text_rtr)
app.include_router(router=special_symbols_parse_rtr)
app.include_router(router=parse_panelboard_rtr)


# ________________________________________________________________________________
# >>>> </> APP - STARTUP </>
@app.on_event(event_type="startup")
async def startup_event():
    logger.info(">>> PDF Elements Parsing - SERVICE STARTUP COMPLETE <<<")


# ________________________________________________________________________________
# >>>> </> APP - SHUTDOWN </>
@app.on_event(event_type="shutdown")
async def shutdown_event():
    logger.info(">>> PDF Elements Parsing - SERVICE SHUTDOWN <<<")


# ________________________________________________________________________________
# >>>> </> APP - HEALTHCHECK </>
class HealthcheckResponse(BaseModel):
    healthcheck: str = "API Status 200"


@app.get(path="/healthcheck/",
         status_code=status.HTTP_200_OK,
         response_model=HealthcheckResponse,
         tags=["HEALTHCHECK"],
         summary="Healthcheck endpoint for API service.")
async def healthcheck() -> Response:
    logger.info("--- HEALTHCHECK Endpoint - Status 200 ---")
    return UJSONResponse(content={"healthcheck": "API Status 200"},
                         status_code=status.HTTP_200_OK)
