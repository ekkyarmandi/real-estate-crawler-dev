import re


def json_finder(func):
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)

        # evaluate json as python dictionary
        attrs = re.findall(r'\w+=".*?"', result)
        for old_cl in attrs:
            new_cl = re.sub(r'"', "'", old_cl)
            result = result.replace(old_cl, new_cl)

        attrs = re.findall(r'href=".*?"', result)
        for old_cl in attrs:
            new_cl = re.sub(r'"', "'", old_cl)
            result = result.replace(old_cl, new_cl)

        result = result.replace("null", "None")
        result = result.replace("false", "False")
        result = result.replace("true", "True")
        result = eval(result)

        return result

    return wrapper
