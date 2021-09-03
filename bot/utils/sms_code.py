import re


def mark_sms_code(msg_list):
    for msg in msg_list:
        finded_numbered_words = re.findall(r"\d\S+\d\b", msg)
        for numbered_word in finded_numbered_words:
            msg = re.sub(r'\b%s\b' % numbered_word, f'<code>{numbered_word}</code>', msg)
        yield msg
