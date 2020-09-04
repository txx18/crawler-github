import itertools
import random
import sys
import time

from crawler_module import crawler
from crawler_module import gol
from util.FileUtils import *
from analy_module.analy_commits import *
from analy_module.analy_repos import *
from visualization_module.visualization import *
import pandas as pd
import plotly.express as px


def saveRepoCommits():
    # 解析repos
    repoJson = readJsonFile(os.path.join(os.getcwd(), "..", "repos", gol.get_value("owner") + ".json"))
    i = 0
    for repo in repoJson:
        i += 1
        if i <= 20:
            continue
        try:
            cw.listPageCommits(gol.get_value("owner"), repo["name"])
        except Exception as e:
            print(e)
            sys.exit(-1)


def analyRepos2csv():
    reposAnalyResult = {}
    # 从repos文件夹下的json文件获取repo相关信息：创建时间、更新时间
    reposInfo = getReposData(gol.get_value("owner"))
    # 从commits文件夹获取各repo的commit信息
    ownerDir = os.path.join(os.getcwd(), "..", "commits", gol.get_value("owner"))
    for repo in os.listdir(ownerDir):
        # 返回reposAnalyResult[repo]是一个dict
        reposAnalyResult[repo] = analyCommits(gol.get_value("owner"), repo, gol.get_value("corp"))
        reposAnalyResult[repo]["createdAt"] = reposInfo["createTimeDict"][repo]
        reposAnalyResult[repo]["updatedAt"] = reposInfo["updateTimeDict"][repo]
    # 4、导出表格
    df = pd.DataFrame(list(reposAnalyResult.values()), index=list(reposAnalyResult.keys()), columns=list(reposAnalyResult.values())[0].keys())
    df = df.sort_values(by=['internalDiffAuthorRatio', 'diffAuthorCount'], ascending=False)
    resultDir = os.path.join(os.getcwd(), "..", "result", "repos")
    if not os.path.exists(resultDir):
        os.makedirs(resultDir)
    df.to_csv(os.path.join(resultDir, "统计结果" + time.strftime("%Y-%m-%d %H-%M-%S", time.localtime()) + ".csv"))
    print("分析完成，已导出csv到results文件夹下")


def getForkInfo():
    ownerDir = os.path.join(os.getcwd(), "..", "forks", gol.get_value("owner"))
    forkOwnerDict = {}
    for repoDirName in os.listdir(ownerDir):
        forkOwnerDict[repoDirName] = readForkOwner(gol.get_value("owner"), repoDirName)
    # 遍历所有forks，分别访问repo
    # forksNumInfo = {}
    for forkRepo, ownerList in forkOwnerDict.items():
        # forksNumInfo[forkRepo] = {}
        for owner in ownerList:
            # ① webDriver爬取方式
            # repoNumTypeInfo = cw.getRepoNumTypeInfo(owner, forkRepo)
            # forksNumInfo[forkRepo][owner] = repoNumTypeInfo
            # print(forksNumInfo)
            # ② api爬取并保存方式
            cw.getStatsContributors(owner, forkRepo)
        # 写入文件
        # writeFileAppend(os.path.join(os.getcwd(), "..", "tmp", gol.get_value("owner")), forkRepo + ".txt", forksNumInfo)


def saveStatsContributors():
    # 获取所有repo的forks
    # for repo in repoJson:
    #     cw.getRepoForks(gol.get_value("owner"), repo["name"])
    # 获取所有fork仓库的statContributors
    ownerDir = os.path.join(os.getcwd(), "..", "forks", gol.get_value("owner"))
    forkOwnerDict = {}
    for repoFolder in os.listdir(ownerDir):
        forkOwnerDict[repoFolder] = readForkOwner(gol.get_value("owner"), repoFolder)
    # 遍历所有forks，分别访问repo
    # forksNumInfo = {}
    # i = 0
    for forkRepo, ownerList in forkOwnerDict.items():
        # forksNumInfo[forkRepo] = {}
        # interruptIndexRepo = list(forkOwnerDict).index("VisualDL")
        # if i < 56:
        #     i += 1
        #     continue
        # j = 0
        for owner in ownerList:
            # ① webDriver爬取方式
            # repoNumTypeInfo = cw.getRepoNumTypeInfo(owner, forkRepo)
            # forksNumInfo[forkRepo][owner] = repoNumTypeInfo
            # print(forksNumInfo)

            # ② api爬取并保存方式
            # interruptIndexOwner = ownerList.index("Superjomn")
            # if i == 56 and j < 0:
            #     j += 1
            #     continue
            cw.getStatsContributors(owner, forkRepo)


if __name__ == "__main__":
    # 初始化全局变量
    gol._init()

    gol.set_value("proxyList", [
        "122.4.51.101:9999",
        "183.166.139.28:9999",
        "114.104.128.209:9999",
        "175.42.128.83:9999",
        "110.246.88.112:52600",
    ])

    gol.set_value("tokenList", [
        "f8ce7a0fc2dec251ddc6c55b32213cf61733****",
        "9322fbadda497df4d426a472bfca4552a221****",
        '7d0ccc90554e4d6f7e929da62d260c1d3184****',
        'daf8147992a0d67710fcb3c777124bd2958a****',
        "f1e698d42466d98fe92ad3c783f81bc779ea****",
        "ac2efda69d2ee99cc39a882de2c296df9e99****",
        "36c19c77004780355347f0f1d8381a1a58ff****"
    ])
    # token_iter = itertools.cycle(gol.get_value("tokenList"))  # 生成循环迭代器，迭代到最后一个token后，会重新开始迭代
    # gol.set_value("access_token", "9bbd8b9bb70ecefffcc12d41407d8d7f38dfb015")
    # gol.set_value("headers", {
    #     # "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.18363",
    #     "User-Agent": "Mozilla/5.0",
    #     'Authorization': 'token ' + gol.get_value("tokenList")[0],
    #     'Content-Type': 'application/json',
    #     'method': 'GET',
    #     'Accept': 'application/json'
    # }
    #               )

    # 设置要爬的owner
    gol.set_value("owner", "PaddlePaddle")
    # 还是准备把owner改成参数
    # owner = "PaddlePaddle"
    # 设置公司组织正则
    gol.set_value("corp", "baidu")

    # 整体流程
    # 分析一个org下所有repo
    cw = crawler.Crawler()
    # 1、爬一个user的所有repos
    # cw.listAllRepos(gol.get_value("owner"))

    # 2、对每一个repo，爬指定起始时间的commit
    # saveRepoCommits()

    # 3、遍历repos，对所有repo分析
    # analyRepos2csv()

    # 4、分析一个org下所有的repo的所有forks
    # saveStatsContributors()

    # 分析所有的fork仓库输出结果
    forkReposAnalyRes = statStatsContributors()
    # df = pd.DataFrame(list(forkReposAnalyRes.values()), index=list(forkReposAnalyRes.keys()), columns=list(forkReposAnalyRes.values())[0].keys())
    # df = df.sort_values(by=['contributorCount', 'commitCount'], ascending=False)
    # resultDir = os.path.join(os.getcwd(), "..", "result", "statsContributors")
    # if not os.path.exists(resultDir):
    #     os.makedirs(resultDir)
    # df.to_csv(os.path.join(resultDir, "统计结果" + time.strftime("%Y-%m-%d %H-%M-%S", time.localtime()) + ".csv"))
    # print("分析完成，已导出csv到results文件夹下")
    # 画出直方图
    ForkReposBarh(forkReposAnalyRes)


    # 爬一个repo的所有contributor
    # cw.getAllContributors("PaddlePaddle", "models")

    # 爬一个repo的所有contributor对应的user
    # cw.getUsers("PaddlePaddle", "Paddle")
