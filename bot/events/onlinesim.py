from bot.models.onlinesim import Onlinesim, OnlinesimStatus



async def onlinesim_msg_code_event(event):
    tzid, msg, status = event

    task_info = Onlinesim.where(tzid=tzid).first()
    task_info.update(status=status)
