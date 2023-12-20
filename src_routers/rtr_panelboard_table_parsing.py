# >>>> </> STANDARD IMPORTS </>
# >>>> ********************************************************************************
import logging
import io
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
# >>>> ********************************************************************************

# >>>> </> EXTERNAL IMPORTS </>
# >>>> ********************************************************************************
from fastapi import APIRouter, HTTPException
from fastapi import status, UploadFile, File, Form, Response
from fastapi.responses import UJSONResponse
from pydantic import BaseModel
import ujson as json
# >>>> ********************************************************************************

# >>>> </> LOCAL IMPORTS </>
# >>>> ********************************************************************************
import settings
from src_logging import log_config
from src_processes.parse_panelboard_table import parse_panelboard_table
from src_utils.loading_utils import load_pdf
from src_utils.plotting_utils import plot_extracted_messages
from src_utils.aws_utils import S3Utils
from .request_models import PanelboardTableParsingS3FilesData
# >>>> ********************************************************************************


# ________________________________________________________________________________
# --- INIT CONFIG - LOGGER SETUP ---
logger = log_config.setup_logger(logger_name=__name__, logging_level=logging.DEBUG)

# ________________________________________________________________________________
# --- FastAPI ROUTER ---
parse_panelboard_rtr = APIRouter(prefix="/v1")


class Data(BaseModel):
    lines: dict
    parsed_text: dict
    tables_locations: Optional[List]


# ________________________________________________________________________________
@parse_panelboard_rtr.post(path="/parse-panelboard-table/",
                           responses={200: {}, 500: {}, 503: {}},
                           status_code=status.HTTP_200_OK,
                           response_class=UJSONResponse,
                           tags=["PDF Elements Parsing - Panelboard Table Parsing"],
                           summary="Parse tables relevant to panelboards")
async def parse_panelboard_endpoint(parsed_text_file: UploadFile = File(...),
                                    file: UploadFile = File(...),
                                    tables_locations: Optional[UploadFile] = None,
                                    page_num: int = 0,
                                    table_as_input: bool = True,
                                    remove_border: bool = False):
    if not parsed_text_file.filename.endswith('.json'):
        raise HTTPException(404, f'File with filename {parsed_text_file.filename} does not end with .json')

    if not file.filename.endswith('.pdf'):
        raise HTTPException(404, f'File with filename {file.filename} does not end with .pdf')

    tables_locations = json.loads(await tables_locations.read()) if tables_locations else []

    parsed_text = await parsed_text_file.read()
    parsed_text = json.loads(parsed_text)

    # get parsed text
    parsed_text, pdf_width, pdf_height = parsed_text['parsed_text'], \
                                         parsed_text['pdf_width'], \
                                         parsed_text['pdf_height']

    # get pdf
    doc, page, img_array, pdf_size = load_pdf(pdf_file_obj=file,
                                              page_num=page_num,
                                              s3_origin=False)

    if table_as_input:
        tables_locations = [[0, 0, pdf_width, pdf_height]]

    # parse panelboard tables
    tables = parse_panelboard_table(parsed_text=parsed_text,
                                    table_locations=tables_locations,
                                    original_h=pdf_size[1],
                                    original_w=pdf_size[0],
                                    img_array=img_array,
                                    inner_heuristic_config=settings.INNER_HEURISTIC_CONFIG,
                                    upper_heuristic_config=settings.UPPER_HEURISTIC_CONFIG,
                                    elements_detection_config=settings.ELEMENTS_DETECTION_CONFIG,
                                    remove_border=remove_border)

    return UJSONResponse(content=tables)


@dataclass()
class ExtractClassifiedObjectsJsonData:
    closed_objects: dict = None
    lines:          dict = None
    parsed_text:    dict = None


# ________________________________________________________________________________
@parse_panelboard_rtr.post(path="/parse-panelboard-table-s3/",
                           responses={200: {}, 500: {}, 503: {}},
                           status_code=status.HTTP_200_OK,
                           response_class=UJSONResponse,
                           tags=["PDF Elements Parsing - Panelboard Table Parsing", "S3"],
                           summary="Parse tables relevant to panelboards")
async def parse_panelboard_endpoint_s3(files_data: PanelboardTableParsingS3FilesData) -> Response:
    # ________________________________________________________________________________
    # --- INIT S3 UTILS INSTANCE ---
    s3 = S3Utils()

    # --- DOWNLOAD | PDF FILE | FROM AWS S3 ---
    pdf_file_bytes = s3.download_file_obj(s3_bucket_name=files_data.s3_bucket_name,
                                          s3_file_key=files_data.files.pdf_file.file_key)

    # --- DOWNLOAD | LINES JSON | FROM AWS S3 ---
    lines_json_bytes = s3.download_file_obj(s3_bucket_name=files_data.s3_bucket_name,
                                            s3_file_key=files_data.files.lines_json.file_key)
    lines_json_decoded = lines_json_bytes.getvalue().decode("utf-8")
    lines = json.loads(lines_json_decoded)

    # --- DOWNLOAD | PARSED TEXT JSON | FROM AWS S3 ---
    parsed_text_json_bytes = s3.download_file_obj(s3_bucket_name=files_data.s3_bucket_name,
                                                  s3_file_key=files_data.files.parsed_text_json.file_key)
    parsed_text_json_decoded = parsed_text_json_bytes.getvalue().decode("utf-8")
    parsed_text = json.loads(parsed_text_json_decoded)

    # --- DOWNLOAD | TABLES LOCATIONS JSON | FROM AWS S3 ---
    if files_data.files.tables_locations_json:
        tables_locations_json_bytes = s3.download_file_obj(s3_bucket_name=files_data.s3_bucket_name,
                                                           s3_file_key=files_data.files.tables_locations_json.file_key)
        tables_locations_json_decoded = tables_locations_json_bytes.getvalue().decode("utf-8")
        tables_locations = json.loads(tables_locations_json_decoded)
    else:
        tables_locations = []

    # ________________________________________________________________________________
    # --- PARSE PANELBOARD TABLES ---
    # ________________________________________________________________________________
    # - GET PARSED TEXT
    parsed_text, pdf_width, pdf_height = parsed_text['parsed_text'], \
                                         parsed_text['pdf_width'], \
                                         parsed_text['pdf_height']

    # - GET PDF
    doc, page, img_array, pdf_size = load_pdf(pdf_file_obj=pdf_file_bytes,
                                              page_num=files_data.page_num,
                                              s3_origin=True)

    if files_data.table_as_input:
        tables_locations = [[0, 0, pdf_width, pdf_height]]


    # - PARSE PANELBOARD TABLES
    tables = parse_panelboard_table(parsed_text=parsed_text,
                                    table_locations=tables_locations,
                                    original_h=pdf_size[1],
                                    original_w=pdf_size[0],
                                    img_array=img_array,
                                    inner_heuristic_config=settings.INNER_HEURISTIC_CONFIG,
                                    upper_heuristic_config=settings.UPPER_HEURISTIC_CONFIG,
                                    elements_detection_config=settings.ELEMENTS_DETECTION_CONFIG,
                                    remove_border=files_data.remove_border)
    # ________________________________________________________________________________

    # --- CONVERT JSON TO BYTES STREAM ---
    json_payload = json.dumps(tables)
    json_byte_stream = io.BytesIO(json_payload.encode("utf-8"))

    # --- UPLOAD FILE TO AWS S3 BUCKET ---
    try:
        s3_upload_status = s3.upload_file_obj(s3_bucket_name=files_data.s3_bucket_name,
                                              s3_file_key=files_data.out_s3_file_key,
                                              file_byte_stream=json_byte_stream)
        if not s3_upload_status:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"ERROR -> S3 upload status: {s3_upload_status}")
        return Response(status_code=status.HTTP_200_OK)

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"ERROR -> Failed to upload file to S3. Error: {e}")
