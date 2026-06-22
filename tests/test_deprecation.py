"""Tests for the @deprecated and @version_introduced decorators."""
import warnings

import pytest

from easycord.decorators import deprecated, version_introduced


# ---------------------------------------------------------------------------
# @deprecated
# ---------------------------------------------------------------------------

def test_deprecated_emits_deprecation_warning():
    @deprecated("5.0.0")
    def old_func():
        return "value"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        old_func()

    assert len(caught) == 1
    assert issubclass(caught[0].category, DeprecationWarning)


def test_deprecated_warning_contains_version():
    @deprecated("5.0.0")
    def old_func():
        pass

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        old_func()

    assert "5.0.0" in str(caught[0].message)


def test_deprecated_warning_contains_replacement():
    @deprecated("5.0.0", replacement="new_func()")
    def old_func():
        pass

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        old_func()

    assert "new_func()" in str(caught[0].message)


def test_deprecated_warning_contains_reason():
    @deprecated("5.0.0", reason="This approach is unsafe.")
    def old_func():
        pass

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        old_func()

    assert "This approach is unsafe." in str(caught[0].message)


def test_deprecated_wrapped_function_still_returns_value():
    @deprecated("5.0.0")
    def add(a, b):
        return a + b

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        result = add(2, 3)

    assert result == 5


def test_deprecated_wrapped_function_passes_args_and_kwargs():
    @deprecated("5.0.0")
    def greet(name, *, greeting="Hello"):
        return f"{greeting}, {name}!"

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        result = greet("world", greeting="Hi")

    assert result == "Hi, world!"


def test_deprecated_preserves_function_name_and_docstring():
    @deprecated("5.0.0")
    def my_old_function():
        """Old docstring."""
        pass

    assert my_old_function.__name__ == "my_old_function"
    assert my_old_function.__doc__ == "Old docstring."


def test_deprecated_sets_dunder_deprecated_attribute():
    @deprecated("5.0.0")
    def old_func():
        pass

    assert old_func.__deprecated__ == "5.0.0"


def test_deprecated_sets_dunder_replacement_attribute():
    @deprecated("5.0.0", replacement="new_func()")
    def old_func():
        pass

    assert old_func.__replacement__ == "new_func()"


def test_deprecated_replacement_none_when_omitted():
    @deprecated("5.0.0")
    def old_func():
        pass

    assert old_func.__replacement__ is None


def test_deprecated_warning_message_no_replacement_or_reason():
    @deprecated("5.0.0")
    def old_func():
        pass

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        old_func()

    msg = str(caught[0].message)
    assert "deprecated since v5.0.0" in msg
    # replacement phrase must not appear if none given
    assert "instead" not in msg


def test_deprecated_can_be_applied_to_method():
    class MyClass:
        @deprecated("5.0.0", replacement="MyClass.new_method()")
        def old_method(self):
            return 42

    obj = MyClass()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = obj.old_method()

    assert result == 42
    assert issubclass(caught[0].category, DeprecationWarning)
    assert "MyClass.old_method" in str(caught[0].message)


# ---------------------------------------------------------------------------
# @version_introduced
# ---------------------------------------------------------------------------

def test_version_introduced_sets_attribute():
    @version_introduced("5.49.0")
    def new_func():
        pass

    assert new_func.__version_introduced__ == "5.49.0"


def test_version_introduced_does_not_alter_return_value():
    @version_introduced("5.49.0")
    def compute():
        return 99

    assert compute() == 99


def test_version_introduced_does_not_emit_warnings():
    @version_introduced("5.49.0")
    def new_func():
        pass

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        new_func()

    assert len(caught) == 0


def test_version_introduced_preserves_name_and_doc():
    @version_introduced("5.49.0")
    def documented():
        """A documented function."""
        pass

    assert documented.__name__ == "documented"
    assert documented.__doc__ == "A documented function."


def test_version_introduced_can_stack_with_deprecated():
    """Stacking both decorators should not break either."""
    @version_introduced("5.0.0")
    @deprecated("5.50.0", replacement="better_func()")
    def transitional():
        return "result"

    assert transitional.__version_introduced__ == "5.0.0"
    assert transitional.__deprecated__ == "5.50.0"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = transitional()

    assert result == "result"
    assert issubclass(caught[0].category, DeprecationWarning)


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------

def test_deprecated_importable_from_easycord():
    from easycord import deprecated as dep
    assert callable(dep)


def test_version_introduced_importable_from_easycord():
    from easycord import version_introduced as vi
    assert callable(vi)
