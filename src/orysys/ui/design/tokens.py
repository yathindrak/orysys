from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DesignTokens:
    background: str = "#F7F8FA"
    foreground: str = "#172033"
    primary: str = "#3157D5"
    muted: str = "#667085"
    border: str = "#D8DEE9"
    success: str = "#178447"
    warning: str = "#B54708"
    error: str = "#B42318"
    radius: str = "0.75rem"


TOKENS = DesignTokens()
