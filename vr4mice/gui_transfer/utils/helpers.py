"""
    Script contains helpers for GUI:
    simple logical or arithmetic operations
"""


def get_max(list):
    """
    Get max length based on length of all elements in the list
    """
    max = -1
    for l in list:
        if len(l) > max:
            max = len(l)
    return max


def get_idx(i, j, max, step):
    """
    Deduce idx according to step, used for rows distribution
    """
    if j < max:
        j += step
    else:
        i += 1
        j = 0
    return i, j


def get_size(options):  # gui fields
    """
    Get size of Gui's element/form (combobox etc)
    """
    min_len = 100
    max_len = 300
    k = 10

    len_elm = get_max(options) * k

    if len_elm < min_len:
        len_elm = min_len
    elif len_elm > max_len:
        len_elm = max_len

    return len_elm


def get_min_len():
    return 100


def get_step():
    return 2


def get_pattern(key, format):
    """
    Assemble all formats together to Dialog-specific input
    """
    if isinstance(format, list):
        pattern = ""
        for f in format:
            pattern += f + " "
    else:
        pattern = format

    return pattern
