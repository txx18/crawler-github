import itertools

from crawler_module import crawler
from crawler_module import gol
from util.FileUtils import *
from analy_module.analy_commits import *
import pandas as pd

if __name__ == "__main__":
    gol._init()

    gol.set_value("headers", {
        # "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.18363",
        "User-Agent": "Mozilla/5.0",
        'Authorization': 'token cfb4ad35f5cbde8676b8fbb8ef858ea0dc32391e',
        'Content-Type': 'application/json',
        'method': 'GET',
        'Accept': 'application/json'
    }
                  )
    # gol.set_value("tokenList", [
    #     '293a06ac6ed5a746f7314be5a25f3d**********',
    #     '66de084042a7d3311544c656ad9273**********',
    #     'a513f61368e16c2da229e38e139a8e**********',
    #     '9055150c8fd031468af71cbb4e12c5**********',
    #     'ba119dc83af804327fa9dad8e07718**********',
    #     'b93e6996a4d76057d16e5e45788fbf**********',
    #     'c9c13e5c14d6876c76919520c9b05d**********',
    #     '3e41cbfc0c8878aec935fba68a0d3c**********',
    #     '402ff55399ca08ca7c886a2031f49f**********',
    #     '7cb6e20a24000968983b79b5de705c**********',
    # ])
    #
    # token_iter = itertools.cycle(gol.get_value("tokenList"))  # 生成循环迭代器，迭代到最后一个token后，会重新开始迭代

    # 流程
    # 设置要爬的owner
    gol.set_value("owner", "PaddlePaddle")
    cw = crawler.Crawler()

    # 1、爬一个user的所有repos
    # cw.listAllRepos(gol.get_value("owner"))

    # 2、对每一个repo，爬指定起始时间的commit
    # 解析repos
    repoJson = readJsonFile(os.path.join(os.getcwd(), "..", "repos", gol.get_value("owner") + ".json"))
    i = 0
    for repo in repoJson:
        i += 1
        if i < 16:
            continue
        cw.listPageCommits(gol.get_value("owner"), repo["name"])

    # 3、遍历repos，对所有repo分析
    reposAnalyResult = {}
    # 从repos文件夹下的json文件获取repo相关信息：创建时间、更新时间
    # repoJson = readJsonFile(os.path.join(os.getcwd(), "..", "repos", gol.get_value("owner") + ".json"))
    createTimeDict = {}
    updateTimeDict = {}
    for repo in repoJson:
        createTimeDict[repo["name"]] = repo["created_at"][:10]
        updateTimeDict[repo["name"]] = repo["updated_at"][:10]
    # 从commits文件夹获取各repo的commit信息
    ownerDir = os.path.join(os.getcwd(), "..", "commits", gol.get_value("owner"))
    # 设置公司组织正则
    corp = "baidu"
    for repo in os.listdir(ownerDir):
        reposAnalyResult[repo] = analyCommits(gol.get_value("owner"), repo, corp)
        reposAnalyResult[repo]["createdAt"] = createTimeDict[repo]
        reposAnalyResult[repo]["updatedAt"] = updateTimeDict[repo]

    # 4、导出表格
    df = pd.DataFrame(list(reposAnalyResult.values()), index=list(reposAnalyResult.keys()), columns=list(reposAnalyResult.values())[0].keys())
    df = df.sort_values(by=['internalAuthorRatio', 'diffAuthorCount'], ascending=False)
    df.to_csv(os.path.join(os.getcwd(), "统计结果-tx.csv"))
    print("导出csv完成")

    # 爬一个repo的所有contributor
    # cw.getAllContributors("PaddlePaddle", "models")

    # 爬一个repo的所有contributor对应的user
    # cw.getUsers("PaddlePaddle", "Paddle")
