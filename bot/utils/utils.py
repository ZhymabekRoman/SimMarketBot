def is_digit(string: str) -> bool:
    try:
        float(string)
    except ValueError:
        return False
    else:
        return True

def merge_dicts(x, y):
    z = x.copy()
    z.update(y)
    return z
