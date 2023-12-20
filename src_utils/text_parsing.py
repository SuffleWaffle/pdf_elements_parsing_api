import fitz
from tqdm import tqdm
import numpy as np
import cv2
from src_utils.geometry_utils import fix_coords, scale, make_bigger_bbox
import pytesseract
import PIL.Image as pil_image


def filter_parsed_text(parsed_text, height, width):
    filtered = []
    for i in parsed_text:
        xs = i['x0'], i['x1']
        ys = i['y0'], i['y1']
        if not (any([j > width for j in xs]) or any([j > height for j in ys])):
            filtered.append(i)
    return filtered


def parse_text_pdf(page):
    result = page.get_text('rawdict')
    new_results = []

    if page.rotation:
        rot_mat = page.rotation_matrix

    for block in result['blocks']:
        try:
            for inner_block in block['lines']:

                spans = {'spans': []}
                bbox = inner_block['bbox']
                if page.rotation:
                    bbox_0, bbox_1 = list(fitz.Point(*bbox[:2]) * rot_mat), \
                                     list(fitz.Point(*bbox[2:]) * rot_mat)
                    bbox = bbox_0 + bbox_1
                spans['x0'], spans['y0'], spans['x1'], spans['y1'] = fix_coords(bbox)

                for span in inner_block['spans']:
                    d = {}
                    bbox = span['bbox']

                    if page.rotation:
                        bbox_0, bbox_1 = list(fitz.Point(*bbox[:2]) * rot_mat), \
                                         list(fitz.Point(*bbox[2:]) * rot_mat)
                        bbox = bbox_0 + bbox_1

                    d['x0'], d['y0'], d['x1'], d['y1'] = fix_coords(bbox)

                    d['size'] = span['size']
                    d['color'] = span['color']
                    d['font'] = span['font']
                    d['message'] = ''.join([i['c'] for i in span['chars']])

                    chars = []

                    for char in span['chars']:
                        char_d = {}

                        char_d['message'] = char['c']

                        bbox = char['bbox']

                        if page.rotation:
                            bbox_0, bbox_1 = list(fitz.Point(*bbox[:2]) * rot_mat), \
                                             list(fitz.Point(*bbox[2:]) * rot_mat)
                            bbox = bbox_0 + bbox_1

                        char_d['x0'], char_d['y0'], char_d['x1'], char_d['y1'] = fix_coords(bbox)

                        chars.append(char_d)

                    d['chars'] = chars

                    if 'unoccupied' in d['message'].lower():
                        continue
                    container = spans['spans']
                    container.append(d)
                    spans['spans'] = container
                new_results.append(spans)
        except Exception as e:
            pass

    return new_results


def ocr_text(page, text_dict,
             pdf_size, ocr_config='',
             dpi=300,
             to_add_border_pix=5):
    # get mapping
    mapping = {}
    for c1, i in enumerate(text_dict):
        for c2, j in enumerate(i['spans']):
            if '�' in j['message'] or \
                    '∅' in j['message']:
                mapping[(c1, c2)] = [j['x0'], j['y0'], j['x1'], j['y1']]

    # get image and process it
    pix = page.get_pixmap(dpi=dpi)
    img = pil_image.frombytes('RGB', [pix.width, pix.height], pix.samples)
    img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    img = pil_image.fromarray(img)
    # ocr
    to_del = []
    for k, bbox in tqdm(mapping.items()):
        bbox = scale(make_bigger_bbox([list(map(round, bbox))], to_add_border_pix)[0], pdf_size, (pix.width, pix.height))
        text = pytesseract.image_to_string(img.crop(bbox),
                                           config=ocr_config)
        if text:
            text_dict[k[0]]['spans'][k[1]]['message'] = text.strip()
            for i in text_dict[k[0]]['spans']:
                i['color'] = 0
        else:
            to_del.append(k[0])
    # delete those which were not found
    text_dict = [i for c, i in enumerate(text_dict) if c not in to_del]
    return text_dict
