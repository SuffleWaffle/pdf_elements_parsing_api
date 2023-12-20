from copy import deepcopy
import re
import numpy as np
from src_utils.geometry_utils import euclidean_dist


def check_for_same_line(obj1, obj2, tol_x=6, tol_y=3):
    # check on x distance
    if obj1['x1'] < obj2['x0']:
        distance = obj2['x0'] - obj1['x1']
    elif obj1['x0'] > obj2['x1']:
        distance = obj1['x0'] - obj2['x1']
    else:
        return False

    if distance > tol_x:
        return False
    # check on y distance

    ### check if the box2 is under or above the box1
    if obj1['y0'] > obj2['y1'] or obj1['y1'] < obj2['y0']:
        return False

    ### check if the box2 is inside box1
    if obj1['y0'] < obj2['y0'] and obj1['y1'] > obj2['y1']:
        return True

    if obj1['y0'] < obj2['y0'] and abs(obj1['y1'] - obj2['y1']) < tol_y:
        return True

    if abs(obj1['y0'] - obj2['y0']) < tol_y and obj1['y1'] > obj2['y1']:
        return True

    ### check if on some tolerance
    if abs(obj1['y0'] - obj2['y0']) < tol_y and abs(obj1['y1'] - obj2['y1']) < tol_y:
        return True

    return False


def find_on_same_line(text_in_upper_segment,
                      tol_x=6, tol_y=3):
    result = []
    for i in range(0, len(text_in_upper_segment)):
        for j in range(i, len(text_in_upper_segment)):
            if i != j:
                check1 = text_in_upper_segment[i]['spans']
                check2 = text_in_upper_segment[j]['spans']
                if len(check1) == len(check2) == 1:
                    if check_for_same_line(check1[0], check2[0], tol_x=tol_x, tol_y=tol_y):
                        result.append((check1[0], check2[0]))
    return result

def duplicate_connections(parsed_table, columns):
    additional_field = deepcopy(parsed_table['circuit'])
    flag = False
    for idx in range(len(parsed_table['description'])):
        value = parsed_table['description'][idx]
        if (value=='--' or value is None) and flag:
            for col in columns:
                if parsed_table[col][idx]=='--' or parsed_table[col][idx] is None:
                    parsed_table[col][idx] = parsed_table[col][idx -1]

            additional_field[idx] = additional_field[idx -1]

        elif value and value!='--':
            flag = True

    parsed_table['connected_circuits'] = additional_field


def find_table_columns_values(table, column_pattern_func, value_pattern_func,
                              inclusive_match=True):
    possible_columns = column_pattern_func(table.columns)
    possible_columns = list(set(possible_columns))
    if inclusive_match:
        if value_pattern_func:
            appropriate_cols = []
            for col in possible_columns:
                if value_pattern_func(table[col].values):
                    appropriate_cols.append(col)
            if appropriate_cols:
                return appropriate_cols[0]
            else:
                return None
        else:
            if possible_columns:
                return possible_columns[0]
            else:
                return None
    else:
        if not possible_columns:
            appropriate_cols = []
            for col in table.columns:
                if value_pattern_func(table[col].values):
                    appropriate_cols.append(col)
            if appropriate_cols:
                return appropriate_cols[0]
            else:
                return None
        else:
            return possible_columns[0]


def column_heuristic(columns, patterns, inner_check=False, anti_pattern=None):
    chosen_cols = []
    for col in columns:
        for pat in patterns:
            rule = False
            if inner_check:
                rule = any([i.strip() == pat for i in col.lower().split()])
            if col.lower() == pat or rule:
                chosen_cols.append(col)
                break
    if anti_pattern:
        to_del = set()
        for i in anti_pattern:
            for c, j in enumerate(chosen_cols):
                if j.lower() == i.lower():
                    to_del.add(c)
        return [i for c, i in enumerate(chosen_cols) if c not in to_del]
    return chosen_cols


def value_pattern(values, regex, all_rule=True):
    overall_check = []
    if len(values.shape) < 2:
        values = np.expand_dims(values, axis=1)
    for idx in range(values.shape[1]):
        tmp = [str(i) for i in values[:, idx] if i]
        to_check = [True if re.findall(regex, i) else False for i in tmp]
        overall_check.append(all(to_check) if all_rule else any(to_check))
    return any(overall_check)


def find_by_pattern_inner(message, pattern):
    rule = []
    for pat in pattern:
        rule.append(all([inner_pat in message for inner_pat in pat.split()]))
    return rule


def find_by_pattern(text, pattern: list, to_lower=True):
    to_use = []
    for i in text:
        rule = []
        for j in i['spans']:
            message = j['message'].lower() if to_lower else j['message']
            rule.extend(find_by_pattern_inner(message, pattern))
        if any(rule):
            to_use.append(i)

    if not to_use:
        for i in text:
            message = ''.join([j['message'].lower() if to_lower else j['message'] for j in i['spans']])
            if any(find_by_pattern_inner(message, pattern)):
                to_use.append(i)
    return to_use


def find_by_pattern_one_field(key_coords, found_text_in_table, pattern='location',
                              pattern_function=None,
                              func_on_same_line=find_on_same_line):
    if not isinstance(pattern, (list, tuple, np.ndarray)):
        pattern = [pattern]

    top_border_center = ((key_coords[0] + key_coords[2]) / 2, key_coords[1])

    to_check = find_by_pattern(found_text_in_table, pattern)

    result = []
    for i in to_check:
        center = [(i['x0'] + i['x1']) / 2, (i['y0'] + i['y1']) / 2]
        result.append((i, euclidean_dist((center[0], center[1]), \
                                         (top_border_center[0], top_border_center[1]))))
    if result:
        found_result = min(result, key=lambda x: x[1])[0]
        if len(found_result['spans']) > 1:

            message = ''.join([i['message'] for i in found_result['spans']]).split(':')[-1]

            found_result = [i for i in message.split() \
                            if not any(find_by_pattern_inner(i.lower(), pattern)) \
                            and i.strip()]

            return ' '.join(found_result)
        else:
            span = deepcopy(found_result['spans'][0])
            message = span['message'].split(':')[-1].strip()
            if not message:
                on_the_same_line = func_on_same_line(found_text_in_table)
                if on_the_same_line:
                    found_result = [i for i in on_the_same_line if any([j == span for j in i])]
                    if found_result:
                        result = [i for i in found_result[0] if i != span][0]
                        return result
                return None

            else:
                span['message'] = message

            return span

    elif pattern_function:
        result = [i for i in found_text_in_table if \
                  any([pattern_function(j['message']) for j in i['spans']])]

        if result:
            result = result[0]
            if len(result['spans']) > 1:
                result = [i for i in result['spans'] \
                          if pattern_function(i['message'].lower()) and i['message'].strip()]
                return result[0]
            else:
                span = deepcopy(result['spans'][0])
                message = span['message'].split(':')[-1].strip()

                if not message:
                    on_the_same_line = func_on_same_line(found_text_in_table)
                    if on_the_same_line:
                        found_result = [i for i in on_the_same_line if any([j == span for j in i])]
                        if found_result:
                            return [i for i in found_result[0] if i != span][0]
                else:
                    span['message'] = message

                return span
        else:
            return None


    else:
        return None


def upper_segment_mains_rating_heuristic(found_text_in_table, regex_pattern,
                                         func_on_same_line=find_on_same_line):
    # find mains type
    found_mains_type = find_by_pattern(found_text_in_table, ['mains type',
                                                             'main type'])
    pattern_to_find = None

    if found_mains_type:
        # check if mains type already has information about Ampere
        result = [i for i in found_mains_type \
                  if any([bool(re.findall(regex_pattern, \
                                          j['message'].replace(' ', ''))) for j in i['spans']])]
        if result:

            result = result[0]
            if len(result['spans']) > 1:
                result = [i for i in result['spans'] \
                          if bool(re.findall(regex_pattern, \
                                             i['message'].replace(' ', '')))]
                return result[0]
            else:
                span = deepcopy(result['spans'][0])
                message = span['message'].split(':')[-1].strip()
                if not message:
                    on_the_same_line = func_on_same_line(found_text_in_table)
                    if on_the_same_line:
                        found_result = [i for i in on_the_same_line if any([j == span for j in i])]
                        if found_result:
                            result = [i for i in found_result[0] if i != span][0]
                            return result
                    return None

                else:
                    span['message'] = message
                return span

        # if not -> we take the mains type

        found_mains_type = found_mains_type[0]
        if len(found_mains_type['spans']) > 1:
            found_mains_type = ''.join(i['message'] for i in found_mains_type['spans']).split(':')[-1].strip()
        else:
            found_mains_type = found_mains_type['spans'][0]['message']. \
                split(':')[-1].strip()
        pattern_to_find = [found_mains_type]

    # if there is a found mains type - check for it
    if pattern_to_find:
        found_by_pattern = find_by_pattern(found_text_in_table, pattern_to_find,
                                           to_lower=False)
        messages = [''.join([j['message'] for j in i['spans']]) for i in found_by_pattern]
        for i in messages:
            if all(find_by_pattern_inner(i.split(':')[0], pattern_to_find)) and \
                    not all(find_by_pattern_inner(i.split(':')[1], pattern_to_find)):
                found_by_pattern = i.split(':')[1].replace(' ', '')
                if bool(re.findall(regex_pattern, found_by_pattern)):
                    return found_by_pattern

    # in other case let's find by Amperes pattern
    for i in found_text_in_table:
        for j in i['spans']:
            split_by_coma = j['message'].split(',')
            bool_results = []
            for split in split_by_coma:
                to_check = split.strip().replace(' ', '')
                bool_results.append(bool(re.findall(regex_pattern, to_check)))
            if any(bool_results):
                return j


def upper_segment_volts_heuristic(message, end_patterns):
    message = message.lower()
    split_by_coma = message.split(',')
    bool_results = []
    for i in split_by_coma:
        bool_results.append(any([i.endswith(pat) for pat in end_patterns]) and '/' in i)
    return any(bool_results)


def find_panel_name(key_coords, found_text_in_table,
                    func_on_same_line=find_on_same_line):
    top_border_center = ((key_coords[0] + key_coords[2]) / 2, key_coords[1])
    max_size = max([max([j['size'] for j in i['spans']]) for i in found_text_in_table], key=lambda x: x)
    to_check = [i for i in found_text_in_table if any([abs(j['size'] - max_size) < 1 for j in i['spans']])]
    result = []
    for i in to_check:
        center = [(i['x0'] + i['x1']) / 2, (i['y0'] + i['y1']) / 2]
        result.append((i, euclidean_dist((center[0], center[1]), \
                                         (top_border_center[0], top_border_center[1]))))

    res = min(result, key=lambda x: x[1])[0]
    if len(res['spans']) == 1:
        to_return = deepcopy(res['spans'][0])
        message = to_return['message'].split(':')[-1].strip()
        if not message:
            on_the_same_line = func_on_same_line(to_check)
            if on_the_same_line:
                found_result = [i for i in on_the_same_line if any([j == to_return for j in i])]
                if found_result:
                    return [i for i in found_result[0] if i != to_return][0]
        else:
            to_return['message'] = message
            return to_return
    else:
        return [i for i in res['spans'] if not i['message'].endswith(':') and i['message'].strip()]


def parse_upper_values(key_coords, found_text_in_table, config):
    upper_values = {}
    for column_name, value in config.items():
        func = value['func']
        varnames = func.__code__.co_varnames[:func.__code__.co_argcount]
        params = {}
        for i in varnames:
            if i in locals().keys():
                params[i] = locals()[i]
        params.update(value['params'])
        upper_values[column_name] = value['func'](**params)

    for k, v in upper_values.items():
        if isinstance(v, dict):
            upper_values[k] = v['message'].strip()
        elif isinstance(v, list):
            upper_values[k] = ''.join([i['message'] for i in v]).strip()
    return upper_values