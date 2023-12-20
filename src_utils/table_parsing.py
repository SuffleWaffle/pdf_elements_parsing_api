import cv2
from src_utils.geometry_utils import fix_coords, scale_crop, fix_coords_line, \
    is_point_inside_bbox, check_line_type, merge_close_lines, \
    merge_on_one_line, rectangle_inside_rectangle, get_line_length, v_h_line_rectangle_overlap
from src_utils.lines_merging import merge_small_lines_all
from collections import Counter
import pandas as pd
from scipy import stats
from src_utils.table_values_heuristics import *
from src_logging.log_config import setup_logger


logger = setup_logger(__name__)


def adaptive_threshold(gray, process_background=True, blocksize=25, c=-2):
    if process_background:
        threshold = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, blocksize, c
        )
    else:
        threshold = cv2.adaptiveThreshold(
            np.invert(gray),
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blocksize,
            c,
        )
    return gray, threshold


def find_lines(
        threshold, regions=None, direction="horizontal", line_scale=15, iterations=0
):
    lines = []

    if direction == "vertical":
        size = threshold.shape[0] // line_scale
        el = cv2.getStructuringElement(cv2.MORPH_RECT, (1, size))
    elif direction == "horizontal":
        size = threshold.shape[1] // line_scale
        el = cv2.getStructuringElement(cv2.MORPH_RECT, (size, 1))
    elif direction is None:
        raise ValueError("Specify direction as either 'vertical' or 'horizontal'")

    if regions is not None:
        region_mask = np.zeros(threshold.shape)
        for region in regions:
            x, y, w, h = region
            region_mask[y: y + h, x: x + w] = 1
        threshold = np.multiply(threshold, region_mask)

    threshold = cv2.erode(threshold, el)
    threshold = cv2.dilate(threshold, el)
    dmask = cv2.dilate(threshold, el, iterations=iterations)

    try:
        _, contours, _ = cv2.findContours(
            threshold.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
    except ValueError:
        # for opencv backward compatibility
        contours, _ = cv2.findContours(
            threshold.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        x1, x2 = x, x + w
        y1, y2 = y, y + h
        if direction == "vertical":
            lines.append(((x1 + x2) // 2, y2, (x1 + x2) // 2, y1))
        elif direction == "horizontal":
            lines.append((x1, (y1 + y2) // 2, x2, (y1 + y2) // 2))

    return dmask, lines


def find_lines_in_tables_img(img, tables_coords: list,
                             margin=0,
                             line_scale=30,
                             iterations=1,
                             blocksize=25,
                             process_background=False):
    tables = {}
    shapes_to_scale = img.shape[1], img.shape[0]
    for coords in tables_coords:
        coords = fix_coords(coords)
        x1, y1, x2, y2 = coords
        cropped_img = img[y1 + margin: y2 - margin, x1 + margin: x2 - margin]
        gray = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY)
        _, threshold = adaptive_threshold(gray, process_background, blocksize=blocksize)

        h_mask, h_lines = find_lines(threshold, direction="horizontal", iterations=iterations,
                                     line_scale=line_scale)
        v_mask, v_lines = find_lines(threshold, direction="vertical", iterations=iterations,
                                     line_scale=line_scale)

        v_lines = [scale_crop(i, coords, shapes_to_scale) for i in v_lines]
        h_lines = [scale_crop(i, coords, shapes_to_scale) for i in h_lines]
        tables[(x1, y1, x2, y2)] = [v_lines, h_lines]

    return tables


def find_lines_in_tables_svg(lines,
                             tables_coords: list,
                             tol=1):
    tables = {}
    for coords in tables_coords:
        coords = fix_coords(coords)
        v_lines = []
        h_lines = []
        for line in lines:
            line = fix_coords_line(line)
            line_type = check_line_type(line)
            start, end = line[:2], line[2:]
            if is_point_inside_bbox(start, coords, tol) and is_point_inside_bbox(end, coords, tol):
                if line_type == 'vertical':
                    v_lines.append(line)
                elif line_type == 'horizontal':
                    h_lines.append(line)

        tables[tuple(coords)] = [merge_small_lines_all(v_lines), merge_small_lines_all(h_lines)]

    return tables


def merge_on_one_line_tables(tables, h_tol=5,
                             v_tol=5):
    for key, vals in tables.items():
        v_lines, h_lines = vals

        h_lines = list(map(lambda x: fix_coords_line(list(x)), h_lines))
        v_lines = list(map(lambda x: fix_coords_line(list(x)), v_lines))

        h_lines = merge_on_one_line(h_lines, mode='horizontal', tol=h_tol)
        v_lines = merge_on_one_line(v_lines, mode='vertical',
                                    tol=v_tol)
        tables[key] = [v_lines, h_lines]
    return tables


def merge_close_lines_tables(tables, h_tol=3,
                             v_tol=3):
    for key, vals in tables.items():
        v_lines, h_lines = vals
        v_lines += [(key[0], key[1], key[0], key[3]), (key[2], key[1], key[2], key[3])]
        h_lines += [(key[0], key[1], key[2], key[1]), (key[0], key[3], key[2], key[3])]

        h_lines = [list(map(int, i)) for i in merge_close_lines(h_lines, mode='horizontal', \
                                                                tol=h_tol)]
        v_lines = [list(map(int, i)) for i in merge_close_lines(v_lines, mode='vertical', \
                                                                tol=v_tol)]
        tables[key] = [v_lines, h_lines]
    return tables


def text_in_table(table_coords, parsed_text, c=0):
    in_table = []
    for i in parsed_text:
        if rectangle_inside_rectangle(table_coords, [i['x0'], i['y0'], i['x1'], i['y1']], c=c):
            in_table.append(i)
    return in_table


def get_horziontal_lines_inside(inner_segment, h_lines):
    new_h_lines = []
    for i in h_lines:
        if i[1] > inner_segment[1] and i[3] < inner_segment[3]:
            new_h_lines.append(i)
    return new_h_lines


def get_vertical_lines_inside_sld(inner_segment, v_lines, tol=0.9):
    new_v_lines = []
    for i in v_lines:
        start, end = i[:2], i[2:]

        if (is_point_inside_bbox(start, inner_segment) or is_point_inside_bbox(end, inner_segment)) \
                and get_line_length(i) / abs(inner_segment[1] - inner_segment[3]) > tol:
            new_v_lines.append([i[0], i[1], i[2], inner_segment[3]])
    return new_v_lines

def find_column_segment_sld(table_coords, h_lines, v_lines, tol=10, thr=0.3 #10 #TODO UPD 8
                            ):
    horizontal_border = (table_coords[0], table_coords[1], table_coords[2], table_coords[1])
    horizontal_border_len = abs(horizontal_border[0] - horizontal_border[2])
    h_lines = list(map(tuple, h_lines))
    if horizontal_border not in h_lines:
        h_lines += [horizontal_border]

    sorted_h_lines = sorted([tuple(list(i)) for i in h_lines], key=lambda x: x[1])
    sorted_h_lines = [i for i in sorted_h_lines \
                      if abs(i[0] - i[2]) / horizontal_border_len > 0.9]#525] #0.9
    
    v_lines_to_use = list(map(fix_coords_line, [i for i in v_lines if not (abs(i[0] - table_coords[0]) < tol \
                                                                           or abs(i[2] - table_coords[2]) < tol)]))
    candidates = []
    for i in range(len(sorted_h_lines) - 1):
        start_line = sorted_h_lines[i]
        end_line = sorted_h_lines[i + 1]
        upper_segment = [min(start_line[0], end_line[0]), start_line[1], min(start_line[2], end_line[2]),
                         end_line[1]]
        # check upper segment for lines there
        if (upper_segment[1] - upper_segment[3]) != 0:
            flag_thr = sum(
                [(end_line[1] - j[1]) / abs(upper_segment[1] - upper_segment[3]) > thr for j in v_lines_to_use])
            if flag_thr > min(1, len(v_lines_to_use) - 1):
                candidates.append(
                    [upper_segment, [min(start_line[0], end_line[0]), start_line[1], min(start_line[2], end_line[2]),
                                     start_line[3]], flag_thr])
    
    best_candidate = candidates[0]
    if len(candidates) > 1:
        for i in candidates[1:]:
            upper_segment, start_line, flag_thr = i
            if flag_thr - best_candidate[-1] >= 2 and best_candidate[-1] < 3:
                selected_best_candidate = upper_segment, start_line
            else:
                selected_best_candidate = best_candidate[:2]
    else:
        selected_best_candidate = best_candidate[:2]
    # TODO fix best cand
    L_table = table_coords[3] - table_coords[1]
    print(selected_best_candidate)
    if (selected_best_candidate[0][3] - table_coords[1])/L_table > .9:
        print('f')
        print(candidates[0])
        selected_best_candidate = candidates[0][:2]
        
    L_table = table_coords[3] - table_coords[1]
    L_cand = selected_best_candidate[0][3] - selected_best_candidate[0][1]
    if L_cand/L_table > .5:
        print('Not standart table column size')
        sorted_h_lines = sorted([tuple(list(i)) for i in h_lines], key=lambda x: x[1])
        sorted_h_lines = [i for i in sorted_h_lines \
                          if abs(i[0] - i[2]) / horizontal_border_len > 0.525]
        v_lines_to_use = list(map(fix_coords_line, [i for i in v_lines if not (abs(i[0] - table_coords[0]) < tol \
                                                                               or abs(i[2] - table_coords[2]) < tol)]))
        candidates = []
        for i in range(len(sorted_h_lines) - 1):
            start_line = sorted_h_lines[i]
            end_line = sorted_h_lines[i + 1]
            upper_segment = [min(start_line[0], end_line[0]), start_line[1], min(start_line[2], end_line[2]),
                             end_line[1]]
            if (upper_segment[1] - upper_segment[3]) != 0:
                flag_thr = sum(
                    [(end_line[1] - j[1]) / abs(upper_segment[1] - upper_segment[3]) > thr for j in v_lines_to_use])
                if flag_thr > min(1, len(v_lines_to_use) - 1):
                    candidates.append(
                        [upper_segment, [min(start_line[0], end_line[0]), start_line[1], min(start_line[2], end_line[2]),
                                         start_line[3]], flag_thr])
        best_candidate = candidates[0]
        if len(candidates) > 1:
            for i in candidates[1:]:
                upper_segment, start_line, flag_thr = i
                if flag_thr - best_candidate[-1] >= 2 and best_candidate[-1] < 3:
                    selected_best_candidate = upper_segment, start_line
                else:
                    selected_best_candidate = best_candidate[:2]
        else:
            selected_best_candidate = best_candidate[:2]
    return selected_best_candidate
# def find_column_segment_sld(table_coords, h_lines, v_lines, tol=10, thr=0.3
#                             ):
#     horizontal_border = (table_coords[0], table_coords[1], table_coords[2], table_coords[1])
#     horizontal_border_len = abs(horizontal_border[0] - horizontal_border[2])
#     h_lines = list(map(tuple, h_lines))
#     if horizontal_border not in h_lines:
#         h_lines += [horizontal_border]

#     sorted_h_lines = sorted([tuple(list(i)) for i in h_lines], key=lambda x: x[1])
#     sorted_h_lines = [i for i in sorted_h_lines \
#                       if abs(i[0] - i[2]) / horizontal_border_len > 0.9]

#     v_lines_to_use = list(map(fix_coords_line, [i for i in v_lines if not (abs(i[0] - table_coords[0]) < tol \
#                                                                            or abs(i[2] - table_coords[2]) < tol)]))
#     candidates = []
#     for i in range(len(sorted_h_lines) - 1):
#         start_line = sorted_h_lines[i]
#         end_line = sorted_h_lines[i + 1]
#         upper_segment = [min(start_line[0], end_line[0]), start_line[1], min(start_line[2], end_line[2]),
#                          end_line[1]]
#         # check upper segment for lines there
#         if (upper_segment[1] - upper_segment[3]) != 0:
#             flag_thr = sum(
#                 [(end_line[1] - j[1]) / abs(upper_segment[1] - upper_segment[3]) > thr for j in v_lines_to_use])
#             if flag_thr > min(1, len(v_lines_to_use) - 1):
#                 candidates.append(
#                     [upper_segment, [min(start_line[0], end_line[0]), start_line[1], min(start_line[2], end_line[2]),
#                                      start_line[3]], flag_thr])
#     best_candidate = candidates[0]
#     if len(candidates) > 1:
#         for i in candidates[1:]:
#             upper_segment, start_line, flag_thr = i
#             if flag_thr - best_candidate[-1] >= 2 and best_candidate[-1] < 3:
#                 return upper_segment, start_line
#             else:
#                 return best_candidate[:2]
#     else:
#         return best_candidate[:2]


def crop_bbox_by_message_size(inner_d, points, tol=1):
    to_merge_after = []
    final_res = []
    chars = inner_d['chars']
    for point in sorted(points, key=lambda x: x[0]):
        to_merge_before = []
        to_merge_after = []
        for i in chars:
            if i['x1'] - point[0] < tol:
                to_merge_before.append(i)
            else:
                to_merge_after.append(i)
        if to_merge_before:
            if to_merge_before[0]['message'] == ' ':
                to_merge_before.pop(0)
            if to_merge_before[-1]['message'] == ' ':
                to_merge_before.pop(-1)
            new_d = {'message': ''.join([i['message'] for i in to_merge_before]),
                     'x0': min(to_merge_before, key=lambda x: x['x0'])['x0'],
                     'y0': min(to_merge_before, key=lambda x: x['y0'])['y0'], 'x1': point[0],
                     'y1': max(to_merge_before, key=lambda x: x['y1'])['y1']}

            final_res.append({'spans': [new_d], 'x0': new_d['x0'], 'y0': new_d['y0'],
                              'x1': new_d['x1'], 'y1': new_d['y1']})

        chars = deepcopy(to_merge_after)

    if to_merge_after:
        if to_merge_after.__len__() > 1:
            if to_merge_after[0]['message'] == ' ':
                to_merge_after.pop(0)
            if to_merge_after[-1]['message'] == ' ':
                to_merge_after.pop(-1)
        new_d = {'message': ''.join([i['message'] for i in to_merge_after]),
                 'x0': min(to_merge_after, key=lambda x: x['x0'])['x0'],
                 'y0': min(to_merge_after, key=lambda x: x['y0'])['y0'],
                 'x1': max(to_merge_after, key=lambda x: x['x1'])['x1'],
                 'y1': max(to_merge_after, key=lambda x: x['y1'])['y1']}
        final_res.append({'spans': [new_d], 'x0': new_d['x0'], 'y0': new_d['y0'],
                          'x1': new_d['x1'], 'y1': new_d['y1']})
    return final_res


def fix_text_bbox_vlines(found_text, v_lines, tol=1):
    # for each text bbox - check if any of v_lines intersects it
    # if so - crop bbox by space
    new_text = []
    for d in found_text:
        to_save_normal = []
        for inner_d in d['spans']:
            bbox = [inner_d['x0'], inner_d['y0'], inner_d['x1'], inner_d['y1']]
            flag = False
            points_to_process = []
            for line in v_lines:
                if_in, point = v_h_line_rectangle_overlap(line, bbox)
                if if_in:
                    points_to_process.append(point)
                    flag = True

            if flag:
                new_text.extend(crop_bbox_by_message_size(inner_d, points_to_process, tol=tol))
            else:
                to_save_normal.append(inner_d)

        if to_save_normal:
            d_to_save = {}
            d_to_save['spans'] = to_save_normal
            d_to_save['x0'] = min(to_save_normal, key=lambda x: x['x0'])['x0']
            d_to_save['y0'] = min(to_save_normal, key=lambda x: x['y0'])['y0']
            d_to_save['x1'] = max(to_save_normal, key=lambda x: x['x1'])['x1']
            d_to_save['y1'] = max(to_save_normal, key=lambda x: x['y1'])['y1']
            new_text.append(d_to_save)

    return new_text


def get_columns(found_text_in_column, column_segment, v_lines, tol=1,
                c=2):
    sorted_v_lines = sorted(v_lines, key=lambda x: x[0])
    column_segment_v_lines = [[i[0], i[1], i[2], column_segment[3]] for i in sorted_v_lines]
    paired_v_column_lines = [column_segment_v_lines[i:i + 2] for i in range(len(column_segment_v_lines) - 1)]
    paired_v_lines = [sorted_v_lines[i:i + 2] for i in range(len(sorted_v_lines) - 1)]

    columns_bounding_boxes = [[i[0][0], i[0][1], i[1][2], i[0][3]] for i in paired_v_column_lines]
    columns = []
    for idx, bbox in enumerate(columns_bounding_boxes):
        found_text_in_bbox = text_in_table([bbox[0] - c, bbox[1] - c, bbox[2] + c, bbox[3] + c], found_text_in_column)

        if len(found_text_in_bbox) > 1:
            sorted_text = sorted(found_text_in_bbox, key=lambda x: x['y0'])
            single_letter_text = [i['spans'][0] for i in sorted_text \
                                  if len(i['spans']) == 1 and len(i['spans'][0]['message']) == 1]
            if len(single_letter_text) > 1:
                joined_single_letter = []
                for i in range(len(single_letter_text) - 1):
                    if abs(single_letter_text[i]['y1'] - single_letter_text[i + 1]['y0']) < tol:
                        joined_single_letter.append(single_letter_text[i]['message'])
                        if i + 1 == len(single_letter_text) - 1:
                            joined_single_letter.append(single_letter_text[i + 1]['message'])
                    else:
                        joined_single_letter.append(' ')

                joined_single_letter = ''.join(joined_single_letter)
            elif len(single_letter_text) == 1:
                joined_single_letter = single_letter_text[0]['message']
            else:
                joined_single_letter = ' '
            if len(single_letter_text) != len(sorted_text):
                not_single_letter_text = [i['spans'] \
                                          for i in sorted_text if
                                          len(i['spans']) != 1 or len(i['spans'][0]['message']) != 1]

                joined_single_letter += ' ' + ' '.join([j['message'] for i in not_single_letter_text for j in i])

            columns.append([joined_single_letter.strip(), paired_v_lines[idx]])
        elif len(found_text_in_bbox) == 1:

            columns.append(
                [' '.join([i['message'] for i in found_text_in_bbox[0]['spans']]).strip(), paired_v_lines[idx]])
        else:
            print('found nothing')
    if not columns:
        return [(None, i) for i in paired_v_lines]
    return columns


def find_double_tables_sld(columns):
    counter_columns = Counter([i[0] for i in columns])
    if len(counter_columns) > 1:
        duplicated_columns = [k for k, v in counter_columns.items() if v > 1]
        if not set([i[0] for i in columns]).difference(duplicated_columns):
            tables = [columns[:len(duplicated_columns)], columns[len(duplicated_columns):]]

        else:
            tables = [columns]

    else:
        tables = [columns]

    tables = [i for i in tables if i]
    return tables


def merge_h_lines_on_same_line(h_lines,
                               tol=3):
    on_same_line_mult = []
    for i in range(len(h_lines)):
        on_same_line = []
        for j in range(len(h_lines)):

            if i != j and abs(h_lines[i][1] - h_lines[j][1]) < tol:
                on_same_line.append(h_lines[j])

        on_same_line.append(h_lines[i])
        on_same_line_mult.append(on_same_line)

    new_h_lines = set()
    for inner_lines in on_same_line_mult:
        max_x = max([i[2] for i in inner_lines])
        min_x = min([i[0] for i in inner_lines])
        min_y = min([i[1] for i in inner_lines])
        max_y = min([i[3] for i in inner_lines])

        new_h_lines.add((min_x, min_y, max_x, max_y))

    return list(new_h_lines)


def check_line_x_ovelapping(line1, line2, tol=0.5):
    xmin_1, xmax_1 = line1[0], line1[2]
    xmin_2, xmax_2 = line2[0], line2[2]

    if xmin_1 < xmax_2 and xmax_1 >= xmax_2:

        xmin = max(xmin_1, xmin_2)
        xmax = min(xmax_1, xmax_2)
        if abs(xmin - xmax) / abs(xmin_2 - xmax_2) > tol:
            return True

    elif xmin_1 < xmax_2 and xmax_2 >= xmax_1 > xmin_2:
        xmin = max(xmin_1, xmin_2)
        if abs(xmin - xmax_1) / abs(xmin_2 - xmax_2) > tol:
            return True


def get_rows(columns, h_lines, found_text, c=2,
             char_delimetr=','):
    # logic: for each column we are making a specific row bboxes in which we are searching for text
    # even if the text isn't here - we add the empty value
    # at the end for each column we have text bboxes in it

    paired_h_column_lines = [h_lines[i:i + 2] for i in range(len(h_lines) - 1)]
    data = [[] for _ in columns]
    bboxes = []
    for idx, column in enumerate(columns):
        column_name, col_lines = column
        h_bboxes = [[col_lines[0][0] - c, line[0][1] - c, col_lines[1][0] + c, line[1][1] + c] for line in
                    paired_h_column_lines]
        bboxes.extend(h_bboxes)
        values_in_column = []
        for h_bbox in h_bboxes:
            found_in_bbox = text_in_table(h_bbox, found_text, 3)
            if found_in_bbox:
                found_in_bbox = sorted(found_in_bbox, key=lambda x: x['y0'])
                message = []
                for i in found_in_bbox:
                    message.append(' '.join([j['message'] for j in i['spans']]))
                message = char_delimetr.join(message)
                values_in_column.append(message)
            else:
                values_in_column.append(None)

        data[idx] = data[idx] + values_in_column

    data = pd.DataFrame(np.array(data).T, columns=[i[0] for i in columns])
    data = data.dropna(how='all')
    return data, bboxes


def merge_by_delimetrs(list_vals, delimetr_to_check):
    new_vals = []
    i = 0
    while i < len(list_vals):
        if not list_vals[i].endswith(delimetr_to_check):
            new_vals.append(list_vals[i])
            i += 1
        else:
            final_val = ''
            while list_vals[i].endswith(delimetr_to_check):
                final_val += list_vals[i]
                i += 1
            final_val += list_vals[i]
            new_vals.append(final_val)
            i += 1
    return new_vals


def post_process_table(inner_info,
                       delimetrs_to_check=',',
                       delimetr='|'):
    # create new columns
    already_seen = Counter()
    new_columns = []
    for i in inner_info.columns.tolist():
        if i in already_seen.keys():
            new_columns.append(f'{i}_{already_seen[i]}')
        else:
            new_columns.append(i)
        already_seen.update([i])
    # split inner info
    inner_info.columns = new_columns
    for i in inner_info.columns:
        inner_info[i] = inner_info[i].apply(lambda x: x.split(delimetr) if x else [x])

    # try to explode, if doesn't help -> try logic for delimetrs
    try:
        inner_info = inner_info.explode(inner_info.columns.tolist())
    except:
        d = []
        for i in inner_info.columns:
            d.append(inner_info[i].apply(len).values)
        d = np.array(d)
        modes = np.apply_along_axis(lambda x: stats.mode(x)[0], 0, d)[0]
        for i in range(d.shape[1]):
            if modes[i] == 1:
                indices_equal = np.where(d[:, i] == modes[i])[0]
                equal_vals = set(inner_info.loc[i, [i for c, i in enumerate(inner_info.columns) \
                                                    if c in indices_equal]].apply(lambda x: x[0]).values)
                if len(equal_vals) == 1 and list(equal_vals)[0] is None:
                    max_len = inner_info.loc[i].apply(len).max()
                    for idx in indices_equal:
                        inner_info.loc[:, inner_info.columns[idx]].loc[i] = \
                            np.repeat(inner_info.loc[i, inner_info.columns[idx]][0], max_len)
                else:
                    indices_to_check = np.where(d[:, i] != modes[i])[0]
                    for idx in indices_to_check:
                        inner_info.loc[:, inner_info.columns[idx]].loc[i] = \
                            [' '.join(inner_info.loc[i, inner_info.columns[idx]])]

            else:
                indices_to_check = np.where(d[:, i] != modes[i])[0]
                try:
                    for idx in indices_to_check:
                        to_check = inner_info.loc[i, inner_info.columns[idx]]
                        merged = merge_by_delimetrs(to_check, delimetrs_to_check)
                        if len(merged) != modes[i] and len(merged) % modes[i] == 0:
                            step = len(merged) // modes[i]
                            inner_info.loc[:, inner_info.columns[idx]].loc[i] = [merged[i:i + step] for i in
                                                                                 range(0, len(merged), step)]
                        elif len(merged) == modes[i]:
                            inner_info.loc[:, inner_info.columns[idx]].loc[i] = merged
                except:
                    pass

    # logic for None values
    to_check = []
    for c, i in enumerate(inner_info.iterrows()):
        idx, vals = i
        vals, columns = vals.values, list(vals.index)
        if not (isinstance(vals[0], list) or isinstance(vals[0], np.ndarray)):
            counter = Counter(vals)
            if None in counter.keys() and counter[None] == len(vals) - 1:
                col_idx = np.where(np.array(vals) != None)[0][0]
                col = columns[col_idx]
                to_check.append([c - 1, col])
    dropped_idx = []
    for i in to_check:
        idx, col = i
        if inner_info.loc[idx, col].endswith(delimetrs_to_check):
            inner_info.loc[:, col].loc[idx] = inner_info.loc[idx, col] + inner_info.loc[idx + 1, col]
            inner_info = inner_info.drop(idx + 1, axis=0)
            print(idx + 1)
            dropped_idx.append([idx + 1])

    # try explode
    try:
        inner_info = inner_info.explode(inner_info.columns.tolist())
    except:
        pass
    # try dropping duplicates
    try:
        dummy_col = []
        for i in inner_info.iterrows():
            dummy_col.append(''.join(list(map(str, i[1].values.tolist()))))
        inner_info['dummy_col'] = dummy_col
        
        df1 = inner_info.drop_duplicates('dummy_col')
        idx = inner_info.index.difference(df1.index)
        inner_info = inner_info.drop_duplicates('dummy_col')
        print(list(idx))
        dropped_idx.append(list(idx))
        inner_info = inner_info.drop(columns='dummy_col')
    except:
        pass

    return inner_info, dropped_idx


def drop_by_threshold(parsed_text, v_lines, h_lines,
                      q=0.5):
    y_length_thrs = np.quantile([i['y1'] - i['y0'] for i in parsed_text], q=q)
    x_length_thrs = np.quantile([i['x1'] - i['x0'] for i in parsed_text], q=q)

    return [i for i in v_lines if abs(i[3] - i[1]) > y_length_thrs], \
           [i for i in h_lines if abs(i[2] - i[0]) > x_length_thrs]



def mark_collapsed_values(x, delimiter):
    vals = [i for i in x.values if i]
    split_by_del = [len(str(i).split(delimiter)) for i in vals]
    return all([i > 1 for i in split_by_del]) and len(vals) > 1


def fix_collapsed_values(table, delimiter):
    columns = table.columns.tolist()
    table['marker'] = table.apply(lambda x: mark_collapsed_values(x, delimiter), axis=1)
    if any(table['marker'].unique()):
        new_values = []
        for idx, vals in table.iterrows():
            if vals['marker']:
                split_vals = [list(reversed(vals[col].split(delimiter))) \
                                  if vals[col] else vals[col] for col in columns]

                most_common_len = max(Counter([len(i) for i in split_vals if i]).items(), key=lambda x: x[1])[0]
                for c, val in enumerate(split_vals):
                    if val and len(val) > most_common_len:
                        split_vals[c] = [delimiter.join(val[:most_common_len]), delimiter.join(val[most_common_len:])]
                    elif not val:
                        split_vals[c] = [val for _ in range(most_common_len)]

                for c in range(most_common_len):
                    new_values.append([i[c] for i in split_vals])

            else:
                new_values.append([vals[col] for col in columns])
        return pd.DataFrame(new_values, columns=columns)

    else:
        return table.drop(columns=['marker'])


def find_contours(h_mask, v_mask):
    mask = h_mask + v_mask
    try:
        __, contours, __ = cv2.findContours(
            mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
    except ValueError:
        # for opencv backward compatibility
        contours, __ = cv2.findContours(
            mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    cont = []
    for c in contours:
        c_poly = cv2.approxPolyDP(c, 3, True)
        x, y, w, h = cv2.boundingRect(c_poly)
        cont.append((x, y, w, h))
    return cont


def get_contours_from_image(img, process_background=True):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    _, threshold = adaptive_threshold(gray, process_background)

    h_mask, h_lines = find_lines(threshold, direction="horizontal", iterations=0)
    v_mask, v_lines = find_lines(threshold, direction="vertical", iterations=0)

    contours = find_contours(h_mask, v_mask)
    return contours


def find_tables_and_lines(contours, img, original_w, original_h,
                          margin=6,
                          intersection_percentage=0.9,
                          size_lim=10,
                          remove_border=True):
    # crop logic, cropping boundary and finding the actual tables
    to_crop = []
    for i in contours:
        w, h = i[-2:]
        intersection = (w / original_w + h / original_h) / 2
        if intersection > intersection_percentage and intersection != 1 \
                and remove_border:
            to_crop.append((i, intersection))

    crop_bbox = []
    if to_crop:
        to_crop = max(to_crop, key=lambda x: x[1])[0]
        x, y, w, h = to_crop
        cropped_img = img[y + margin: y + h - margin, x + margin: x + w - margin]
        crop_bbox = (x + margin, y + margin, x + w - margin, y + h - margin)
        contours = get_contours_from_image(cropped_img)

    to_del = []
    for c, i in enumerate(contours):
        w, h = i[-2:]
        intersection = (w / original_w + h / original_h) / 2
        if intersection > intersection_percentage:
            to_del.append(c)

    contours = [i for c, i in enumerate(contours) if c not in to_del]

    # contours filtering
    to_del = set()
    for i in contours:
        x, y, w, h = i
        to_check1 = (x, y + h, x + w, y)
        for j in contours:
            x, y, w, h = j
            to_check2 = (x, y + h, x + w, y)
            if i != j and rectangle_inside_rectangle(to_check1, to_check2):
                to_del.add(j)

    for i in to_del:
        contours.remove(i)

    if not to_crop:
        cropped_img = img

    # finding tables
    tables = {}
    for c in contours:
        x, y, w, h = c

        if crop_bbox:
            shapes_to_scale = cropped_img.shape[1], cropped_img.shape[0]
            new_crop = cropped_img[y: y + h, x: x + w]
        else:
            shapes_to_scale = img.shape[1], img.shape[0]
            new_crop = img[y: y + h, x: x + w]

        crop_box_tmp = [x, y, x + w, y + h]

        if new_crop.shape[0] < size_lim or new_crop.shape[1] < size_lim:
            continue

        gray = cv2.cvtColor(new_crop, cv2.COLOR_BGR2GRAY)

        _, threshold = adaptive_threshold(gray, False)

        h_mask, h_lines = find_lines(threshold, direction="horizontal", iterations=0)
        v_mask, v_lines = find_lines(threshold, direction="vertical", iterations=0)
        roi = np.multiply(h_mask, v_mask)

        try:
            __, jc, __ = cv2.findContours(
                roi.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
        except ValueError:
            # for opencv backward compatibility
            jc, __ = cv2.findContours(
                roi.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
        if len(jc) <= 4:  # remove contours with less than 4 joints
            continue

        v_lines = [scale_crop(i, crop_box_tmp, shapes_to_scale) for i in v_lines]
        h_lines = [scale_crop(i, crop_box_tmp, shapes_to_scale) for i in h_lines]
        tables[(x, y + h, x + w, y)] = [v_lines, h_lines]

    if crop_bbox:
        scaled_tables = {}
        for key, values in tables.items():
            scaled_key = scale_crop(key, crop_bbox, (original_w, original_h))
            scaled_values = [[scale_crop(i, crop_bbox, (original_w, original_h)) for i in values[0]],
                             [scale_crop(i, crop_bbox, (original_w, original_h)) for i in values[1]]]
            scaled_tables[scaled_key] = scaled_values

        return scaled_tables
    else:
        scaled_tables = {}
        for key, values in tables.items():
            key = fix_coords(key)
            scaled_tables[key] = values
        return scaled_tables


def find_inner_segment(start_line, v_lines, h_lines, tol=2, margin=5):
    v_lines = list(map(tuple, v_lines))
    h_lines = list(map(tuple, h_lines))
    found_vertical_lines = [i for i in v_lines if abs(i[1] - start_line[1]) < tol]
    if found_vertical_lines:
        y_coords = set([i[-1] for i in found_vertical_lines])
        possible_segments = []
        to_remove = set()
        to_check_and_lines = []
        for y_coord in y_coords:
            to_check = [start_line[0], start_line[1], start_line[2], y_coord]
            h_lines_inside = get_horziontal_lines_inside(to_check, h_lines)
            to_check_and_lines.append([to_check, h_lines_inside])
            max_line = max(h_lines_inside, key=lambda x: x[3])
            len_max_line = max_line[2] - max_line[0]
            if len_max_line / (to_check[2] - to_check[0]) > 0.99 and max_line[3] - y_coord < 5:
                to_remove.add(max_line)

        for i in to_check_and_lines:
            to_check, h_lines_inside = i
            for j in to_remove:
                if j in h_lines_inside:
                    h_lines_inside.remove(j)

            possible_segments.append((to_check
                                      , np.mean(
                [abs((i[2] - i[0]) - (to_check[2] - to_check[0])) for i in h_lines_inside]), len(h_lines_inside)))

        mean_len = []
        for i in possible_segments:
            y_coord = i[0][-1]
            to_repeat = [j for j in found_vertical_lines if j[-1] == y_coord]
            mean_len.extend([i[-1] for _ in to_repeat])
        counter = [val for val in Counter(mean_len).values()]
        if len(counter) > 1 and len(set(counter)) == 1:
            segment = min(possible_segments, key=lambda x: x[1])[0]
            segment[3] += margin
            return segment
        else:
            mean_len = np.median(mean_len)
            possible_segments = [i for i in possible_segments if i[-1] >= mean_len]
            segment = min(possible_segments, key=lambda x: x[1])[0]
            segment[3] += margin
            return segment

    else:
        return find_inner_segment(sorted([i for i in h_lines if i[1] > start_line[1]],
                                         key=lambda x: x[1])[0], v_lines, h_lines)


def find_upper_segment(table_coords, h_lines, tol=2, c=5):
    horizontal_border_len = abs(table_coords[0] - table_coords[2])
    sorted_lines = sorted([tuple(list(i)) for i in h_lines], key=lambda x: x[1])
    sorted_lines = [i for i in sorted_lines \
                    if abs(i[0] - i[2]) / horizontal_border_len > 0.9]

    sorted_lines = [i for i in sorted_lines if not abs(table_coords[1] - i[1]) < tol]
    start_line = sorted_lines[0]
    end_line = None
    for i in sorted_lines[1:]:
        if not abs(i[1] - start_line[1]) < tol:
            end_line = i
            break

    if abs(table_coords[1] - start_line[1]) > 10:
        return [start_line[0], table_coords[1] - c, start_line[2], start_line[1] + c], \
               [start_line[0], start_line[1], start_line[2], start_line[1]]
    else:
        return [start_line[0], table_coords[1] - c, start_line[2], end_line[1] + c], \
               [start_line[0], end_line[1], start_line[2], end_line[1]]


def get_vertical_lines_inside_panelboard(inner_segment, v_lines, tol=5):
    new_v_lines = []
    for i in v_lines:
        if abs(i[1] - inner_segment[1]) < tol or abs(i[3] - inner_segment[3]) < tol:
            new_v_lines.append([i[0], i[1], i[2], inner_segment[3]])
    return new_v_lines


def get_column_segment_panelboard(inner_segment, h_lines, tol=2):
    h_lines = sorted([i for i in h_lines if abs(i[1] - inner_segment[1]) > tol],
                     key=lambda x: x[1])[0]
    return [inner_segment[0], inner_segment[1], inner_segment[2], h_lines[1]]


def find_double_tables_panelboard(columns):
    counter_columns = Counter([i[0] for i in columns])
    duplicated_columns = [k for k, v in counter_columns.items() if v > 1]
    if duplicated_columns:
        mask = np.isin(np.array([i[0] for i in columns]), np.array(duplicated_columns))
        tables = [[] for _ in range(max(counter_columns.values()))]
        idx = 0
        old_val = True
        for c, i in enumerate(mask):
            if i and not old_val:
                idx += 1

            if i:
                tables[idx].append(columns[c])

            old_val = i

    else:
        tables = [columns]

    return tables

def parse_inner_values(parsed_table, double_tables, h_lines_row_segment,
                       column_segment,
                       inner_segment,
                       text_in_inner_segment,
                       heuristic_config,
                       c=2.5,
                       char_delimetr=','):
    inner_parsed_tables = []
    pandas_tables = []
    for double_table in double_tables:
        inner_parsed_table = {}

        # finding inner table
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

        inner_info, h_bboxes = get_rows(double_table, h_lines_double_table_segment, text_in_inner_segment, c=c,
                                        char_delimetr=char_delimetr)

        inner_info = fix_collapsed_values(inner_info, char_delimetr)

        pandas_tables.append(inner_info)

        # finding column values by heuristics
        columns_to_use = []
        for new_column, conf in heuristic_config.items():
            found_col = find_table_columns_values(inner_info, column_pattern_func=conf['column_heuristic'],
                                                  value_pattern_func=conf['value_heuristic'],
                                                  inclusive_match=conf['inclusive_match'])
            if found_col:
                columns_to_use.append((found_col, new_column))
            else:
                inner_parsed_table[new_column] = None

        for column, to_save_col in columns_to_use:
            values = inner_info[column].values.tolist()
            if to_save_col == 'circuit':
                values = [i.split(char_delimetr) for i in values]

            inner_parsed_table[to_save_col] = values

        inner_parsed_tables.append(inner_parsed_table)

    # detect table type
    try:
        n_circuits = sum([sum([len(j) for j in i['circuit']]) for i in inner_parsed_tables])
        if n_circuits >= 42:
            parsed_table['panel_type'] = 'branch'
        else:
            parsed_table['panel_type'] = 'distribution'
    except:
        parsed_table['panel_type'] = None
    # logic of duplicate connections
    if parsed_table['panel_type'] == 'branch':
        for inner_parsed_table in inner_parsed_tables:
            duplicate_connections(inner_parsed_table, [i[1] for i in columns_to_use])

    # update parsed tables
    for inner_parsed_table in inner_parsed_tables:
        for k, v in inner_parsed_table.items():
            vals = parsed_table.get(k, [])

            if not vals:
                vals = []

            parsed_table[k] = vals + v if v else vals

    return parsed_table, pandas_tables
                           
def notes_removal(found_tables_dict, dict_list_of_table_rows, tol_ = 2):
    '''
    Removes notes or * parsed as rows. 
    Checks only two first columns (to reduce number of false positive) 
    If templates match, remove this and next rows. Double tables also removed by # of row.
    '''
    for table_id in found_tables_dict.keys():
        y_to_break = 99999999999
        
        logger.info('dict_list_of_table_rows')
        logger.info(dict_list_of_table_rows)
        logger.info(dict_list_of_table_rows.keys())
        logger.info('dict_list_of_table_rows')
        logger.info('table_id')
        logger.info(table_id)
        logger.info('table_id')
        if table_id in dict_list_of_table_rows.keys():
            list_of_table_rows = dict_list_of_table_rows[table_id]
            #row_to_break = -1
            for table_id_v2 in range(found_tables_dict[table_id]['tables'].__len__()):
                new_list = []
                if list(list_of_table_rows[table_id_v2].keys()).__len__() == found_tables_dict[table_id]['tables'][table_id_v2].__len__():
                    for row_id in range(found_tables_dict[table_id]['tables'][table_id_v2].__len__()):
                        first_col_key = list(found_tables_dict[table_id]['tables'][table_id_v2][row_id].keys())[0]
                        second_col_key = list(found_tables_dict[table_id]['tables'][table_id_v2][row_id].keys())[1]
                        list_words = found_tables_dict[table_id]['tables'][table_id_v2][row_id][first_col_key]
                        if list_words is None:
                            list_words = 'None'
                        list_words = ['None' if v is None else v for v in list_words]
                        list_words_a = [item for sublist in list_words for item in sublist if type(sublist) == list]
                        list_words_b = [i for i in list_words if type(i) != list]
                        list_words = list_words_a + list_words_b
                        list_words = ['None' if v is None else v for v in list_words]
                        str_words_f = ''.join(list_words).lower()
                        
                        list_words = found_tables_dict[table_id]['tables'][table_id_v2][row_id][second_col_key]
                        if list_words is None:
                            list_words = 'None'
                        list_words = ['None' if v is None else v for v in list_words]
                        list_words_a = [item for sublist in list_words for item in sublist if type(sublist) == list]
                        list_words_b = [i for i in list_words if type(i) != list]
                        list_words = list_words_a + list_words_b
                        list_words = ['None' if v is None else v for v in list_words]
                        str_words_s = ''.join(list_words).lower()
    
                        id_of_row = list(list_of_table_rows[table_id_v2].keys())[row_id]
                        coord_y = list_of_table_rows[table_id_v2][id_of_row] - tol_
                        if 'note' in str_words_f or 'NOTE'.lower() in str_words_f or '*' in str_words_f[:2]:
                            y_to_break = coord_y
                            break
                        elif 'note' in list_words or 'NOTE'.lower() in str_words_s or '*' in str_words_s[:2]:
                            y_to_break = coord_y
                            break
                        elif coord_y>=y_to_break:
                            break
                        else:
                            new_list.append(found_tables_dict[table_id]['tables'][table_id_v2][row_id])
                    found_tables_dict[table_id]['tables'][table_id_v2] = new_list
                else:
                    logger.info(f"Table {table_id}, {table_id_v2}, has len {found_tables_dict[table_id]['tables'][table_id_v2].__len__()}, while Y of rows has {list(list_of_table_rows[table_id_v2].keys()).__len__()} elements. Table skipped.")
        else:
            logger.info(f"Table {table_id} probably empty, not in {dict_list_of_table_rows.keys()}")
    return found_tables_dict

def to_json_preparation(found_tables_dict):
    '''
    Replaces type of np.ndarray with list. That allow us to use json.
    '''
    for key_ in found_tables_dict.keys():
        for el_id in range(found_tables_dict[key_]['tables'].__len__()):
            for el2_id in range(found_tables_dict[key_]['tables'][el_id].__len__()):
                for key_2 in found_tables_dict[key_]['tables'][el_id][el2_id].keys():
                    if isinstance(found_tables_dict[key_]['tables'][el_id][el2_id][key_2], (np.ndarray, list, tuple)):
                        found_tables_dict[key_]['tables'][el_id][el2_id][key_2] = list(found_tables_dict[key_]['tables'][el_id][el2_id][key_2])

    return found_tables_dict

def values_to_list(found_tables_dict):
    for key_ in found_tables_dict:
        for table in found_tables_dict[key_]['tables']:
            for inner_table in table:
                for k,v in inner_table.items():
                    if not isinstance(v, list):
                        inner_table[k] = [v]


def prepare_list_in_val(list_in_val):
    '''
    Change col name, so we correctly handle dubblicates 
    '''
    for i in range(list_in_val.__len__()):
        df_T = list_in_val[i][0]
        
        if not df_T.empty:
            if list(pd.unique(df_T.columns)).__len__() != list(df_T.columns).__len__():
                list_of_col_old = list(df_T.columns)
                list_of_col_new = []
                for ii in range(list_of_col_old.__len__()):
                    col_name = list_of_col_old[ii]
                    if col_name in list_of_col_new:
                        i_c = 0
                        while True:
                            i_c +=1
                            col_name_n = col_name+'_'+str(i_c)
                            if col_name_n not in list_of_col_new:
                                list_of_col_new.append(col_name_n)
                                break
                    else:
                        list_of_col_new.append(col_name)
                list_in_val[i][0].columns = list_of_col_new 
    return list_in_val



def prepare_list_of_table_rows(list_in_val, list_all_dropped_idx):
    '''
    Gather coords y for rows of table
    '''
    list_of_table_rows = []
    dict_of_rows_y = {}
    for table_num in range(list_in_val.__len__()):
        counter_ = 0
        dict_of_rows_y = {}
        for col_ in list_in_val[table_num][0].columns:
            for counter_, row_ in enumerate(list_in_val[table_num][0][col_]):
                if counter_ in dict_of_rows_y.keys():
                    dict_of_rows_y[counter_] = min(list_in_val[table_num][1][counter_][1], dict_of_rows_y[counter_])
                else:
                    dict_of_rows_y[counter_] = list_in_val[table_num][1][counter_][1]
                counter_+=1
        list_of_table_rows.append(dict_of_rows_y)
    for i in range(list_all_dropped_idx.__len__()):
        for ix_to_remove in list_all_dropped_idx[i]:
            for idx_ in ix_to_remove:
                del list_of_table_rows[i][idx_]
    return list_of_table_rows
