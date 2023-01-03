# Release Notes

## Latest changes

## 0.3.0.0

Fix errors on cleanup in Python 3.9+ when calling async methods

Fix some more use cases of the module

The `wrap` function now automatically creates sync variants of async context managers

Fixed an issue where `get_event_loop` would error if it was called only during finalizers

## 0.2.0.2

Support python 3.11

## 0.2.0.1

Fix type hints

## 0.2.0.0

Added docs, proper typing everywhere, fixed hanging issues in some contexts as well as the `get_event_loop` function

## 0.1.0.0

Initial release
