import itertools
import sys
import time

from crawler_module import crawler
from crawler_module import gol
from util.FileUtils import *
from analy_module.analy_commits import *
from analy_module.analy_repos import *
import pandas as pd
import plotly.express as px

if __name__ == "__main__":
    # 初始化全局变量
    gol._init()

    gol.set_value("tokenList", [
        # '7d0ccc90554e4d6f7e929da62d260c1d31844878',
        "f8ce7a0fc2dec251ddc6c55b32213cf6173383bb",
        'daf8147992a0d67710fcb3c777124bd2958af497',
    ])
    token_iter = itertools.cycle(gol.get_value("tokenList"))  # 生成循环迭代器，迭代到最后一个token后，会重新开始迭代
    # gol.set_value("access_token", "9bbd8b9bb70ecefffcc12d41407d8d7f38dfb015")
    gol.set_value("headers", {
        # "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.18363",
        "User-Agent": "Mozilla/5.0",
        'Authorization': 'token ' + token_iter.__next__(),
        'Content-Type': 'application/json',
        'method': 'GET',
        'Accept': 'application/json'
    }
                  )
    # 设置要爬的owner
    gol.set_value("owner", "PaddlePaddle")
    # 设置公司组织正则
    gol.set_value("corp", "baidu")

    # 整体流程
    cw = crawler.Crawler()
    # 1、爬一个user的所有repos
    # cw.listAllRepos(gol.get_value("owner"))

    # 2、对每一个repo，爬指定起始时间的commit
    # 解析repos
    repoJson = readJsonFile(os.path.join(os.getcwd(), "..", "repos", gol.get_value("owner") + ".json"))
    # 爬取
    # i = 0
    # for repo in repoJson:
    #     i += 1
    #     if i <= 20:
    #         continue
    #     try:
    #         cw.listPageCommits(gol.get_value("owner"), repo["name"])
    #     except Exception as e:
    #         print(e)
    #         sys.exit(-1)

    # 2.5 获取一个owner的所有repo的forks
    i = 0
    for repo in repoJson:
        i += 1
        if i <= 19:
            continue
        cw.listPageForks(gol.get_value("owner"), repo["name"])

    # 3、遍历repos，对所有repo分析
    # 开关
    sys.exit(-1)
    reposAnalyResult = {}
    # 从repos文件夹下的json文件获取repo相关信息：创建时间、更新时间
    reposInfo = getReposData(gol.get_value("owner"))
    # 从commits文件夹获取各repo的commit信息
    ownerDir = os.path.join(os.getcwd(), "..", "commits", gol.get_value("owner"))
    for repo in os.listdir(ownerDir):
        reposAnalyResult[repo] = analyCommits(gol.get_value("owner"), repo, gol.get_value("corp"))
        reposAnalyResult[repo]["createdAt"] = reposInfo["createTimeDict"][repo]
        reposAnalyResult[repo]["updatedAt"] = reposInfo["updateTimeDict"][repo]

    # 4、导出表格
    df = pd.DataFrame(list(reposAnalyResult.values()), index=list(reposAnalyResult.keys()), columns=list(reposAnalyResult.values())[0].keys())
    df = df.sort_values(by=['internalDiffAuthorRatio', 'diffAuthorCount'], ascending=False)
    resultDir = os.path.join(os.getcwd(), "..", "result")
    if not os.path.exists(resultDir):
        os.makedirs(resultDir)
    df.to_csv(os.path.join(resultDir, "统计结果" + time.strftime("%Y-%m-%d %H-%M-%S", time.localtime()) + ".csv"))
    print("分析完成，已导出csv到results文件夹下")

    # 爬一个repo的所有contributor
    # cw.getAllContributors("PaddlePaddle", "models")

    # 爬一个repo的所有contributor对应的user
    # cw.getUsers("PaddlePaddle", "Paddle")
