### Environment
DoKey has no dependencies — there is nothing to install and no venv to create.
Any Python 3 install can run it straight from the repository root:
```
python main.py
```

Only `app/` and `tests/` import on Linux/WSL; everything under `os_level/` is
Windows-only.

### Tests
Run tests with: 
```
python -m unittest
```
