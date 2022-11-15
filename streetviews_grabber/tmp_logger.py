VERBOSE = False


def set_verbose(verbose_value):
    global VERBOSE
    VERBOSE = verbose_value


def verbose_info(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs)
    else:
        pass
