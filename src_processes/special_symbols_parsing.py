from src_utils.special_symbols_parsing import find_Y, find_triangles, \
    find_closest_text, substitute_symbol_text
from src_utils.geometry_utils import scale, fix_coords_line, get_line_length, \
    check_line_type, create_bbox


def parse_special_symbols(parsed_text, lines,
                          pdf_width, pdf_height,
                          svg_width, svg_height,
                          triangle_symbol,
                          y_symbol):
    # working with lines
    lines = [list(map(int, scale(i,
                                 (svg_width, svg_height),
                                 (pdf_width, pdf_height)))) for i in lines]
    lines = list(map(fix_coords_line, lines))
    lines = list(set([tuple(i) for i in lines]))
    lines = [i for i in lines if get_line_length(i) != 1]
    horizontal_lines = [line for line in lines if check_line_type(line) == 'horizontal']
    vertical_lines = [line for line in lines if check_line_type(line) == 'vertical']
    inclined_lines = [line for line in lines if check_line_type(line) == 'other']
    # find triangles
    triangles = find_triangles(horizontal_lines, vertical_lines, inclined_lines)
    triangles = create_bbox(triangles)
    triangles = find_closest_text(parsed_text, triangles)
    parsed_text = substitute_symbol_text(parsed_text, triangles, triangle_symbol)
    # find Ys
    Ys = find_Y(vertical_lines, inclined_lines)
    Ys = create_bbox(Ys)
    Ys = find_closest_text(parsed_text, Ys)
    parsed_text = substitute_symbol_text(parsed_text, Ys, y_symbol)
    return parsed_text
