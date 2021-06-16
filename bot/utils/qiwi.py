from bot.utils import utils
from urllib.parse import urlencode


def split_float(amount: float):
    params = {}
    if type(amount) == float:
        params['amountInteger'] = str(amount).split('.')[0]
        params['amountFraction'] = str(amount).split('.')[1]
    else:
        params['amount'] = amount
    return params


def sources_list(sources, params, name='sources'):
    """
    Adds defined list of sources to params
    Parameters
    ----------
    sources : list
        Payment sources
    params : dict
        Default params
    name : str
        name for list
    Returns
    -------
    dict
        params with sources
    """
    if isinstance(sources, list):
        for source in sources:
            params['{0}[{1}]'.format(name, sources.index(source))] = source
    else:
        raise TypeError('You should use list Type for sources')
    return params


def generate_qiwi_payment_form_link(pid: str, account: str, amount: str, comment: str, currency: int = 643, blocked: list = None, account_type=None):
    """
    Создание автозаполненной платежной формы. Код адаптирован из pyqiwi: https://github.com/mostm/pyqiwi/blob/master/pyqiwi/__init__.py
    Parameters
    ----------
    pid : str
        ID провайдера
    account : str
        Счет получателя
    amount : float
        Сумма платежа
    comment : str
        Комментарий
    currency : int
        Валюта в стандарте ISO 4217
    blocked : list[str]
        Список из значений "заблокированных" (не изменяемых на веб-странице) полей внутри ссылки.
        Варианты: sum, account, comment
    account_type : int or str
        Отвечает за вариант перевода при pid=99999 (вариация перевода на Qiwi Кошелек)
        Варианты: 0 (перевод по номеру телефона, phone), 1 (перевод по "никнейму", nickname),
         str (сами впишите вариант по соответствию с Qiwi API)
    Note
    ----
    Комментарий применяется только при переводе на Qiwi Кошелек по номеру (pid==99)
    Сумма платежа не может быть более 99999 из-за ограничений на один платеж.
    Тип счета для перевода на Qiwi Кошелек (pid=99999) с возможностью ввода "nickname" выбирается в account_type
    Returns
    -------
    str
        Ссылка
    Raises
    ------
    ValueError
        amount>99999 или список blocked неверен
    """
    url = "https://qiwi.com/payment/form/{0}".format(pid)
    params = {"currency": currency}
    params = utils.merge_dicts(params, split_float(amount))
    if amount > 99999:
        raise ValueError('amount не может превышать 99999 из-за ограничений на один платеж внутри QIWI')
    if pid == "99" and comment:
        params["extra['comment']"] = comment
    if account:
        params["extra['account']"] = account
    if type(blocked) == list and len(blocked) > 0:
        for entry in blocked:
            if entry not in ['sum', 'account', 'comment']:
                raise ValueError('Заблокированное значение может быть только sum, account или comment')
        params = sources_list(blocked, params, name='blocked')
    if pid == "99999" and account_type == 0:
        params["extra['accountType']"] = 'phone'
    elif pid == "99999" and account_type == 1:
        params["extra['accountType']"] = 'nickname'
    elif pid == "99999" and type(account_type) == str:
        params["extra['accountType']"] = account_type

    encoded_params = urlencode(params)

    return url + '?' + encoded_params
