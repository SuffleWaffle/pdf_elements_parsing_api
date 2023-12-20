from src_utils.geometry_utils import check_line_type, scale, get_line_length,\
    fix_coords_line
from src_utils.table_parsing import find_lines_in_tables_svg, find_lines_in_tables_img, \
    merge_close_lines_tables, merge_on_one_line_tables, text_in_table, drop_by_threshold, \
    find_column_segment_sld, get_horziontal_lines_inside, get_vertical_lines_inside_sld, \
    fix_text_bbox_vlines, get_columns, find_double_tables_sld, merge_h_lines_on_same_line, \
    check_line_x_ovelapping, get_rows, post_process_table, to_json_preparation, notes_removal, prepare_list_in_val, \
    prepare_list_of_table_rows, values_to_list
from src_utils.text_parsing import filter_parsed_text
from src_utils.img_processing import delete_objects, del_by_existence
from copy import deepcopy
import numpy as np
from src_logging.log_config import setup_logger
logger = setup_logger(__name__)


def parse_sld_table(parsed_text: list,
                    lines: list,
                    table_locations: list,
                    img_array: np.array,
                    config:dict,
                    svg_width: float,
                    svg_height: float,
                    original_width: int = None,
                    original_height: int = None,
                    changed_len: bool = False
                    ):
    # UPD_VACHU TODO wrap to func: separate merged text spans                  
    list_parsed_text = []
    list_T = []
    for text_bl in parsed_text:
        if text_bl['spans'].__len__() > 1:
            for text_bl_spans in text_bl['spans']:
                if text_bl_spans['message'] != ' ':
                    print(text_bl_spans['message'])
                    Temp_dict = {}
                    Temp_dict['spans'] = [text_bl_spans]
                    Temp_dict['x0'] = text_bl_spans['x0']
                    Temp_dict['y0'] = text_bl_spans['y0']
                    Temp_dict['x1'] = text_bl_spans['x1']
                    Temp_dict['y1'] = text_bl_spans['y1']
                    list_parsed_text.append(Temp_dict)
                    list_T.append(Temp_dict)
        else:
            list_parsed_text.append(text_bl)
    parsed_text = deepcopy(list_parsed_text)
                        
    # initialize container for results
    original_table_coords = [tuple(i) for i in table_locations]
    # scale lines if needed
    #logger.info([original_width, original_height,
    #      svg_width, svg_height])
    if original_width and original_height:
        lines = [list(map(int, scale(line, (svg_width, svg_height),
                                     (original_width, original_height)))) for line in lines]

    # process lines
    lines = list(map(fix_coords_line, lines))
    lines = list(set([tuple(i) for i in lines]))
    lines = [i for i in lines if get_line_length(i) != 1]
    lines = [i for i in lines if check_line_type(i) in ('horizontal', 'vertical')]
    # if original_width/original_height -> scale to size of lines
    #logger.info(table_locations)
    tables = find_lines_in_tables_svg(lines, table_locations,
                                      **config['find_lines_in_tables_svg'])

    if not all([bool(v[0] or v[1]) for v in tables.values()]) or \
        changed_len:
        tables = find_lines_in_tables_img(img_array, table_locations,
                                          **config['find_lines_in_tables_img'])
    # process img
    text_coords = [list(map(int, [i['x0'], i['y0'], i['x1'], i['y1']])) \
                   for i in parsed_text]
    img_processed = delete_objects(deepcopy(img_array), text_coords)

    # filter bad lines
    for k, v in tables.items():
        h_lines, v_lines = v
        #logger.info(v_lines[:5])
        tables[k] = [del_by_existence(img_processed, h_lines,
                                      **config['filter_bad_lines']),
                     del_by_existence(img_processed, v_lines,
                                      **config['filter_bad_lines'])]
    # logger.info('TABLE')
    # logger.info(tables[(167, 200, 760, 821)])
    # logger.info('TABLE')
    # merge close lines
    tables = merge_close_lines_tables(tables,
                                     **config['merge_close_lines'])
    # merge lines on one line
    tables = merge_on_one_line_tables(tables,
                                      **config['merge_on_one_line'])
    dict_list_of_table_rows = {}
    found_tables = []
    # actual process
    for table_coords, lines_container in tables.items():
        v_lines, h_lines = lines_container
        # find text in table
        found_text_in_table = text_in_table(table_coords, parsed_text,
                                            **config['find_text_in_table'])
        # drop lines by threshold
        if found_text_in_table:
            v_lines, h_lines = drop_by_threshold(found_text_in_table, v_lines, h_lines,
                                                 **config['drop_by_threshold'])
        else:
            found_tables.append({'tables': [],
                                 'error': 'No text in table'})
            continue

        # drop vertical lines by threshold
        thr = np.min(np.diff(sorted([i[1] for i in h_lines])))
        thr = max(thr, config['drop_v_lines_by_threshold']['max_val'])

        v_lines = [i for i in v_lines if abs(i[1] - i[3]) > thr]
        #logger.info('hv_lines')
        #logger.info(v_lines)
        #logger.info(h_lines)
        #logger.info('hv_lines')
        # process lines
        h_lines = [list(map(int, i)) for i in h_lines]
        v_lines = [list(map(int, i)) for i in v_lines]
        # find column and inner segments
        column_segment, start_line = find_column_segment_sld(table_coords,
                                                             deepcopy(h_lines), deepcopy(v_lines),
                                                             **config['find_column_segment'])
        inner_segment = [start_line[0], start_line[1], start_line[2], table_coords[3]]
        # get lines in segments
        h_lines, v_lines = get_horziontal_lines_inside(inner_segment, h_lines), \
                           get_vertical_lines_inside_sld(inner_segment, v_lines,
                                                         **config['get_vertical_lines_inside'])

        v_lines += [[inner_segment[0], inner_segment[1], inner_segment[0], inner_segment[3]],
                    [inner_segment[2], inner_segment[1], inner_segment[2], inner_segment[3]]]
        h_lines += [[inner_segment[0], inner_segment[1], inner_segment[2], inner_segment[1]],
                    [inner_segment[0], inner_segment[3], inner_segment[2], inner_segment[3]]]

        column_segment_v_lines = [[i[0], column_segment[1], i[2], column_segment[3]] for i in v_lines]

        # process text in inner segment
        text_in_inner_segment = text_in_table(inner_segment, found_text_in_table, c=0)

        text_in_inner_segment = fix_text_bbox_vlines(found_text=text_in_inner_segment, v_lines=v_lines,
                                                     **config['fix_text_bbox_vlines'])
        

        # get columns
        columns = get_columns(text_in_inner_segment, column_segment, column_segment_v_lines,
                              **config['get_columns'])

        # find double tables
        double_tables = find_double_tables_sld(columns)
        # processing of double_tables
        found_inner_tables = []
        list_in_val = []
        list_all_dropped_idx = []
        for double_table in double_tables:
            # get lines relevant to double table segments
            row_segment = [column_segment[0], column_segment[3], column_segment[2], inner_segment[3]]
            h_lines_row_segment = get_horziontal_lines_inside(row_segment, h_lines)
            h_lines_row_segment = merge_h_lines_on_same_line(h_lines_row_segment,
                                                             **config['merge_h_lines_on_same_line'])
            double_table_segment = [double_table[0][1][0][0], column_segment[3], \
                                    double_table[-1][1][-1][2], inner_segment[3]]

            upper_line = [double_table_segment[0], double_table_segment[1], double_table_segment[2],
                          double_table_segment[1]]

            double_table_segment_len = abs(double_table_segment[0] - double_table_segment[2])
            h_lines_double_table_segment = [i for i in h_lines_row_segment \
                                            if check_line_x_ovelapping(i, upper_line)]

            h_lines_double_table_segment = [i for i in h_lines_double_table_segment if
                                            (i[2] - i[0]) / double_table_segment_len > 0.85]

            h_lines_double_table_segment = [(upper_line[0], i[1], upper_line[2], i[3]) for i in
                                            h_lines_double_table_segment]

            if not upper_line in h_lines_double_table_segment:
                h_lines_double_table_segment = [upper_line] + h_lines_double_table_segment
                h_lines_double_table_segment = sorted(h_lines_double_table_segment, key=lambda x: x[1])
            # get rows
            inner_info, h_bboxes = get_rows(double_table, h_lines_double_table_segment, text_in_inner_segment,
                                            **config['get_rows'])
            list_in_val.append([inner_info, h_bboxes])
            inner_info = inner_info.reset_index()
            inner_info.drop(columns='index', inplace=True)
            #logger.info(inner_info.shape)
            # postprocess table
            inner_info, dropped_idx = post_process_table(inner_info, **config['post_process_table'])
            # table to dict records
            json_records = inner_info.to_dict('records')
            # save double tables
            found_inner_tables.append(json_records)
            list_all_dropped_idx.append(dropped_idx)
            
        list_in_val = prepare_list_in_val(list_in_val)
        list_of_table_rows = prepare_list_of_table_rows(list_in_val, list_all_dropped_idx)
        dict_list_of_table_rows[table_coords] = list_of_table_rows
        # save result with tables
        found_tables.append({'tables': found_inner_tables,
                             'error': None})
    found_tables_dict = dict(zip(original_table_coords, found_tables))
    found_tables_dict = to_json_preparation(found_tables_dict)

    found_tables_dict = notes_removal(found_tables_dict, dict_list_of_table_rows)
    values_to_list(found_tables_dict)
    return found_tables_dict
