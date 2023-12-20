# >>>> </> STANDARD IMPORTS </>
# >>>> ********************************************************************************
from typing import Optional
# >>>> ********************************************************************************

# >>>> </> EXTERNAL IMPORTS </>
# >>>> ********************************************************************************
from pydantic import BaseModel, Field
# >>>> ********************************************************************************


# ________________________________________________________________________________
class PDFFileAttrs(BaseModel):
    file_key: str = "sample/file/path.pdf"


class JSONFileAttrs(BaseModel):
    file_key: str = "sample/file/path.json"


# ________________________________________________________________________________
class TextParsingS3Files(BaseModel):
    pdf_file: PDFFileAttrs


class TextParsingS3FilesData(BaseModel):
    """
    - Data model for the request body of the /parse-text-s3/ endpoint.
    """
    files: TextParsingS3Files
    s3_bucket_name: str = "s3-bucket-name-sample"
    out_s3_file_key: str = "sample/file/path.json"

    page_num: Optional[int] = 0
    return_svg_size: Optional[bool] = True
    return_attributes: Optional[bool] = False

    class Config:
        title = "TextParsingS3FilesData"
        schema_extra = {
            "files": {
                "pdf_file": {
                    "file_key": "sample/file/path.pdf"
                }
            },
            "s3_bucket_name": "s3-bucket-name-sample",
            "out_s3_file_key": "sample/file/path.json",

            "page_num": 0,
            "return_svg_size": True,
            "return_attributes": False
        }


# ________________________________________________________________________________
class SpecialSymbolsParsingS3Files(BaseModel):
    lines_json:         JSONFileAttrs
    parsed_text_json:   JSONFileAttrs


class SpecialSymbolsParsingS3FilesData(BaseModel):
    """
    - Data model for the request body of the /parse-special-symbols-s3/ endpoint.
    """
    files: SpecialSymbolsParsingS3Files
    s3_bucket_name: str = "s3-bucket-name-sample"
    out_s3_file_key: str = "sample/file/path.json"

    class Config:
        title = "SpecialSymbolsParsingS3FilesData"
        schema_extra = {
            "files": {
                "lines_json": {
                    "file_key": "sample/file/path.json"
                },
                "parsed_text_json": {
                    "file_key": "sample/file/path.json"
                }
            },
            "s3_bucket_name": "s3-bucket-name-sample",
            "out_s3_file_key": "sample/file/path.json"
        }


# ________________________________________________________________________________
class ParseSldTableS3Files(BaseModel):
    pdf_file:               PDFFileAttrs
    lines_json:             JSONFileAttrs
    parsed_text_json:       JSONFileAttrs
    tables_locations_json:  JSONFileAttrs = None


class ParseSldTableS3FilesData(BaseModel):
    """
    - Data model for the request body of the /parse-sld-table-s3/ endpoint.
    """
    files: ParseSldTableS3Files
    s3_bucket_name: str = "s3-bucket-name-sample"
    out_s3_file_key: str = "sample/file/path.json"

    page_num: Optional[int] = 0
    table_as_input: Optional[bool] = True

    class Config:
        title = "ParseSldTableS3FilesData"
        schema_extra = {
            "files": {
                "pdf_file": {
                    "file_key": "sample/file/path.pdf"
                },
                "lines_json": {
                    "file_key": "sample/file/path.json"
                },
                "parsed_text_json": {
                    "file_key": "sample/file/path.json"
                }
            },
            "s3_bucket_name": "s3-bucket-name-sample",
            "out_s3_file_key": "sample/file/path.json",

            "page_num": 0,
            "table_as_input": True
        }


# ________________________________________________________________________________
class PanelboardTableParsingS3Files(BaseModel):
    pdf_file:               PDFFileAttrs
    lines_json:             JSONFileAttrs
    parsed_text_json:       JSONFileAttrs
    tables_locations_json:  JSONFileAttrs = None


class PanelboardTableParsingS3FilesData(BaseModel):
    """55
    - Data model for the request body of the /parse-panelboard-table-s3/ endpoint.
    """
    files: PanelboardTableParsingS3Files
    s3_bucket_name: str = "s3-bucket-name-sample"
    out_s3_file_key: str = "sample/file/path.json"

    page_num: Optional[int] = 0
    table_as_input: Optional[bool] = True
    remove_border: Optional[bool] = False

    class Config:
        title = "PanelboardTableParsingS3FilesData"
        schema_extra = {
            "files": {
                "pdf_file": {
                    "file_key": "sample/file/path.pdf"
                },
                "lines_json": {
                    "file_key": "sample/file/path.json"
                },
                "parsed_text_json": {
                    "file_key": "sample/file/path.json"
                }
            },
            "s3_bucket_name": "s3-bucket-name-sample",
            "out_s3_file_key": "sample/file/path.json",

            "page_num": 0,
            "table_as_input": True,
            "remove_border": False
        }
