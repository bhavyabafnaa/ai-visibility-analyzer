class CrawlerError(Exception):
    error_type = "crawler_error"
    stage = "fetch"


class UrlValidationError(CrawlerError):
    error_type = "invalid_url"
    stage = "validation"


class UnsafeUrlError(UrlValidationError):
    error_type = "unsafe_url"


class UrlResolutionError(UrlValidationError):
    error_type = "url_resolution_failed"


class OffDomainError(CrawlerError):
    error_type = "off_domain"
    stage = "validation"


class FetchError(CrawlerError):
    error_type = "fetch_failed"


class FetchTimeoutError(FetchError):
    error_type = "timeout"


class ResponseTooLargeError(FetchError):
    error_type = "response_too_large"


class RedirectLoopError(FetchError):
    error_type = "redirect_loop"


class TooManyRedirectsError(FetchError):
    error_type = "too_many_redirects"


class InvalidRedirectError(FetchError):
    error_type = "invalid_redirect"
