from bot.models.refills import Refill, RefillSource

def make_referrals_map(user, depth: int =10):
    for reffer_count in range(depth):
        if not user or not user.reffer:
            return

        yield user.reffer
        user = user.reffer


async def reward_referrals(user):
    refferal_map = make_referrals_map(user)
    for referral_amounnt in [0.25]:
        refferal = next(refferal_map, None)
        if not refferal:
            break
        Refill.create(user_id=refferal.user_id, source=RefillSource.REFERRAL, amount=referral_amounnt)
        refferal.update(balance=refferal.balance + referral_amounnt)
