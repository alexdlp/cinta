"""Errors carry an exit code and, where possible, the command that fixes them."""


class CintaError(Exception):
    def __init__(self, message: str, exit_code: int = 1, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code
        self.hint = hint


# Exit codes reported by cintarec (DESIGN.md 4.5), mapped to explanations the
# user can act on. The raw codes are never shown.
RECORDER_EXIT_CODES = {
    10: (
        "macOS has not granted screen recording permission.",
        "System Settings > Privacy & Security > Screen & System Audio Recording.\n"
        "Enable your terminal application, then restart it completely.",
    ),
    11: (
        "macOS has not granted microphone permission.",
        "System Settings > Privacy & Security > Microphone, then enable your terminal.",
    ),
    12: ("The display or microphone you asked for does not exist.", "Run: cinta devices"),
    13: ("Could not write the output file.", None),
    20: ("The recorder rejected its arguments. This is a bug in cinta.", None),
}
