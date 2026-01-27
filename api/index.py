import os
import sys

# Añade el directorio actual al path para poder importar módulos locales
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importa tu instancia de 'app' desde main.py
# Asumo que en api/main.py tienes algo como: app = FastAPI(...)
from main import app 

# Vercel busca una variable 'app' o 'handler' automáticamente
