# >>>> </> STANDARD IMPORTS </>
# >>>> ********************************************************************************
import logging
# >>>> ********************************************************************************

# >>>> </> EXTERNAL IMPORTS </>
# >>>> ********************************************************************************
from fastapi import APIRouter, HTTPException
from fastapi import status, UploadFile, File, Form
from fastapi.responses import UJSONResponse, StreamingResponse, Response
# from starlette.responses import StreamingResponse
import PIL.Image as pil_image
import ujson as json

import settings
# >>>> ********************************************************************************

# >>>> </> LOCAL IMPORTS </>
# >>>> ********************************************************************************
from src_logging import log_config
from src_processes.parse_text import parse_text
from src_utils.loading_utils import load_pdf
from src_utils.plotting_utils import plot_extracted_messages
from src_utils.zipping_utils import FileProc
from src_utils.aws_utils import S3FileOps
from .request_models import TextParsingS3FilesData
# >>>> ********************************************************************************


# ________________________________________________________________________________
# --- INIT CONFIG - LOGGER SETUP ---
logger = log_config.setup_logger(logger_name=__name__, logging_level=logging.DEBUG)

# ________________________________________________________________________________
# --- FastAPI ROUTER ---
parse_text_rtr = APIRouter(prefix="/v1")


# ________________________________________________________________________________
# @parse_text_rtr.post(path="/parse-text-zip/",
#                      responses={200: {}, 404: {"description": "No text found in pdf"}},
#                      status_code=status.HTTP_200_OK,
#                      response_class=Response,
#                      tags=["Parse Text", "ZIP"],
#                      summary="Parse text from PDF and return ZIP archive")
# async def parse_text_zip_func(file: UploadFile = File(...),
#                               page_num: int = Form(0),
#                               visualize_results: bool = Form(True)) -> StreamingResponse:
#     doc, page, img_array, pdf_size = load_pdf(pdf_file_obj=file,
#                                               page_num=page_num,
#                                               s3_origin=False)
#
#     parsed_text, changed_len = parse_text(page, pdf_size[0], pdf_size[1])
#     parsed_text = {'parsed_text': parsed_text,
#                    'pdf_width': pdf_size[0],
#                    'pdf_height': pdf_size[1],
#                    'changed_len': changed_len}
#
#     if not parsed_text:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
#                             detail=f"No text found in pdf")
#
#     file_name = 'parsed_text.zip'
#     if not visualize_results:
#         resp_content, resp_media_type = FileProc.get_zip_with_json({'parsed_text': parsed_text})
#
#     else:
#         img = plot_extracted_messages(page, parsed_text['parsed_text'])
#         img = pil_image.fromarray(img)
#         json_content = {"parsed_text": parsed_text}
#         img_content = {"test_img": img}
#         resp_content, resp_media_type = FileProc.get_zip_with_json_and_img(json_content=json_content,
#                                                                            img_content=img_content)
#
#     return StreamingResponse(content=resp_content,
#                              status_code=status.HTTP_200_OK,
#                              headers={"Content-Disposition": f"attachment; filename={file_name}"},
#                              media_type="application/zip")


# ________________________________________________________________________________
@parse_text_rtr.post(path="/parse-text-json/",
                     responses={200: {}, 404: {}, 500: {}, 503: {}},
                     status_code=status.HTTP_200_OK,
                     response_class=Response,
                     tags=["Parse Text", "JSON"],
                     summary="Parse text from PDF and return JSON")
async def post_parse_text_json_func(file: UploadFile = File(...),
                                    page_num: int = 0) -> UJSONResponse:
    doc, page, img_array, pdf_size = load_pdf(pdf_file_obj=file,
                                              page_num=page_num,
                                              s3_origin=False)

    parsed_text, changed_len = parse_text(page, pdf_size[0], pdf_size[1],
                                          **settings.OCR_SETTING)
    parsed_text = {'parsed_text': parsed_text,
                   'pdf_width': pdf_size[0],
                   'pdf_height': pdf_size[1],
                   'changed_len': changed_len}

    # if not parsed_text:
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
    #                         detail=f"No text found in pdf")

    return UJSONResponse(content=parsed_text,
                         status_code=status.HTTP_200_OK,
                         media_type="application/json")


# ________________________________________________________________________________
@parse_text_rtr.post(path="/parse-text-json-s3/",
                     responses={200: {}, 500: {}, 503: {}},
                     status_code=status.HTTP_200_OK,
                     response_class=Response,
                     tags=["Parse Text", "S3"],
                     summary="Parse text from PDF and return JSON")
async def post_parse_text_json_s3_func(files_data: TextParsingS3FilesData) -> Response:
    # ________________________________________________________________________________
    # --- INIT S3FileOps INSTANCE ---
    s3 = S3FileOps(s3_bucket_name=files_data.s3_bucket_name)

    # --- DOWNLOAD PDF FILE FROM AWS S3 ---
    logger.info("- 1 - DOWNLOADING PDF FILE FROM AWS S3 -")
    pdf_file_bytes = s3.download_file_obj(s3_bucket_name=files_data.s3_bucket_name,
                                          s3_file_key=files_data.files.pdf_file.file_key)
    # --- LOAD PDF FILE DATA ---
    logger.info("- 2 - LOADING PDF FILE DATA -")
    doc, page, img_array, pdf_size = load_pdf(pdf_file_obj=pdf_file_bytes,
                                              page_num=files_data.page_num,
                                              s3_origin=True)

    # ________________________________________________________________________________
    # --- PARSE TEXT ---
    logger.info("- 3 - PARSING TEXT -")

    parsed_text, changed_len = parse_text(page=page,
                                          width=pdf_size[0],
                                          height=pdf_size[1],
                                          **settings.OCR_SETTING)

    parsed_text = {'parsed_text': parsed_text,
                   'pdf_width': pdf_size[0],
                   'pdf_height': pdf_size[1],
                   'changed_len': changed_len}

    if not parsed_text:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No text found in pdf")

    # ________________________________________________________________________________
    # --- UPLOAD RESULTS TO AWS S3 ---
    try:
        logger.info("- 4 - UPLOADING RESULTS TO AWS S3 -")

        s3.upload_json_file_to_bucket(s3_file_key=files_data.out_s3_file_key,
                                      data_for_json=parsed_text)

        return Response(status_code=status.HTTP_200_OK)

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"ERROR -> Failed to upload file to S3. Error: {e}")
