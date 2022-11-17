class Logger:
    _instance = None
    _verbose = None

    def __new__(cls, verbose=None):
        if not cls._instance:
            cls._instance = super(Logger, cls).__new__(cls)
        if verbose is not None:
            cls._instance._verbose = verbose
        return cls._instance

    def verbose(self, *args, **kwargs):
        if self._verbose:
            print(*args, **kwargs)

    def info(self, *args, **kwargs):
        print(*args, **kwargs)


