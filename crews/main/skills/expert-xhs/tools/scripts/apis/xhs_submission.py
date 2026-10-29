"""Track the single note POST separately from preflight and media uploads."""
from uuid import uuid4


def new_submission():
    return {'attempt_id': uuid4().hex, 'stage': 'preflight',
            'submission_attempted': False, 'media_uploaded': False}


class NoteSubmissionError(RuntimeError):
    def __init__(self, code, message, progress):
        super().__init__(message)
        self.code = code
        self.progress = dict(progress)
