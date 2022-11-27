class Context(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


    def __init__(self, debug, download, plot):
        self.debug = debug
        self.download = download
        self.plot = plot
