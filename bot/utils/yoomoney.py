from requests.models import PreparedRequest


def generate_yoomoney_payment_form_link(receiver, refill_msg, label, price):
    yoomoney_payment_link = "https://yoomoney.ru/quickpay/confirm.xml"
    yoomoney_payment_link_parameters = {"receiver": receiver, "quickpay-form": "shop", "targets": refill_msg, "paymentType": "SB", "sum": price, "label": label}
    yoomoney_payment_link_prepared = PreparedRequest()
    yoomoney_payment_link_prepared.prepare_url(yoomoney_payment_link, yoomoney_payment_link_parameters)
    return yoomoney_payment_link_prepared.url
