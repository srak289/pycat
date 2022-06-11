#!/usr/bin/python3

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import *


class SQLDriver:
    def __init__(self):
        self.user = 'pycat'
        self.passwd = self.user
        # self.engine = create_engine(f'postgresql://{self.user}:{self.passwd}@localhost:5432/pycat')
        path = os.path.join(os.listdir(os.abspath(__file__)), 'dev.db')
        self.engine = create_engine(f'sqlite:///pycat.db')
        # Base.metadata.create_all(self.engine)
        self.sm = sessionmaker(bind=self.engine)
        self.sess = self.sm()

    def init(self):
        print("Creating all")
        Base.metadata.create_all(self.engine)

    def create(self, o):
        try:
            print(f'Creating {o}')
            self.sess.add(o)
            self.sess.commit()
        except Exception as e:
            print(e)

    def read(self, o):
        try:
            print(f'Searching for {o}')
            return self.sess.query(o)
        except Exception as e:
            print(e)

    def update(self, o, **kwargs):
        try:
            for k, v in kwargs:
                print(f'Updating {o}.{k} to be {v}')
                o.k = v
            self.sess.commit()
        except Exception as e:
            print(e)

    def delete(self, o):
        try:
            print(f'Deleting {o}')
            self.sess.delete(o)
            self.sess.commit()
        except Exception as e:
            print(e)


