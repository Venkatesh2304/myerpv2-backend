from abc import ABC, abstractmethod
import os
import re
from io import BytesIO
import json
from logging import Handler
from typing import Generic, TypeVar
from urllib.parse import urljoin, urlparse
import requests
import curlify
import logging
from requests.models import Response
from uuid import uuid1
import toml
from bs4 import BeautifulSoup
import shutil
from pymongo import MongoClient
from .std import get_mongo
import urllib3
from app.company_models import UserSession
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

## DB FIELDS
DB_COLLECTION_NAME = "demo"
DB_NAME = "test_users"
DB_USER_FIELD = "username"
DB_COOKIE_FIELD = "_cookies"


## MongoDB setup
client = MongoClient("mongodb+srv://venkatesh2004:venkatesh2004@cluster0.9x1ccpv.mongodb.net/?retryWrites=true&w=majority")
# client = get_mongo()
collection = client[DB_COLLECTION_NAME]
user_db = collection[DB_NAME]

## DB SETUP
class UserDB:
    def __init__(self, db, username, class_key):
        self.db = db
        self.user = username
        self.class_key = class_key
        self.user_data = None

    def get_user(self):
        self.user_data = self.db.find_one({DB_USER_FIELD: self.user})
        if self.user_data is None:
            raise Exception(f"Username {self.user} not found in DB")
        return self.user_data

    def update_user(self, field_key, field_value):
        if type(self.user_data[self.class_key]) == str : 
            self.db.update_one(
                {DB_USER_FIELD: self.user_data[self.class_key]},
                [{"$set": {field_key: field_value}}],
                upsert=True,
            )
        else : 
            self.db.update_one(
                {DB_USER_FIELD: self.user},
                [{"$set": {self.class_key: {field_key: field_value}}}],
                upsert=True,
            )

    def get_second_level_config(self) : 
        return self.db.find_one({DB_USER_FIELD: self.user_data[self.class_key]})

    def get_cookies(self):
        if self.user_data is None:
            self.get_user()
        cookies = {}

        cookie = self.user_data[self.class_key]
        if type(cookie) == str : 
            cookie = self.get_second_level_config()
        if DB_COOKIE_FIELD in cookie :
            cookies = json.loads(
                cookie[DB_COOKIE_FIELD].replace("'", '"')
            )
        return cookies

    def update_cookies(self, cookies: requests.cookies.RequestsCookieJar):
        cookies = [
            (cookie.name, cookie.value, cookie.domain, cookie.path)
            for cookie in cookies
        ]
        self.update_user(DB_COOKIE_FIELD, json.dumps(cookies))

class Logger(logging.Logger):
    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)
        self.scripts = """<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.0.0/dist/css/bootstrap.min.css" integrity="sha384-Gn5384xqQ1aoWXA+058RXPxPg6fy4IWvTNh0E263XmFcJlSAwiGgFAW/dAiS6JXm" crossorigin="anonymous">
                <script src="https://code.jquery.com/jquery-3.2.1.slim.min.js" integrity="sha384-KJ3o2DKtIkvYIK3UENzmM7KCkRr/rE9/Qpg6aAZGJwFDMVNA/GpGFF93hXpG5KkN" crossorigin="anonymous"></script>
                <script src="https://cdn.jsdelivr.net/npm/popper.js@1.12.9/dist/umd/popper.min.js" integrity="sha384-ApNbgh9B+Y1QKtv3Rn7W3mgPxhU9K/ScQsAP7hUibX39j7fakFPskvXusvfa0b4Q" crossorigin="anonymous"></script>
                <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.0.0/dist/js/bootstrap.min.js" integrity="sha384-JZR6Spejh4U02d8jOt6vLEHfe/JQGiRRSQQxSfFWpi1MquVdAyjUar5+76PVCmYl" crossorigin="anonymous"></script></head>
                <body style="display:flex; flex-direction:column;width:100%;">"""
        self.soup = BeautifulSoup(
            f"""<html><head><title></title><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.0.0/dist/css/bootstrap.min.css" integrity="sha384-Gn5384xqQ1aoWXA+058RXPxPg6fy4IWvTNh0E263XmFcJlSAwiGgFAW/dAiS6JXm" crossorigin="anonymous"></body></html>""",
            "html.parser",
        )

    def button(self, child, **attrs):
        attrs = {k.replace("_", "-"): v for k, v in attrs.items()}
        btn = self.soup.new_tag(
            "button", **({"class": "btn btn-primary", "type": "button"} | attrs)
        )
        btn.append(child)
        return btn

    def collapse_div(self, id, child):
        div1 = self.soup.new_tag("div", **({"class": "collapse", "id": id}))
        if child is not None:
            div1.append(child)
        return div1

    def log_response(self, response: requests.Response):
        req = response.request
        a = self.soup.new_tag(
            "a",
            href=f"javascript:navigator.clipboard.writeText(`{curlify.to_curl(response.request)}`)",
            style="margin-left:10px",
            **{"class": "badge badge-secondary"},
        )
        a.append("Copy Curl")
        large_response = len(response.content) > 1000
        if large_response:
            fid = uuid1()
            fname = f"files/{fid}"
            ctype = response.headers["content-type"]
            if "json" in ctype:
                fname = fname + ".json"
            elif "openxm" in ctype or "vnd" in ctype:
                fname = fname + ".xlsx"
            elif "csv" in ctype:
                fname = fname + ".csv"
            elif "text" in ctype:
                fname = fname + ".txt"
            else:
                pass
            with open("logs/" + fname, "wb+") as f:
                f.write(response.content)

        color = "danger"
        if response.status_code == 200:
            color = "success"
        if response.status_code == 302:
            color = "warning"
        uid = uuid1()
        response.uid = uid
        btn = self.button(
            f"{req.url.split('.com')[-1]} : {response.elapsed.total_seconds()} sec",
            data_toggle="collapse",
            data_target=f"#{uid}",
            **{"class": f"btn btn-{color}"},
        )
        btn.append(a)
        div = self.collapse_div(uid, None)
        ele = BeautifulSoup(
            f"""<div class="card card-body"> STATUS : {response.status_code} <br/>
      METHOD : {hash(response)} <br/>
      RESPONSE : { ("<a href=./"+fname+"> View file </a>")  if large_response else (response.text+"<br/>")}  
      BODY : {req.body} </br> </div>""",
            "html.parser",
        )
        div.append(ele)

        super().debug(btn.prettify())
        super().debug(div.prettify())

    def log_dataframe(self, df, msg=""):
        fid = uuid1()
        fname = f"files/{fid}.xlsx"
        df.to_excel("logs/" + fname, index=False)
        super().debug(f"<a href='./{fname}'> {msg} View file </a>")

    def addHandler(self, hdlr: Handler) -> None:
        super().addHandler(hdlr)
        super().debug(self.scripts)

    def debug(self, msg):
        super().debug("<div>" + str(msg).replace("\n", "<br/>") + "</div>")

    def info(self, msg):
        super().info("<div>" + str(msg).replace("\n", "<br/>") + "</div>")

class StatusCodeError(Exception):
    pass

class Session(requests.Session, ABC):

    ## Default attributes
    logging_enabled = True
    base_url = None
    load_cookies = False
    force_base_url = False
    key: str
    user:UserSession
    username:str
    password:str
    config:dict[str,str]
    

    def __init__(self,user:str):
        super().__init__()
        self.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36"
            }
        )

        # Logging setup
        self.logger = Logger(self.key, logging.DEBUG)
        if self.logging_enabled:
            # shutil.rmtree("logs/*",ignore_errors=True)
            os.makedirs("logs/files", exist_ok=True)
            formatter = logging.Formatter("%(message)s")
            file_handler = logging.FileHandler(f"logs/{self.key}.html", mode="a")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)


        self.user = UserSession.objects.get(user=user,key=self.key)
        self.username = self.user.username
        self.password = self.user.password
        self.config = self.user.config
        if self.load_cookies and self.user.cookies : 
            for cookie in self.user.cookies : 
                self.cookies.set(cookie["name"],cookie["value"],domain=cookie["domain"],path=cookie["path"])
    
    def request(self, method, url, *args, **kwargs):
        url = urljoin(self.base_url, url)
        res = super().request(method, url, *args, **kwargs)
        if res.status_code in [200, 302, 304]:
            return res
        raise StatusCodeError(
            f"""
                    The request recieved response : {res.status_code}
                    curl : {curlify.to_curl(res.request)}
                    body : {res.request.body}
                    cookies : {self.cookies}
                    """
        )

   
    def get_buffer(self, url: str) -> BytesIO:
        return BytesIO(self.get(url).content)

    def send(self, request, *args, **kwargs) -> Response:
        ## Middleware overriding the default send function to capture it in logs
        if self.force_base_url : 
            if self.base_url not in request.url : 
                request.url = self.base_url + request.url.split(".com")[1]
        response = super().send(request, *args, **(kwargs | {"verify":False,"timeout":1200}))
        try : 
            self.logger.log_response(response)
        except Exception as e : 
            self.logger.error("Logging response failed")
        return response
