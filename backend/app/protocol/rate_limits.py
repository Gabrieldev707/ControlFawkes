from app.input.pointer import PointerRateLimiter


MAX_MESSAGES_PER_SECOND = 120
MAX_CONNECTIONS = 32
MAX_NAVIGATION_PER_SECOND = 20
MAX_NON_REPEATABLE_PER_SECOND = 3


def message_limiter() -> PointerRateLimiter:
    return PointerRateLimiter(max_updates=MAX_MESSAGES_PER_SECOND)


def navigation_limiter() -> PointerRateLimiter:
    return PointerRateLimiter(max_updates=MAX_NAVIGATION_PER_SECOND)


def non_repeatable_navigation_limiter() -> PointerRateLimiter:
    return PointerRateLimiter(max_updates=MAX_NON_REPEATABLE_PER_SECOND)
