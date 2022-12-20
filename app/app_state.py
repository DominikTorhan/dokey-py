from app.keys import Keys
from app.modificators import Modificators

OFF: int = 0
NORMAL: int = 1
INSERT: int = 2

class AppState:
    def __init__(self):
        self.modificators: Modificators = Modificators()
