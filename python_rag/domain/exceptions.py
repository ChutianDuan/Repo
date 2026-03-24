class AppException(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super(AppException, self).__init__(message)