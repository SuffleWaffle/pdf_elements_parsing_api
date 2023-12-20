import PIL.Image as pil_image
from src_utils.table_parsing import find_lines_in_tables_img, get_horziontal_lines_inside, \
    merge_close_lines_tables, text_in_table, fix_text_bbox_vlines, get_columns, \
    merge_h_lines_on_same_line, get_contours_from_image, find_tables_and_lines, \
    find_upper_segment, find_inner_segment, get_vertical_lines_inside_panelboard, \
    get_column_segment_panelboard, find_double_tables_panelboard, parse_inner_values
from src_utils.table_values_heuristics import parse_upper_values
from fastapi import HTTPException
import pandas as pd
from copy import deepcopy
from src_logging.log_config import setup_logger

logger = setup_logger(__name__)


def parse_panelboard_table(parsed_text: list,
                           table_locations: list,
                           img_array: pil_image.Image,
                           elements_detection_config: dict,
                           inner_heuristic_config: dict,
                           upper_heuristic_config: dict,
                           original_w: int,
                           original_h: int,
                           remove_border: bool = True):
    # find lines in tables and tables
    #logger.info(f'Table locations : {table_locations}, {all(table_locations)}')
    if table_locations and all(table_locations):
        #logger.info('Find lines in tables')
        tables = find_lines_in_tables_img(img_array, table_locations,
                                          **elements_detection_config['find_lines_in_tables_img'])
    else:
       # logger.info('Iterate through contours')
        for contours in [get_contours_from_image(img_array, False), \
                         get_contours_from_image(img_array, True)]:

            # find tables
            tables = find_tables_and_lines(contours, deepcopy(img_array), original_h=original_h, original_w=original_w,
                                           remove_border=remove_border,
                                           **elements_detection_config['table_searching'])
            if len(tables.values()):
                break

    if not len(tables.values()):
        raise HTTPException(404, 'No tables found')

    # initialize original table coords
    original_table_coords = [tuple(i) for i in tables.keys()]
    logger.info(f'Number of tables identified : {len(original_table_coords)}')
    # merge close lines
    tables = merge_close_lines_tables(tables,
                                      **elements_detection_config['merge_close_lines']
                                      )
    # iterate through each table
    found_tables = []
    for table_coords, table_lines in tables.items():
        try:
            found_text_in_table = text_in_table(table_coords, parsed_text,
                                                **elements_detection_config['text_in_table'])
            v_lines, h_lines = table_lines
            # find upper segment
            upper_segment, end_line_upper_segment = find_upper_segment(table_coords, h_lines,
                                                                       **elements_detection_config[
                                                                           'upper_segment_searching'])
            # find text in upper segment
            text_in_upper_segment = text_in_table(upper_segment, found_text_in_table)
            # find inner segment
            inner_segment = find_inner_segment(end_line_upper_segment, v_lines, h_lines,
                                               **elements_detection_config['inner_segment_searching'])
            # find text in inner segment
            text_in_inner_segment = text_in_table(inner_segment, found_text_in_table)
            # get lines inside inner table
            h_lines, v_lines = get_horziontal_lines_inside(inner_segment, h_lines), \
                               get_vertical_lines_inside_panelboard(inner_segment, v_lines,
                                                                    **elements_detection_config[
                                                                        'get_vertical_lines_inside_panelboard'])

            v_lines += [[inner_segment[0], inner_segment[1], inner_segment[0], inner_segment[3]], \
                        [inner_segment[2], inner_segment[1], inner_segment[2], inner_segment[3]]]
            h_lines += [[inner_segment[0], inner_segment[1], inner_segment[2], inner_segment[1]],
                        [inner_segment[0], inner_segment[3], inner_segment[2], inner_segment[3]]]
            # get column segment
            column_segment = get_column_segment_panelboard(inner_segment, h_lines, \
                                                           **elements_detection_config['get_column_segment'])
            column_segment_height = column_segment[3] - column_segment[1]
            column_segment_v_lines = [[i[0], column_segment[1], i[2], column_segment[3]] for i in v_lines if
                                      abs(i[1] - column_segment[1]) <
                                      column_segment_height * (
                                              1 - elements_detection_config['column_segment_v_lines'][
                                          'percentage'])]

            # fix of text bbox intersection with vertical line
            text_in_inner_segment = fix_text_bbox_vlines(found_text=text_in_inner_segment, v_lines=v_lines,
                                                         **elements_detection_config['fix_text_bbox_vlines'])

            # getting columns and their names
            columns = get_columns(text_in_inner_segment, column_segment, column_segment_v_lines,
                                  **elements_detection_config['get_columns'])
            #logger.info(f'Columns : {columns}')

            # finding double tables
            double_tables = find_double_tables_panelboard(columns)
            # merge horizontal lines
            row_segment = [column_segment[0], column_segment[3], column_segment[2], inner_segment[3]]
            h_lines_row_segment = get_horziontal_lines_inside(row_segment, h_lines)
            h_lines_row_segment = merge_h_lines_on_same_line(h_lines_row_segment,
                                                             **elements_detection_config[
                                                                 'merge_h_lines_on_same_line'])
            # parse inner table values and columns
            parsed_table, pandas_tables = parse_inner_values({}, double_tables, h_lines_row_segment,
                                                             column_segment,
                                                             inner_segment,
                                                             text_in_inner_segment,
                                                             heuristic_config=inner_heuristic_config,
                                                             **elements_detection_config['parse_inner_values'])

            # parse upper values
            upper_info = parse_upper_values(upper_segment, text_in_upper_segment, upper_heuristic_config)

            parsed_table.update(upper_info)

            parsed_table_df = pd.DataFrame(dict([(k, v) for k, v in parsed_table.items() \
                                                 if not isinstance(v, str) and v and len(v) > 1]))

            for k, v in parsed_table.items():
                if not v or len(v) == 0:
                    parsed_table_df[k] = None
                elif isinstance(v, str):
                    parsed_table_df[k] = v

            if parsed_table and not parsed_table_df.empty:
                # logger.info(f'Here, {table_coords}')
                found_tables.append({'tables': parsed_table,
                                     'error': None})
            else:
                #logger.info('No info found')
                found_tables.append({'tables': [],
                                     'error': 'No info found inside table'})
        except Exception as e:
            error = e
            logger.error(f'ERROR : {str(e)}')
            found_tables.append({'tables': [],
                                 'error': str(error)})

    found_tables_dict = dict(zip(original_table_coords, found_tables))
    return found_tables_dict
