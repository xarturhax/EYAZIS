"""Ожидаемые ошибки, которые интерфейс может показать пользователю."""


class ApplicationError(Exception):
    """Базовая ошибка приложения; не используется для ошибок программирования."""


class ValidationError(ApplicationError):
    """Некорректный пользовательский ввод или предметные данные."""


class NotFoundError(ApplicationError):
    """Запрашиваемый документ отсутствует."""


class StorageError(ApplicationError):
    """Ошибка открытия, чтения или записи хранилища."""


class FetchError(ApplicationError):
    """Не удалось получить поддерживаемый интернет-документ."""


class ExportError(ApplicationError):
    """Не удалось сохранить отчёт."""
