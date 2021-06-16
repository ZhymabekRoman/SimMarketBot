import sqlalchemy as sa
from bot.models import BaseModel


class Refill(BaseModel):
    __tablename__ = 'refills'

    id = sa.Column(sa.Integer, unique=True, primary_key=True, index=True, autoincrement=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.user_id'))
    txn_id = sa.Column(sa.Integer, nullable=False)
    amount = sa.Column(sa.Float, nullable=False)
    data = sa.Column(sa.JSON, nullable=False)
    source = sa.Column(sa.Text, default="qiwi")

    payer = sa.orm.relationship("User", backref="refills", foreign_keys="User.user_id")
