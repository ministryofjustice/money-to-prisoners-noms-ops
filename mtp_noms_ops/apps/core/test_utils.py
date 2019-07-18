import responses


def activate_strict_responses(func):
    """
    Instantiates a new responses.RequestsMock and makes it available in the test
    via a 'strict_responses' kwarg.
    This is the preferred approach as the requests.activate decorator doesn't raise
    any assertion error if a url was registered but not accessed.

    Usage:

    @activate_strict_responses
    def test_something(self, strict_responses):
        strict_responses.add(...)
        ...
    """
    def wrapper(*args, **kwargs):
        with responses.RequestsMock() as strict_responses:
            kwargs['strict_responses'] = strict_responses
            func(*args, **kwargs)
    return wrapper
