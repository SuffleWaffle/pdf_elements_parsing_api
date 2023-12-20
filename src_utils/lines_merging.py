import networkx as nx
from itertools import chain
from src_utils.geometry_utils import is_part_of_other, check_line_type

def merge_small_lines(lines, line_type):
    # define graph
    G = nx.Graph()
    for i, line in enumerate(lines):
        G.add_node(i)
    # add edges
    for i in range(len(lines)):
        start1, end1 = lines[i][:2], lines[i][2:]
        for j in range(i + 1, len(lines)):
            start2, end2 = lines[j][:2], lines[j][2:]
            if start1 == end2 or start2 == end1 or \
                    is_part_of_other(lines[i], lines[j], line_type) \
                    or is_part_of_other(lines[j], lines[i], line_type) \
                    or start1 == start2 or end1 == end2:
                G.add_edge(i, j)
    # get big_lines
    big_lines = []
    to_del = []
    for component in nx.connected_components(G):
        big_line = []
        to_del_tmp = []
        for node in component:
            big_line.append(lines[node])
            to_del_tmp.append(node)

        if len(big_line) > 1:
            to_del.extend(to_del_tmp)
            big_lines.append(big_line)

    # get minimal and maximal point for each line
    actual_lines = []
    for line in big_lines:
        all_points = list(chain(*[[i[:2], i[2:]] for i in line]))
        max_point = max(all_points)
        min_point = min(all_points)
        actual_lines.append([*min_point, *max_point])

    return [i for c, i in enumerate(lines) if c not in to_del] + actual_lines


def merge_small_lines_all(lines):
    v_lines = [i for i in lines if check_line_type(i) == 'vertical']
    o_lines = [i for i in lines if check_line_type(i) == 'other']
    h_lines = [i for i in lines if check_line_type(i) == 'horizontal']
    return merge_small_lines(h_lines, line_type='horizontal') \
           + merge_small_lines(v_lines, line_type='vertical') + o_lines




