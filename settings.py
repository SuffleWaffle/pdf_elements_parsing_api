import os
import functools
from src_utils.table_values_heuristics import find_panel_name, find_by_pattern_one_field, \
    upper_segment_volts_heuristic, upper_segment_mains_rating_heuristic, column_heuristic, \
    value_pattern, find_on_same_line

# ________________________________________________________________________________
# --- APPLICATION SETTINGS ---
PARALLEL_PROC_TIMEOUT: int = int(os.getenv("PARALLEL_PROC_TIMEOUT"))

AWS_ACCESS_KEY: str = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY: str = os.getenv("AWS_SECRET_KEY")
AWS_REGION_NAME: str = os.getenv("AWS_REGION_NAME")

# ________________________________________________________________________________
# --- ALGORITHM SETTINGS
SPECIAL_SYMBOLS_CONF = {'triangle': '3-wire',
                        'y': '4-wire'}
OCR_SETTING = dict(apply_ocr=True,
                   ocr_config='-l eng --oem 1 --psm 7 -c page_separator=',
                   to_add_border_pix=0,
                   dpi=500)

SLD_PARSING_CONF = {'find_lines_in_tables_svg': dict(tol=0),
                    'find_lines_in_tables_img': dict(line_scale=15,
                                                     iterations=1,
                                                     blocksize=15,
                                                     process_background=False),
                    'drop_by_threshold': dict(q=0.5),
                    'filter_bad_lines': dict(tol=0.1),
                    'merge_close_lines': dict(h_tol=6,
                                              v_tol=6),
                    'merge_on_one_line': dict(h_tol=6, v_tol=6),
                    'find_text_in_table': dict(c=5),
                    'drop_v_lines_by_threshold': dict(max_val=3),
                    'find_column_segment': dict(thr=0.475),
                    'get_vertical_lines_inside': dict(tol=0.3),
                    'fix_text_bbox_vlines': dict(tol=1),
                    'get_columns': dict(tol=2, c=10),
                    'merge_h_lines_on_same_line': dict(tol=5),
                    'get_rows': dict(c=2.5, char_delimetr='|'),
                    'post_process_table': dict(delimetrs_to_check=',',
                                               delimetr='|')
                    }

ELEMENTS_DETECTION_CONFIG = {'find_lines_in_tables_img': dict(line_scale=15,
                                                              iterations=0,
                                                              blocksize=15,
                                                              process_background=False),
                             'table_searching':
                                 dict(margin=6,  # margin used for cropping (as the boundary line can have big width)
                                      intersection_percentage=0.9,  # percentage of intersection of bounddary and image
                                      size_lim=10  # minimal size for table
                                      ),
                             'merge_close_lines': dict(h_tol=3,
                                              v_tol=3),
                             'upper_segment_searching': dict(tol=15,
                                                             c=10),
                             'text_on_same_line': dict(tol_x= 6, tol_y=3),
                             'text_in_table': dict(c=5),
                             'inner_segment_searching': dict(tol=5, margin=5),
                             'get_vertical_lines_inside_panelboard': dict(tol=10),
                             'get_column_segment': dict(tol=3),
                             'column_segment_v_lines': dict(percentage=0.05),
                             'fix_text_bbox_vlines': dict(tol=1),
                             'get_columns': dict(tol=1, c=4),
                             'merge_h_lines_on_same_line': dict(tol=5),
                             'parse_inner_values': dict(char_delimetr=';',
                                                    c=2.5)

                             }

find_on_same_line = functools.partial(find_on_same_line,
                                      **ELEMENTS_DETECTION_CONFIG['text_on_same_line'])


regex_pattern_amps = r'[1-9][0-9]+\sA'
regex_pattern_mains_raring = r'[1-9][0-9]+A'
regex_pattern_only_numbers = r'(^[0-9]$|^[1-9][0-9]+|--|^(\d+(;\d+)*)?$)'
regex_wire_size = r'("\sc$|--)'

UPPER_HEURISTIC_CONFIG = {'panel_name': {'func': find_panel_name,
                               'params': {'func_on_same_line' : find_on_same_line}},
                          'location':
                              {'func': find_by_pattern_one_field,
                               'params': {'pattern': ['location'],
                                          'func_on_same_line' : find_on_same_line},
                               },
                          'supply_from':
                              {'func': find_by_pattern_one_field,
                               'params': {'pattern': ['supply from', 'fed from',
                                                      'supply', 'from', 'fed'],
                                          'func_on_same_line' : find_on_same_line}
                               },
                          'mains_rating': {'func': upper_segment_mains_rating_heuristic,
                                           'params': {'regex_pattern': regex_pattern_mains_raring,
                                                      'func_on_same_line' : find_on_same_line}
                                           },
                          'volts': {'func': find_by_pattern_one_field,
                                    'params': {'pattern': ['distribution system', 'volt',
                                                           'system'],
                                               'pattern_function': functools.partial(upper_segment_volts_heuristic,
                                                                                     end_patterns=['wye', 'v']),
                                               'func_on_same_line' : find_on_same_line}
                                    }
                          }

INNER_HEURISTIC_CONFIG = {'circuit':
                              {'column_heuristic': \
                                   functools.partial(column_heuristic, patterns=['ckt', 'circuit', '#', 'circ',
                                                                                 '# ckt'],
                                                     inner_check=False),
                               'value_heuristic': functools.partial(value_pattern, regex=regex_pattern_only_numbers,
                                                                    all_rule=True),
                               'inclusive_match': True},

                          'wire_size':
                              {'column_heuristic': functools.partial(column_heuristic,
                                                                     patterns=['wire', 'conduit', 'feeder',
                                                                               'feeders'], inner_check=True),
                               'value_heuristic': None,
                               'inclusive_match': True},
                          'poles':
                              {'column_heuristic': functools.partial(column_heuristic, patterns=['p', 'poles', 'pole',
                                                                                                 '# of poles'],
                                                                     inner_check=True),
                               'value_heuristic': functools.partial(value_pattern, regex=regex_pattern_only_numbers,
                                                                    all_rule=True),
                               'inclusive_match': True},
                          'description':
                              {'column_heuristic': functools.partial(column_heuristic,
                                                                     patterns=['load served', 'description',
                                                                               'descriptions',
                                                                               'served', 'serves', 'load name'],
                                                                     inner_check=True),
                               'value_heuristic': None,
                               'inclusive_match': True},
                          'frame_size':
                              {'column_heuristic': functools.partial(column_heuristic, patterns=['frame', 'frame size'],
                                                                     inner_check=True),
                               'value_heuristic': None,
                               'inclusive_match': True},
                          'breaker':
                              {'column_heuristic': functools.partial(column_heuristic, patterns=['bkr', 'breaker',
                                                                                                 'trip', 'ocp size',
                                                                                                 'trip rating',
                                                                                                 'amps'],
                                                                     inner_check=True, anti_pattern=['conn. amps']),
                               'value_heuristic': functools.partial(value_pattern, regex=regex_pattern_amps,
                                                                    all_rule=False),
                               'inclusive_match': False}
                          }
