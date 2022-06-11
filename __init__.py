from pycat.models import *
from pycat.connection import SSHConnection, CiscoConnection
from pycat.driver import SQLDriver
from pycat.dbpass import dbpass

dbuser = 'pycat'
dbhost = 'localhost'
dbname = 'pycat'
dburl = f'postgresql://{dbuser}:{dbpass}@{dbhost}:5431/{dbname}'

engine = create_engine(dburl)
sm = sessionmaker(bind=engine)
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

session = sm()
