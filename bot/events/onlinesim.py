from bot.models.onlinesim import Onlinesim  # , OnlinesimStatus
# from bot import sim_service
# from icecream import ic


async def onlinesim_msg_code_event(event):
    tzid, msg, status = event

    _msg = {"msg": msg}
    # ic("Onlinesim event", event)

    task_info = Onlinesim.where(tzid=tzid).first()
    task_info.update(status=status, msg=_msg)


# async def onlinesim_close_operation(tzid):
#     await sim_service.close(tzid)
