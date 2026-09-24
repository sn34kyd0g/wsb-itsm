# ai-generated: 100% - Claude Code (spec-kit implement) wrote this from research.md R3
"""The one error type the API raises; main.py turns it into {"error": {"code", "message"}}."""


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
