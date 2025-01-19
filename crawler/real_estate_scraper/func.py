from supabase import create_client
from decouple import config
from io import BytesIO
from PIL import Image
import requests
import re
import os

url = config("SUPABASE_URL")
key = config("SUPABASE_KEY")
supabase = create_client(url, key)


def clean_double_quotes(text):
    try:
        target_text = re.search(r'"desc":\s*(.*?)\s*,"\w+"', text).group(1)
        target_text = target_text.strip('"')
        target_text = target_text.replace("“", '"')
        target_text = target_text.replace("”", '"')
        new_text = re.sub(r'"', r"'", target_text)
        text = text.replace(target_text, new_text)
    except Exception as e:
        print("Error cleaning double quotes::clean_double_quotes::", e)
    return text


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


def change_value_to_set(field: str, value: str) -> str:
    if field != "price":
        return f"'{value}'"
    return value


def supabase_uploader(url: str, path: str) -> str:
    try:
        # get dir name
        dir_name = re.search(r"(?P<name>\w+)\.(com|rs)", url).group("name")
        # download image
        filename = url.split("/")[-1].split("?")[0].split("#")[0]
        ext = filename.split(".")[-1]
        filepath = f"{dir_name}/{path}.{ext}"
        response = requests.get(url)
        if response.status_code != 200:
            raise ValueError(f"Failed to download image from {url}")
        # save image locally
        image = Image.open(BytesIO(response.content))
        image.save(filename)
        # upload image to supabase storage
        supabase.storage.from_("images").upload(filepath, filename)
        # get public url
        source_url = supabase.storage.from_("images").get_public_url(filepath)
        return source_url.split("?")[0]
    except Exception as e:
        raise ValueError(f"Failed to upload image to Supabase: {e}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)


def str_to_price(value: str) -> float:
    if isinstance(value, str) and re.search(r"\d", value):
        value = re.sub(r"\s+", "", value)
        value = re.search(r"[0-9.,]+", value).group(0)
        value = value.replace(".", "")
        value = value.replace(",", ".")
        value = float(value)
    return value
