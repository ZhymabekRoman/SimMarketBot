from icecream import ic


def readable_timedelta(duration):
    ic(duration)

    data = {}
    data['дней'], remaining = divmod(duration.total_seconds(), 86_400)
    data['часов'], remaining = divmod(remaining, 3_600)
    data['минут'], data['секунд'] = divmod(remaining, 60)

    time_parts = ((name, round(value)) for name, value in data.items())
    time_parts = [f'{value} {name[:-1] if value == 1 else name}' for name, value in time_parts if value > 0]
    if time_parts:
        return ' '.join(time_parts)
    else:
        return '0 секунд'
