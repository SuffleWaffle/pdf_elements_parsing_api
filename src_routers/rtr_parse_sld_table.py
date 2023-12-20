# >>>> </> STANDARD IMPORTS </>
# >>>> ********************************************************************************
import logging
import io
# >>>> ********************************************************************************

# >>>> </> EXTERNAL IMPORTS </>
# >>>> ********************************************************************************
from fastapi import APIRouter, HTTPException
from fastapi import status, UploadFile, File, Form, Response
from fastapi.responses import UJSONResponse
from src_processes.parse_sld_table import parse_sld_table
import ujson as json
# >>>> ********************************************************************************

# >>>> </> LOCAL IMPORTS </>
# >>>> ********************************************************************************
import settings
from src_logging import log_config
from src_utils.loading_utils import load_pdf
# from src_utils.plotting_functions import plot_extracted_messages
from src_utils.aws_utils import S3Utils
from .request_models import ParseSldTableS3FilesData
# >>>> ********************************************************************************


# ________________________________________________________________________________
# --- INIT CONFIG - LOGGER SETUP ---
logger = log_config.setup_logger(logger_name=__name__, logging_level=logging.DEBUG)

# ________________________________________________________________________________
# --- FastAPI ROUTER ---
parse_sld_table_rtr = APIRouter(prefix="/v1")


# ________________________________________________________________________________
@parse_sld_table_rtr.post(path="/parse-sld-table/",
                          responses={200: {}, 500: {}, 503: {}},
                          status_code=status.HTTP_200_OK,
                          response_class=UJSONResponse,
                          tags=["Parse SLD Table", "JSON"],
                          summary="Parse tables relevant to feeder schedules")
async def parse_sld_table_endpoint(parsed_text_file: UploadFile = File(...),
                                   lines_file: UploadFile = File(...),
                                   file: UploadFile = File(...),
                                   tables_locations: UploadFile = None,
                                   page_num: int = 0):

    if not parsed_text_file.filename.endswith('.json'):
        raise HTTPException(404, f'File with filename {parsed_text_file.filename} does not end with .json')

    if not lines_file.filename.endswith('.json'):
        raise HTTPException(404, f'File with filename {lines_file.filename} does not end with .json')

    if not file.filename.endswith('.pdf'):
        raise HTTPException(404, f'File with filename {file.filename} does not end with .pdf')

    tables_locations = json.loads(await tables_locations.read()) if tables_locations else []
    logger.info('page_num')
    logger.info(page_num)
    #logger.info(page_num)
    logger.info('page_num')
    lines = await lines_file.read()
    lines = json.loads(lines)

    parsed_text = await parsed_text_file.read()
    parsed_text = json.loads(parsed_text)

    # get parsed text
    parsed_text, pdf_width, pdf_height, changed_len = (parsed_text['parsed_text'],
                                                       parsed_text['pdf_width'],
                                                       parsed_text['pdf_height'],
                                                       parsed_text['changed_len'])

    # get params from lines
    svg_width, svg_height, lines = lines['svg_width'], \
                                   lines['svg_height'], lines['lines_data']
    # get pdf
    doc, page, img_array, pdf_size = load_pdf(pdf_file_obj=file,
                                              page_num=page_num,
                                              s3_origin=False)
    logger.info('img_array')
    logger.info(img_array.shape)
    logger.info(pdf_size)
    logger.info('img_array')
    if not tables_locations:
        tables_locations = [[0, 0, pdf_width, pdf_height]]


    # parse sld tables
    tables = parse_sld_table(parsed_text=parsed_text,
                             lines=lines,
                             table_locations=tables_locations,
                             img_array=img_array,
                             config=settings.SLD_PARSING_CONF,
                             svg_height=svg_height,
                             svg_width=svg_width,
                             original_width=pdf_width,
                             original_height=pdf_height,
                             changed_len=changed_len)

    return UJSONResponse(content=tables)


# ________________________________________________________________________________
@parse_sld_table_rtr.post(path="/parse-sld-table-s3/",
                          responses={200: {}, 500: {}, 503: {}},
                          status_code=status.HTTP_200_OK,
                          response_class=UJSONResponse,
                          tags=["Parse SLD Table", "S3"],
                          summary="Parse tables relevant to feeder schedules")
async def parse_sld_table_endpoint_s3(files_data: ParseSldTableS3FilesData) -> Response:
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
    # --- PARSE SLD TABLES ---
    # ________________________________________________________________________________
    # - GET PARSED TEXT
    parsed_text, pdf_width, pdf_height, changed_len = (parsed_text['parsed_text'],
                                                       parsed_text['pdf_width'],
                                                       parsed_text['pdf_height'],
                                                       parsed_text['changed_len'])

    # - GET PARAMS FROM LINES
    svg_width, svg_height, lines = (lines['svg_width'],
                                    lines['svg_height'],
                                    lines['lines_data'])
    # - GET PDF
    doc, page, img_array, pdf_size = load_pdf(pdf_file_obj=pdf_file_bytes,
                                              page_num=files_data.page_num,
                                              s3_origin=True)

    if files_data.table_as_input:
        tables_locations = [[0, 0, pdf_width, pdf_height]]

    if not files_data.table_as_input and not files_data.files.tables_locations_json:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Expected to get tables_locations when table_as_input=True")

    # - PARSING SLD TABLES
    tables = parse_sld_table(parsed_text=parsed_text,
                             lines=lines,
                             table_locations=tables_locations,
                             img_array=img_array,
                             config=settings.SLD_PARSING_CONF,
                             svg_height=svg_height,
                             svg_width=svg_width,
                             original_width=pdf_width,
                             original_height=pdf_height,
                             changed_len=changed_len)
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
                                detail=f"ERROR -> S3 upload status: FALSE")
        return Response(status_code=status.HTTP_200_OK)

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"ERROR -> Failed to upload file to S3. Error: {e}")
