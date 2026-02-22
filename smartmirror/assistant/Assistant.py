class Assistant:
    def __init__(self, with_speech = True, with_RAG = False, with_DB = False, keywords = ["ABDOU"]):
        self.with_speech = with_speech
        self.with_RAG = with_RAG
        self.with_DB = with_DB
        self.keywords = keywords