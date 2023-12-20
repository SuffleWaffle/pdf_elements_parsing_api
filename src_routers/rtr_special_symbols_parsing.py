# >>>> </> STANDARD IMPORTS </>
# >>>> ********************************************************************************
import logging
import io
# >>>> ********************************************************************************

# >>>> </> EXTERNAL IMPORTS </>
# >>>> ********************************************************************************
from fastapi import APIRouter, HTTPException, Response
from fastapi import status
from fastapi.responses import UJSONResponse
from pydantic import BaseModel
import ujson as json
# >>>> ********************************************************************************

# >>>> </> LOCAL IMPORTS </>
# >>>> ********************************************************************************
from src_logging import log_config
from src_processes.special_symbols_parsing import parse_special_symbols
from settings import SPECIAL_SYMBOLS_CONF
from src_utils.aws_utils import S3Utils
from .request_models import SpecialSymbolsParsingS3FilesData
# >>>> ********************************************************************************


# ________________________________________________________________________________
# --- INIT CONFIG - LOGGER SETUP ---
logger = log_config.setup_logger(logger_name=__name__, logging_level=logging.DEBUG)

# ________________________________________________________________________________
# --- FastAPI ROUTER ---
special_symbols_parse_rtr = APIRouter(prefix="/v1")


class Data(BaseModel):
    lines: dict
    parsed_text: dict


# ________________________________________________________________________________
@special_symbols_parse_rtr.post(path="/parse-special-symbols/",
                                responses={200: {}, 500: {}, 503: {}},
                                status_code=status.HTTP_200_OK,
                                response_class=UJSONResponse,
                                summary="Parse special symbols using SVG lines and convert them to text")
async def parse_special_symbols_endpoint(data: Data) -> UJSONResponse:
    lines = data.lines
    parsed_text = data.parsed_text

    parsed_text, pdf_width, pdf_height, changed_len = (parsed_text["parsed_text"],
                                                       parsed_text["pdf_width"],
                                                       parsed_text["pdf_height"],
                                                       parsed_text["changed_len"])

    svg_width, svg_height, lines = int(lines["svg_width"]), int(lines["svg_height"]), lines["lines_data"]
    parsed_text = parse_special_symbols(parsed_text, lines,
                                        pdf_width=pdf_width,
                                        pdf_height=pdf_height,
                                        svg_width=svg_width,
                                        svg_height=svg_height,
                                        triangle_symbol=SPECIAL_SYMBOLS_CONF["triangle"],
                                        y_symbol=SPECIAL_SYMBOLS_CONF["y"])
    parsed_text = {"parsed_text": parsed_text,
                   "pdf_width": pdf_width,
                   "pdf_height": pdf_height,
                   "changed_len": changed_len}

    return UJSONResponse(content=parsed_text)


# ________________________________________________________________________________
@special_symbols_parse_rtr.post(path="/parse-special-symbols-s3/",
                                responses={200: {}, 500: {}, 503: {}},
                                status_code=status.HTTP_200_OK,
                                response_class=Response,
                                tags=["PDF Elements Parsing - Special Symbols Parsing", "S3"],
                                summary="Parse special symbols using SVG lines and convert them to text")
async def parse_special_symbols_endpoint_s3(files_data: SpecialSymbolsParsingS3FilesData) -> Response:
    # ________________________________________________________________________________
    # --- INIT S3 UTILS INSTANCE ---
    s3 = S3Utils()

    # --- DOWNLOAD LINES JSON FROM AWS S3 ---
    lines_json_bytes = s3.download_file_obj(s3_bucket_name=files_data.s3_bucket_name,
                                            s3_file_key=files_data.files.lines_json.file_key)
    lines_json_decoded = lines_json_bytes.getvalue().decode("utf-8")
    lines_data = json.loads(lines_json_decoded)

    # --- DOWNLOAD PARSED TEXT JSON FROM AWS S3 ---
    parsed_text_json_bytes = s3.download_file_obj(s3_bucket_name=files_data.s3_bucket_name,
                                                  s3_file_key=files_data.files.parsed_text_json.file_key)
    parsed_text_json_decoded = parsed_text_json_bytes.getvalue().decode("utf-8")
    parsed_text_data = json.loads(parsed_text_json_decoded)

    # ________________________________________________________________________________
    # --- PARSE SPECIAL SYMBOLS  ---
    # ________________________________________________________________________________
    lines = lines_data
    parsed_special_symbols = parsed_text_data

    parsed_special_symbols, pdf_width, pdf_height, changed_len = (parsed_special_symbols["parsed_text"],
                                                                  parsed_special_symbols["pdf_width"],
                                                                  parsed_special_symbols["pdf_height"],
                                                                  parsed_special_symbols["changed_len"])

    svg_width, svg_height, lines = int(lines["svg_width"]), int(lines["svg_height"]), lines["lines_data"]

    parsed_special_symbols = parse_special_symbols(parsed_text=parsed_special_symbols,
                                                   lines=lines,
                                                   pdf_width=pdf_width,
                                                   pdf_height=pdf_height,
                                                   svg_width=svg_width,
                                                   svg_height=svg_height,
                                                   triangle_symbol=SPECIAL_SYMBOLS_CONF["triangle"],
                                                   y_symbol=SPECIAL_SYMBOLS_CONF["y"])

    parsed_special_symbols = {"parsed_text": parsed_special_symbols,
                              "pdf_width": pdf_width,
                              "pdf_height": pdf_height,
                              "changed_len": changed_len}
    # ________________________________________________________________________________

    # --- CONVERT JSON TO BYTES STREAM ---
    json_payload = json.dumps(parsed_special_symbols)
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
