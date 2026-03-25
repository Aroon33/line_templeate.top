from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv('/var/www/line-platform/.env')

class Settings(BaseModel):
    app_name: str = os.getenv('APP_NAME', 'line-platform')
    app_env: str = os.getenv('APP_ENV', 'production')
    api_host: str = os.getenv('API_HOST', '127.0.0.1')
    api_port: int = int(os.getenv('API_PORT', '8101'))

    db_host: str = os.getenv('DB_HOST', '127.0.0.1')
    db_port: int = int(os.getenv('DB_PORT', '3306'))
    db_name: str = os.getenv('DB_NAME', 'line_platform')
    db_user: str = os.getenv('DB_USER', 'line_platform')
    db_password: str = os.getenv('DB_PASSWORD', 'CHANGE_ME')

    @property
    def db_url(self) -> str:
        return f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"

settings = Settings()
