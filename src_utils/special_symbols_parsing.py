from src_utils.geometry_utils import get_line_length, check_line_type


def find_triangles(horizontal_lines, vertical_lines, inclined_lines):
    # we start off with base which is a horizontal line
    triangles = []
    for base_line in horizontal_lines:
        base_start, base_end = base_line[:2], base_line[2:]
        # find the first line relevant to lines
        tmp_lines = {}
        for line_1 in vertical_lines + inclined_lines:
            line_1_start, line_1_end = line_1[:2], line_1[2:]
            if line_1_start == base_start:
                tmp = tmp_lines.get('to_the_left', [])
                tmp.append(line_1)
                tmp_lines['to_the_left'] = tmp
            elif line_1_end == base_start:
                tmp = tmp_lines.get('to_the_left', [])
                tmp.append([*line_1_end, *line_1_start])
                tmp_lines['to_the_left'] = tmp
            elif line_1_start == base_end:
                tmp = tmp_lines.get('to_the_right', [])
                tmp.append(line_1)
                tmp_lines['to_the_right'] = tmp
            elif line_1_end == base_end:
                tmp = tmp_lines.get('to_the_right', [])
                tmp.append([*line_1_end, *line_1_start])
                tmp_lines['to_the_right'] = tmp
        # filtering of candidates
        if len(tmp_lines.get('to_the_left', [])) == 1 and len(tmp_lines.get('to_the_right', [])) == 1:
            to_the_left = tmp_lines['to_the_left'][0]
            to_the_right = tmp_lines['to_the_right'][0]
            # types of lines should be different
            type_to_the_left = check_line_type(to_the_left)
            type_to_the_right = check_line_type(to_the_right)
            if (type_to_the_left == 'vertical' and type_to_the_right != type_to_the_left) \
                    or type_to_the_left == 'other':
                # lines should end at one point
                if tuple(to_the_left[2:]) == tuple(to_the_right[2:]):
                    triangles.append([base_line, to_the_left, to_the_right])
    return triangles


def find_Y(vertical_lines, inclined_lines):
    # vertical line is a base here
    y_lines = []
    for base_line in vertical_lines:
        base_start, base_end = base_line[:2], base_line[2:]
        # find the lines relevant to base
        tmp_lines = []
        for line_1 in inclined_lines:
            line_1_start, line_1_end = line_1[:2], line_1[2:]
            if line_1_start == base_start:
                tmp_lines.append(line_1)
            elif line_1_end == base_start:
                tmp_lines.append([*line_1_end, *line_1_start])

        # filter lines
        if len(tmp_lines) == 2:
            line1, line2 = tmp_lines
            if (not ((line1[2] < base_line[0] and line2[2] < base_line[0]) or \
                     (line1[2] > base_line[0] and line2[2] > base_line[0]))) and \
                    (not (line1[3] > base_line[1] or line2[3] > base_line[1])):
                base_line_length = get_line_length(base_line)
                line1_length = get_line_length(line1)
                line2_length = get_line_length(line2)
                if line1_length / base_line_length > 0.5 and line2_length / base_line_length > 0.5:
                    y_lines.append([base_line, *tmp_lines])
    return y_lines


def find_closest_text(parsed_text, objects):
    to_check = []
    for text in parsed_text:
        text_bbox = [text['x0'], text['y0'], text['x1'], text['y1']]
        for obj in objects:
            obj_bbox = obj['bbox']
            if text_bbox[0] <= obj_bbox[0] and abs(text_bbox[2] - obj_bbox[0]) < 3 and \
                    abs(text_bbox[1] - obj_bbox[1]) < 3:
                to_check.append([text, obj])
    return to_check


def substitute_symbol_text(all_text, to_check, symbol='▲'):
    for ent in to_check:
        text, obj = ent
        try:
            all_text.remove(text)
        except Exception as e:
            print(e)

        obj_bbox = obj['bbox']
        x_diff = abs(obj_bbox[2] - obj_bbox[0])

        new_char = {'message': symbol,
                    'x0': text['spans'][-1]['chars'][-1]['x1'],
                    'y0': text['spans'][-1]['chars'][-1]['y0'],
                    'x1': text['spans'][-1]['chars'][-1]['x1'] + x_diff,
                    'y1': text['spans'][-1]['chars'][-1]['y1']}
        text['x1'] = obj_bbox[2]
        text['spans'][-1]['x1'] = text['spans'][-1]['x1'] + x_diff
        text['spans'][-1]['chars'] = text['spans'][-1]['chars'] + [new_char]
        text['spans'][-1]['message'] = text['spans'][-1]['message'] + symbol

        all_text.append(text)

    return all_text
