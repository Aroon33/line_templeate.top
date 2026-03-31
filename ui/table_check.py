from sqlalchemy import inspect
from app.database import engine
insp = inspect(engine)
print(insp.get_table_names())
