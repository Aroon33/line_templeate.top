from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

app = FastAPI(title='line-platform-ui')
BASE = '/var/www/line-template.top/ui'
templates = Jinja2Templates(directory=os.path.join(BASE, 'templates'))
app.mount('/static', StaticFiles(directory=os.path.join(BASE, 'static')), name='static')

@app.get('/', response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})

@app.get('/health')
def health():
    return {'status': 'ok', 'app': 'line-platform-ui'}
