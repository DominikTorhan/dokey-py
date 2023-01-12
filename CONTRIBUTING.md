### Environment (venv)
In Pycharm
1. Add New Interpreter
2. Go to Terminal in pycharm
3. Make sure environment is active - name of environment in parentheses (e.g. venv)
4. Execute: pip install -r pip_dependencies.txt

In vscode (linux wsl)
1. Install pip and venv
2. Create new environment: virtualenv -p python3 venv
3. Activate: source venv/bin/activate
4. Install dependencies: pip install -r pip_dependencies.txt

### Tests
Run tests with: 
```
python -m unittest
```
