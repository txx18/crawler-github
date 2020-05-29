# 对所有的用户，抽取其主页email信息

import time
from lxml import etree
import random

import codecs
import pymysql

pymysql.install_as_MySQLdb()
import MySQLdb

host, user, passwd, db = "localhost", "root", "11111111", "crawler_github"
conn = MySQLdb.connect(host, user, passwd, db, charset='utf8mb4')
cursor = conn.cursor()

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from time import sleep

driver = webdriver.Chrome()
driver.get("https://www.github.com")
time.sleep(30)
print("initialed")


# driver.set_page_load_timeout(30)
def _get_url(url, retry_times=3):
    try:
        raw_data = None
        error_msg = None
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("t").key_up(Keys.CONTROL).perform()
        # Loads a web page in the current browser session.
        driver.get(url)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("w").key_up(Keys.CONTROL).perform()
        print("getted")
        raw_data = driver.page_source.encode('utf-8')
    except Exception as e:
        print(e)
        error_msg = "maybe timeout"
    if error_msg != None:
        print(error_msg)
        if retry_times == 0:
            return None
        else:
            time.sleep(3)
            return _get_url(url, retry_times - 1)
    return raw_data


cursor.execute('select id,author_login from contributor_email where id < 12392 and id>37')
authors = cursor.fetchall()

profile_url = "https://github.com/%s"
for author in authors:
    author_id, login = author
    print(author)
    ini_html = _get_url(profile_url % login)
    if ini_html is None:
        print("\t", "no result")
        continue
    # print (ini_html)
    # with open("tmp.txt","wb") as fp:
    # 	fp.write(ini_html)
    # etree.HTML() 将字符串转换为Element对象
    # xpath() Evaluate an xpath expression using the element as context node
    # 选取 文档中的所有元素-a元素-拥有class属性，值为"u-email"-text()
    email = etree.HTML(ini_html).xpath('//*/a[@class="u-email "]/text()')
    if len(email) != 0:
        cursor.execute("update contributor_email set profile_email=%s where id=%s", (email[0], author_id))
        print(login, email)
        conn.commit()
    else:
        print("no email")
