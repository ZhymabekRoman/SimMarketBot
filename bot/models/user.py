import sqlalchemy as sa
from bot.models import BaseModel


class User(BaseModel):
    __tablename__ = 'users'

    user_id = sa.Column(sa.Integer, unique=True, primary_key=True, index=True)
    balance = sa.Column(sa.Float, default=0.00, nullable=False)
    reffer_id = sa.Column(sa.Integer, sa.ForeignKey('users.user_id'), default=None)

    reffer = sa.orm.relationship("User", backref="refferals", remote_side=user_id)
