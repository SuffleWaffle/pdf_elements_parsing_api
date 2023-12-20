import fitz
import PIL.Image as pil_image
import numpy as np
from src_logging.log_config import setup_logger

logger = setup_logger(__name__)


def load_pdf(pdf_file_obj, page_num: int = 0, s3_origin: bool = False):
    """
    Load PDF file from file object.

    Parameters:
        pdf_file_obj (FileStorage): PDF file object.
        page_num (int): Page number to load.
        s3_origin (bool): If True, then pdf_file_obj is a BytesIO object from S3.
    """
    if s3_origin:
        doc = fitz.open(stream=pdf_file_obj,
                        filetype="pdf")
    else:
        doc = fitz.open(stream=pdf_file_obj.file.read(),
                        filetype="pdf")
    page = doc[page_num]
    pix = page.get_pixmap()
    pdf_size = (pix.width, pix.height)
    img = pil_image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    img_array = np.array(img)
    return doc, page, img_array, pdf_size


def load_image_from_page(page):
    pixmap = page.get_pixmap()
    img = pil_image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
    return img, pixmap.width, pixmap.height
