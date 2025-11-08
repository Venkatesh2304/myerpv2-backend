from sqlalchemy import create_engine
from myerpv2 import settings

engine = create_engine(
    f"postgresql+psycopg2://{settings.DATABASES['default']['USER']}:{settings.DATABASES['default']['PASSWORD']}@"
    f"{settings.DATABASES['default']['HOST']}:{settings.DATABASES['default']['PORT']}/"
    f"{settings.DATABASES['default']['NAME']}"
, echo = False)
