class TaskState(object):
    PENDING = "PENDING"
    STARTED = "STARTED"
    PROGRESS = "PROGRESS"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"

    ALL = {
        PENDING,
        STARTED,
        PROGRESS,
        SUCCESS,
        FAILURE,
    }