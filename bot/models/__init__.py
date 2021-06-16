from sqlalchemy_mixins import AllFeaturesMixin, TimestampsMixin
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class BaseModel(Base, AllFeaturesMixin, TimestampsMixin):
    __abstract__ = True
