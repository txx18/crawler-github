# 输入一个repo，返回所有的contributor信息
import os
import time

import click
import requests
from lxml import etree
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys

from util import helpers
from util.FileUtils import *
from crawler_module import gol, query
from util.helpers import *


class Crawler(object):

    def __init__(self):
        self.USERSAPI = "https://api.github.com/users/"
        self.REPOSAPI = "https://api.github.com/repos/"
        self.access_token = gol.get_value("access_token")
        self.headers = gol.get_value("headers")
        # self.driver = webdriver.Chrome()
        # self.driver.implicitly_wait(10)

    def listAllRepos(self, owner="PaddlePaddle"):
        url = self.USERSAPI + owner + "/repos?per_page=100&access_token=" + self.access_token
        print("开始爬取" + owner + "的至多100个repo...")
        resultStr = ""
        try:
            resp = requests.get(url, gol.get_value("headers"))
            resultStr = resp.content.decode()
        except Exception as e:
            print(e)
        # 写入文件
        outDir = os.path.join(os.getcwd(), "..", "repos")
        writeFile(outDir, os.path.join(outDir, owner + ".json"), resultStr)
        print("已爬完" + owner + "的至多100个repo...")
        return resultStr

    def listAllContributors(self, owner="PaddlePaddle", repo="Serving", pageNo=0, retry_times=3):
        url = "https://api.github.com/repos/" + owner + "/" + repo + "/contributors?per_page=100&access_token=" + self.access_token
        resultStr = ""
        pageNo += 1
        print("爬取...第" + str(pageNo) + "页")
        try:
            resp = requests.get(url, gol.get_value("headers"))
            firstPageStr = resp.content.decode()
            resultStr += firstPageStr
            # 如果有下一页
            if resp.links.__contains__("next"):
                # 处理字符串，第一页把最后的]换成
                resultStr = resultStr[:-1] + ", "
                while resp.links.__contains__("next"):
                    pageNo += 1
                    print("爬取...第" + str(pageNo) + "页")
                    nextUrl = resp.links["next"]["url"] + "&access_token=" + self.access_token
                    resp = requests.get(nextUrl, gol.get_value("headers"))
                    respStr = resp.content.decode()
                    # 处理字符串，其余页把头尾的]换成,
                    nextPageStr = respStr[1:-1] + ", "
                    # 拼接每一页
                    resultStr += nextPageStr
                    time.sleep(1)
        except Exception as e:
            print(e)
            # 出现异常先把爬到的写出
            if retry_times == 3:
                resultStr = resultStr[:-1] + "]"
                outDir = os.path.join(os.getcwd(), "..", "users", owner)
                writeFile(outDir, os.path.join(outDir, repo + ".json"), resultStr)
            error_msg = "爬取第" + str(pageNo) + "页时出现异常...正在重试..."
            if error_msg is not None:
                print(error_msg)
                if retry_times == 0:
                    print("失败3次，中止...")
                    return None
                else:
                    time.sleep(3)
                    return self.listAllContributors(owner, repo, pageNo - 1, retry_times - 1)
        # 写入文件
        # 最后可能还要把,换成]
        resultStr = resultStr[:-1] + "]"
        outDir = os.path.join(os.getcwd(), "..", "contributors", owner)
        writeFile(outDir, os.path.join(outDir, repo + ".json"), resultStr)
        return resultStr

    def listUsers(self, owner="PaddlePaddle", repo="Serving", userNo=0, retry_times=3):
        # 读取repo的contributors
        dir = os.path.join(os.getcwd(), "..", "contributors", owner)
        contributorList = readJsonFile(os.path.join(dir, repo + ".json"))
        # 查询api，获取对应的user
        resultStr = "["
        for contributor in contributorList:
            userNo += 1
            print("爬取...第" + str(userNo) + "个用户")
            login = contributor["login"]
            url = self.USERSAPI + login + "?access_token=" + self.access_token
            try:
                resp = requests.get(url, gol.get_value("headers"))
                respStr = resp.content.decode() + ","
                resultStr += respStr
            except Exception as e:
                print(e)
                # 出现异常先把已经爬到的写出去
                if retry_times == 3:
                    resultStr = resultStr[:-1] + "]"
                    outDir = os.path.join(os.getcwd(), "..", "users", owner)
                    writeFile(outDir, os.path.join(outDir, repo + ".json"), resultStr)
                error_msg = "爬取第" + str(userNo) + "个用户时出现异常...正在重试..."
                if error_msg is not None:
                    print(error_msg)
                    if retry_times == 0:
                        print("失败3次，中止...")
                        return None
                    else:
                        time.sleep(3)
                        return self.listUsers(owner, repo, userNo - 1, retry_times - 1)
            time.sleep(1)
        # 写入文件
        # 最后可能还要把,换成]
        resultStr = resultStr[:-1] + "]"
        outDir = os.path.join(os.getcwd(), "..", "users", owner)
        writeFile(outDir, os.path.join(outDir, repo + ".json"), resultStr)
        return resultStr

    def getStatsContributors(self, owner="PaddlePaddle", repo="Serving", pageNo=0, retry_times=3):
        print("开始爬取" + owner + "的" + repo + "仓库的StatsContributors")
        time.sleep(3)
        # 面对异常处理，需要从当前失败的页继续开始
        pageNo += 1
        url = "%s%s/%s/stats/contributors?page=%s&per_page=100" % (self.REPOSAPI, owner, repo, str(pageNo))
        # url = self.REPOSAPI + owner + "/" + repo + "/stats/contributors?page=" + str(pageNo) + "&per_page=100"
        resultStr = ""
        print("爬取...第" + str(pageNo) + "页")
        try:
            # 获取第pageNo页
            headers = updateHeaders()
            # proxy = updateIP()
            # resp = requests.get(url, headers=headers)
            resp = requests.get(url, headers=headers, verify=False)
            firstPageStr = resp.content.decode()
            # 测试API限制
            print(gol.get_value("headers"))
            # print(gol.get_value("proxy"))
            print(str(resp.headers.get("X-RateLimit-Limit")) + " remain: " + str(resp.headers.get("X-RateLimit-Remaining")))
            resultStr += firstPageStr
            # 剔除没有贡献者的forkRepo
            if resultStr == "{}" or "":
                return
            # 有时候会有各种异常，必须抛出禁止写入
            if resp.status_code != 200 or resultStr.find("total") == -1:
                raise Exception("wrong resp")
            # 写入文件
            outDir = os.path.join(os.getcwd(), "..", "statsContributors", owner, repo)
            writeFile(outDir, os.path.join(outDir, "page1.json"), resultStr)
            # 如果有下一页，循环
            while resp.links.__contains__("next"):
                pageNo += 1
                print("爬取...第" + str(pageNo) + "页")
                time.sleep(3)
                nextUrl = resp.links["next"]["url"]
                headers = updateHeaders()
                resp = requests.get(nextUrl, headers=headers)
                resultStr = resp.content.decode()
                # 有时候被拒绝请求会返回message，抛出异常
                if resultStr.find("API rate limit exceeded for") != -1:
                    raise Exception("API rate limit exceeded")
                # 写入文件
                writeFile(outDir, os.path.join(outDir, "page" + str(pageNo) + ".json"), resultStr)
        except Exception as e:
            print(e)
            error_msg = "爬取第" + str(pageNo) + "页时出现异常...正在重试..."
            if error_msg is not None:
                print(error_msg)
                if retry_times == 0:
                    print("失败3次，中止...")
                    raise Exception('请求异常', '爬取失败')
                else:
                    time.sleep(30)
                    return self.getStatsContributors(owner, repo, pageNo - 1, retry_times - 1)
        print("已爬完" + owner + "的" + repo + "仓库的StatsContributors")
        return resultStr

    # driver.set_page_load_timeout(30)
    def _get_url(self, url, retry_times=3):
        self.driver.get("https://www.github.com")
        # time.sleep(30)
        print("initialed")
        try:
            raw_data = None
            error_msg = None
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys("t").key_up(Keys.CONTROL).perform()
            # Loads a web page in the current browser session.
            self.driver.get(url)
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys("w").key_up(Keys.CONTROL).perform()
            print("url got")
            raw_data = self.driver.page_source.encode('utf-8')
        except Exception as e:
            print(e)
            error_msg = "maybe timeout"
        if error_msg != None:
            print(error_msg)
            if retry_times == 0:
                return None
            else:
                time.sleep(3)
                return self._get_url(self, url, retry_times - 1)
        return raw_data

    def getRepoNumTypeInfo(self, owner, repo):
        """
        webdriver请求的方式
        :param owner:
        :param repo:
        :return:
        """
        repoNumTypeInfo = {}
        repo_url = "https://github.com/%s/%s"
        print("开始爬取%sfork的%s仓库的数值信息..." % (owner, repo))
        ini_html = self._get_url(repo_url % (owner, repo))
        # ini_html = self.driver.get(repo_url % (owner, repo))
        if ini_html is None:
            print("\t", "no result")
        numTypeInfoList = etree.HTML(ini_html).xpath('//*/span[@class="num text-emphasized"]/text()')
        if len(numTypeInfoList) != 0:
            repoNumTypeInfo["commits"] = numTypeInfoList[0]
            repoNumTypeInfo["contributors"] = numTypeInfoList[4]
        else:
            print("no num text-emphasized")
        return repoNumTypeInfo


    def listPageCommits(self, owner="PaddlePaddle", repo="Serving", since="2017-01-01T00:00:00Z", pageNo=0, retry_times=3):
        print("开始爬取" + owner + "的" + repo + "仓库的Commits，数据采集开始时间：" + since)
        time.sleep(3)
        # 面对异常处理，需要从当前失败的页继续开始
        pageNo += 1
        url = "https://api.github.com/repos/" + owner + "/" + repo + "/commits?page=" + str(
            pageNo) + "&per_page=100&since=" + since
        resultStr = ""
        print("爬取...第" + str(pageNo) + "页")
        try:
            # 获取第pageNo页
            resp = requests.get(url, headers=self.headers)
            firstPageStr = resp.content.decode()
            # 测试API限制
            print(gol.get_value("headers"))
            print(str(resp.headers.get("X-RateLimit-Limit")) + " remain: " + str(resp.headers.get("X-RateLimit-Remaining")))
            resultStr += firstPageStr
            # 有时候被拒绝请求会返回message，抛出异常
            if resultStr.find("API rate limit exceeded for") != -1:
                raise Exception("API rate limit exceeded")
            # 写入文件
            outDir = os.path.join(os.getcwd(), "..", "commits", owner, repo)
            writeFile(outDir, os.path.join(outDir, "page1.json"), resultStr)
            # 如果有下一页，循环
            while resp.links.__contains__("next"):
                pageNo += 1
                print("爬取...第" + str(pageNo) + "页")
                time.sleep(4)
                nextUrl = resp.links["next"]["url"] + "&since=" + since
                resp = requests.get(nextUrl, headers=self.headers)
                resultStr = resp.content.decode()
                # 有时候被拒绝请求会返回message，抛出异常
                if resultStr.find("API rate limit exceeded for") != -1:
                    raise Exception("API rate limit exceeded")
                # 写入文件
                writeFile(outDir, os.path.join(outDir, "page" + str(pageNo) + ".json"), resultStr)
        except Exception as e:
            print(e)
            error_msg = "爬取第" + str(pageNo) + "页时出现异常...正在重试..."
            if error_msg is not None:
                print(error_msg)
                if retry_times == 0:
                    print("失败3次，中止...")
                    raise Exception('请求异常', '爬取失败')
                else:
                    time.sleep(3)
                    return self.listPageCommits(owner, repo, since, pageNo - 1, retry_times - 1)
        print("已爬完" + owner + "的" + repo + "仓库的Commits，数据采集开始时间：" + since)
        return resultStr

    def getRepoForks(self, owner="PaddlePaddle", repo="Serving", pageNo=0, retry_times=3):
        print("开始爬取" + owner + "的" + repo + "仓库的Forks")
        time.sleep(4)
        # 面对异常处理，需要从当前失败的页继续开始
        pageNo += 1
        url = self.REPOSAPI + owner + "/" + repo + "/forks?page=" + str(
            pageNo) + "&per_page=100"
        resultStr = ""
        print("爬取...第" + str(pageNo) + "页")
        try:
            # 获取第pageNo页
            resp = requests.get(url, headers=self.headers, verify=False)
            firstPageStr = resp.content.decode()
            # 测试API限制
            print(gol.get_value("headers"))
            print(str(resp.headers.get("X-RateLimit-Limit")) + " remain: " + str(resp.headers.get("X-RateLimit-Remaining")))
            resultStr += firstPageStr
            # 有时候被拒绝请求会返回message，抛出异常
            if resultStr.find("API rate limit exceeded for") != -1:
                raise Exception("API rate limit exceeded")
            # 写入文件
            outDir = os.path.join(os.getcwd(), "..", "forks", owner, repo)
            writeFile(outDir, os.path.join(outDir, "page1.json"), resultStr)
            # 如果有下一页，循环
            while resp.links.__contains__("next"):
                pageNo += 1
                print("爬取...第" + str(pageNo) + "页")
                time.sleep(4)
                nextUrl = resp.links["next"]["url"]
                resp = requests.get(nextUrl, headers=self.headers, verify=False)
                resultStr = resp.content.decode()
                # 有时候被拒绝请求会返回message，抛出异常
                if resultStr.find("API rate limit exceeded for") != -1:
                    raise Exception("API rate limit exceeded")
                # 写入文件
                writeFile(outDir, os.path.join(outDir, "page" + str(pageNo) + ".json"), resultStr)
        except Exception as e:
            print(e)
            error_msg = "爬取第" + str(pageNo) + "页时出现异常...正在重试..."
            if error_msg is not None:
                print(error_msg)
                if retry_times == 0:
                    print("失败3次，中止...")
                    raise Exception('请求异常', '爬取失败')
                else:
                    time.sleep(3)
                    return self.getRepoForks(owner, repo, pageNo - 1, retry_times - 1)
        print("已爬完" + owner + "的" + repo + "仓库的Forks")
        return resultStr

    def fetch_repo_data(self, owner, repository, config):
        # 定义空白数组
        commitArray = []
        pullRequestArray = []

        # 添加一个可过滤掉的数据，确保后续执行完成
        commitArray.append({
            'author': 'localhost',
            'domain': '',
            'is_corp': False,
            'date': '未标注时间',
            "times": 1
        })
        pullRequestArray.append({
            'date': '未标注时间',
            "times": 1
        })
        # 定义查询变量
        start_time = config["time"]["start_time"]
        end_time = config["time"]["end_time"]
        top_number = int(config["rank"]["top"])
        click.echo("抓取数据：+", nl=False)
        # 进行初次查询
        all_query = query.all_query % (owner, repository, start_time, end_time)
        result = helpers.query(all_query, config)
        # 处理第一组数据
        if (helpers.has_result(result, "commit")):
            for commit in result["data"]["repository"]["ref"]["target"]["history"]["edges"]:
                helpers.add_item_to_commit_array(commit, commitArray)
                pass

        if (helpers.has_result(result, "pr")):
            for pullRequest in result["data"]["repository"]["pullRequests"]["nodes"]:
                helpers.add_item_to_pr_array(pullRequest, pullRequestArray)
        # 循环翻页
        while helpers.has_next_page(result, "commit") or helpers.has_next_page(result, "issue") or helpers.has_next_page(result, "pr"):
            click.echo("+", nl=False)
            if (helpers.has_result(result, "commit")):
                for commit in result["data"]["repository"]["ref"]["target"]["history"]["edges"]:
                    helpers.add_item_to_commit_array(commit, commitArray)
                    pass
            if (helpers.has_result(result, "pr")):
                for pullRequest in result["data"]["repository"]["pullRequests"]["nodes"]:
                    helpers.add_item_to_pr_array(pullRequest, pullRequestArray)

            if (helpers.has_next_page(result, "pr") and helpers.has_next_page(result, "commit")):
                next_query = query.all_query_with_pager % (owner, repository, helpers.get_page_cursor(
                    result, "pr"), helpers.get_page_cursor(result, "commit"), start_time, end_time)
            elif (helpers.has_next_page(result, "pr")):
                next_query = query.pr_query_with_pager % (
                    owner, repository, helpers.get_page_cursor(result, "pr"))
            elif (helpers.has_next_page(result, "commit")):
                next_query = query.commit_query_with_pager % (
                    owner, repository, helpers.get_page_cursor(result, "commit"), start_time, end_time)

            result = helpers.query(next_query, config)
        click.echo('')
        return {
            "pullRequestArray": pullRequestArray,
            "commitArray": commitArray
        }
