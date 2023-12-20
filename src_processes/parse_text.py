from src_utils.text_parsing import parse_text_pdf, ocr_text, filter_parsed_text
from src_logging.log_config import setup_logger

logger = setup_logger(__name__)


def parse_text(page, width, height,
               apply_ocr=False,
               ocr_config='',
               to_add_border_pix=0,
               dpi=500):
    # here should also be functionality for global OCR
    # parse text from pdf
    parsed_text = parse_text_pdf(page)
    logger.info('Parsed text from pdf')
    # filter parsed text by location
    len_before = len(parsed_text)
    parsed_text = filter_parsed_text(parsed_text, width=width,
                                     height=height)
    len_after = len(parsed_text)
    logger.info(f'Filtered parsed text, number of instances deleted : {len_before-len_after}')
    # additional functionality for local OCR
    if apply_ocr:
        try:
            parsed_text = ocr_text(page, parsed_text,
                                   pdf_size=(width, height),
                                   to_add_border_pix=to_add_border_pix,
                                   dpi=dpi,
                                   ocr_config=ocr_config)
        except Exception as e:
            logger.info(f'Got exception during OCR : {str(e)}')
            pass
    logger.info('Applied local OCR for � marks')
    return parsed_text, len_before>len_after
