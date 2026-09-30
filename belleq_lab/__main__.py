import logging
import uvicorn
from .config import load_settings
from .app import create_app
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s')
s = load_settings()
uvicorn.run(create_app(s), host=s.bind, port=s.port, workers=1)
