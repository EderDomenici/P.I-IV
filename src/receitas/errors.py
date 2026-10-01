from receitas.models import ValidationReport


class DataImportError(Exception):
    def __init__(self, file_name: str, reason: str, action: str) -> None:
        self.file_name = file_name
        self.reason = reason
        self.action = action
        super().__init__(reason)

    @property
    def user_message(self) -> str:
        return (
            f"Não foi possível importar {self.file_name}: {self.reason}. "
            f"Ação necessária: {self.action}."
        )


class ValidationBlockedError(Exception):
    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        super().__init__("Dataset validation blocked publication")
