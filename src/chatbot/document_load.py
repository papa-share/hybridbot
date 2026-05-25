from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentLoadResult:
    text: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error
