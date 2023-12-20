import numpy as np
from copy import deepcopy
from collections import Counter

def euclidean_dist(point1, point2):
    x0, y0 = point1
    x1, y1 = point2

    return np.sqrt((x0 - x1) ** 2 + (y0 - y1) ** 2)

def fix_coords(tags_coords):
    x1, y1, x2, y2 = tags_coords
    xmin = min(x1, x2)
    xmax = max(x1, x2)
    ymin = min(y1, y2)
    ymax = max(y1, y2)
    return xmin, ymin, xmax, ymax


def fix_coords_line(line):
    start, end = line[:2], line[2:]
    line = sorted([start, end])
    line = [*line[0], *line[1]]
    return tuple(line)


def get_line_length(line):
    x1, y1, x2, y2 = line
    return np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


def check_line_type(line):
    if line[1] == line[3] and not line[0] == line[2]:
        return 'horizontal'
    elif line[0] == line[2] and not line[1] == line[3]:
        return 'vertical'
    else:
        return 'other'


def scale(line, original_size, new_size):
    x0, y0, x1, y1 = line

    Rx = new_size[0] / original_size[0]
    Ry = new_size[1] / original_size[1]

    return np.round(x0 * Rx), np.round(y0 * Ry), np.round(x1 * Rx), np.round(y1 * Ry)

def make_bigger_bbox(coords, to_add=1):
    new_coords = []
    for i in coords:
        tmp = []
        if i[0] - to_add > 0:
            tmp.append(i[0] - to_add)
        else:
            tmp.append(i[0])

        if i[1] - to_add > 0:
            tmp.append(i[1] - to_add)
        else:
            tmp.append(i[1])

        tmp.append(i[2] + to_add)
        tmp.append(i[3] + to_add)
        new_coords.append(tmp)
    return new_coords

def create_bbox(objects_lines):
    bboxes = []
    for i in objects_lines:
        to_comp_x = []
        to_comp_y = []
        for j in i:
            start, end = j[:2], j[2:]
            to_comp_x.extend([start[0], end[0]])
            to_comp_y.extend([start[1], end[1]])

        min_x, max_x = min(to_comp_x), max(to_comp_x)
        min_y, max_y = min(to_comp_y), max(to_comp_y)
        bboxes.append({'bbox': [min_x, min_y, max_x, max_y],
                       'lines': i})
    return bboxes


def is_point_inside_bbox(point, bbox, tol=0):
    x, y = point
    xmin, ymin, xmax, ymax = bbox
    return xmin - tol <= x <= xmax + tol and ymin - tol <= y <= ymax + tol


def scale_crop(rect_to_scale, cropping_bb, original_sizes):
    x0, y0, x1, y1 = rect_to_scale
    original_w, original_h = original_sizes

    min_y = min(y0, y1)
    max_y = max(y0, y1)
    min_x = min(x0, x1)
    max_x = max(x0, x1)

    min_x = min_x + cropping_bb[0]
    min_y = min_y + cropping_bb[1]

    max_x = max_x + (original_w - cropping_bb[2]) + (cropping_bb[0] - (original_w - cropping_bb[2]))
    max_y = max_y + (original_h - cropping_bb[3]) + (cropping_bb[1] - (original_h - cropping_bb[3]))

    return min_x, min_y, max_x, max_y


def is_part_of_other(line1, line2, type_line):
    if type_line == 'vertical':
        if line1[0] == line2[0]:
            if line2[3] >= line1[1] >= line2[1] or (line1[1] <= line2[1] and line1[3] >= line2[3]):
                return True
            else:
                return False
        else:
            return False
    elif type_line == 'horizontal':
        if line1[1] == line2[1]:
            if line2[2] >= line1[0] >= line2[0] or (line1[0] <= line2[0] and line1[2] >= line2[2]):
                return True
            else:
                return False
        else:
            return False


def line_v_h_intersection(line1, line2):
    check_vh_intersect = lambda x, y: x[0] <= y[0] <= x[2] and y[1] <= x[1] <= y[3]
    if line1 == line2:
        return True, [line1[0], line1[1]]

    elif line1[1] == line1[3] and line2[0] == line2[2]:
        return check_vh_intersect(line1, line2), [line2[0], line1[1]]

    elif line1[0] == line1[2] and line2[1] == line2[3]:
        return check_vh_intersect(line2, line1), [line1[0], line2[1]]

    return False, None


def merge_close_lines(lines, mode='horizontal', tol=5):
    points = sorted([((i[0] + i[2]) / 2, (i[1] + i[3]) / 2, i) for i in lines], \
                    reverse=False if mode == 'horizontal' else True,
                    key=lambda x: (x[0], x[1]))
    ret = []
    for a in points:
        if not ret:
            ret.append(a)
        else:
            temp = ret[-1]
            if all(np.isclose(np.array(temp[:2]), np.array(a[:2]), atol=tol)):
                temp = list(temp)
                temp[-1] = (np.array(temp[-1]) + np.array(a[-1])) / 2.0
                ret[-1] = temp
            else:
                ret.append(a)

    return [i[-1] for i in ret]


def merge_on_one_line(lines, mode='horizontal', tol=5):
    on_one_line = {}
    for line in lines:
        if mode == 'horizontal':
            key = line[1]
            tmp = on_one_line.get(key, [])
            tmp.append(line)
            on_one_line[key] = tmp
        elif mode == 'vertical':
            key = line[0]
            tmp = on_one_line.get(key, [])
            tmp.append(line)
            on_one_line[key] = tmp

    new_lines = []
    for lines_list in on_one_line.values():
        new_lines.extend(proximity_merge(lines_list, mode, tol))
    return new_lines


def proximity_merge(lines, mode, tol):
    new_lines = deepcopy(lines)
    merged = set()
    if mode == 'horizontal':
        lines = sorted(lines, key=lambda x: x[0])
    elif mode == 'vertical':
        lines = sorted(lines, key=lambda x: x[1])

    first_line = lines[0]
    lines = lines[1:]
    while len(lines):
        second_line = lines[0]
        if mode == 'horizontal' and (second_line[0] - first_line[2]) < tol:
            new_line = (min(first_line[0], second_line[0]), min(first_line[1], second_line[1]),
                        max(first_line[2], second_line[2]), max(first_line[3], second_line[3]))
            merged.update([first_line, second_line])
            first_line = new_line
            new_lines.append(new_line)
        elif mode == 'vertical' and (second_line[1] - first_line[3]) < tol:
            new_line = (min(first_line[0], second_line[0]), min(first_line[1], second_line[1]),
                        max(first_line[2], second_line[2]), max(first_line[3], second_line[3]))
            merged.update([first_line, second_line])
            first_line = new_line
            new_lines.append(new_line)
        else:
            first_line = second_line

        lines.pop(0)

    lines_to_leave = [k for k, v in Counter(new_lines).items() if v > 1]
    new_lines = list(set(new_lines).difference(merged)) + lines_to_leave
    return new_lines


def rectangle_inside_rectangle(table_coords1, table_coords2, c=0):
    min_x1 = min(table_coords1[0], table_coords1[2]) - c
    max_x1 = max(table_coords1[0], table_coords1[2]) + c
    min_y1 = min(table_coords1[1], table_coords1[3]) - c
    max_y1 = max(table_coords1[1], table_coords1[3]) + c

    min_x2 = min(table_coords2[0], table_coords2[2])
    max_x2 = max(table_coords2[0], table_coords2[2])
    min_y2 = min(table_coords2[1], table_coords2[3])
    max_y2 = max(table_coords2[1], table_coords2[3])

    return min_x2 > min_x1 and min_y2 > min_y1 and max_x2 < max_x1 and max_y2 < max_y1

def v_h_line_rectangle_overlap(line, bbox):
    bbox_lines = [
        [bbox[0], bbox[1], bbox[0], bbox[3]],
        [bbox[2], bbox[1], bbox[2], bbox[3]],
        [bbox[0], bbox[1], bbox[2], bbox[1]],
        [bbox[0], bbox[3], bbox[2], bbox[3]]
    ]
    intersections = [line_v_h_intersection(line, i) for i in bbox_lines]
    point = [i[1] for i in intersections if i[0]]
    intersect = any([i[0] for i in intersections])

    if point:
        return intersect, point[0]
    else:
        return intersect, None



