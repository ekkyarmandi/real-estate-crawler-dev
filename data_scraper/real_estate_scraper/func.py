import re


def raw_json_formatter(text):
    # attrs = re.findall(r'\w+=".*?"', text)
    # for old_cl in attrs:
    #     new_cl = re.sub(r'"', "'", old_cl)
    #     text = text.replace(old_cl, new_cl)
    text = text.replace("null", "None")
    text = text.replace("false", "False")
    text = text.replace("true", "True")
    text = text.replace(",", ",\n\t")
    text = text.replace('\\"', '"')
    return text
