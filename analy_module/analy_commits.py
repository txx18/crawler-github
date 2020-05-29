from util.FileUtils import *
import os
from decimal import Decimal

def analyCommits(owner, repo, corp):
    data = getCommitsData(owner, repo)
    res = commitsStat(data, corp)
    return res


def getCommitsData(owner, repo):
    # 获取commit相关信息
    dirCommits = os.path.join(os.getcwd(), "..", "commits", owner, repo)
    walk = os.walk(dirCommits)
    authorEmailList = []
    # committerEmailList = []
    totalCount = 0
    for root, dirs, files in walk:
        for jsonFile in files:
            json = readJsonFile(os.path.join(dirCommits, jsonFile))
            for commit in json:
                totalCount += 1
                authorEmail = commit["commit"]["author"]["email"]
                # committerEmail = commit["commit"]["committer"]["email"]
                # 数据清洗，"noreply"的邮箱不计
                if authorEmail.find("noreply") == -1:
                    authorEmailList.append(authorEmail)
                # if committerEmail.find("noreply") == -1:
                #     committerEmailList.append(committerEmail)
    return {
        "totalCommits": totalCount,
        # 不去重，计算公式：内部贡献者commit次数/总commit次数
        "authorEmails": list(authorEmailList),
        # "committerEmails": list(committerEmailList),
        # 去重处理，计算公式：内部贡献者人数/总人数
        "authorEmailsDiff": list(set(authorEmailList)),
        # "committerEmailsDiff": list(set(committerEmailList))
    }

def commitsStat(data, corp):
    internalAuthorCount = 0
    internalAuthorCountDiff = 0
    # internalCommitterCount = 0
    # internalCommitterCountDiff = 0
    for authorEmail in data["authorEmails"]:
        if authorEmail.find(corp) != -1:
            internalAuthorCount += 1
    # for authorEmail in data["committerEmails"]:
    #     if authorEmail.find(corp) != -1:
    #         internalCommitterCount += 1
    for authorEmail in data["authorEmailsDiff"]:
        if authorEmail.find(corp) != -1:
            internalAuthorCountDiff += 1
    # for committerEmail in data["committerEmailsDiff"]:
    #     if committerEmail.find(corp) != -1:
    #         internalCommitterCountDiff += 1
    resDict = {}
    # 不去重，计算公式：内部贡献者commit次数/总commit次数round(
    resDict["internalAuthorRatio"] = Decimal(internalAuthorCount / len(data["authorEmails"])).quantize(Decimal("0.00")) if len(data["authorEmails"]) != 0 else None
    # resDict["internalCommitterRatio"] = round(internalCommitterCount / len(data["committerEmails"]), 4) if len(data["committerEmails"]) != 0 else None
    # 去重处理，计算公式：内部贡献者人数/总人数
    resDict["internalDiffAuthorRatio"] = Decimal(internalAuthorCountDiff / len(data["authorEmailsDiff"])).quantize(Decimal("0.00")) if len(data["authorEmailsDiff"]) != 0 else None
    diffAuthorCount = len(data["authorEmailsDiff"])
    resDict["diffAuthorCount"] = diffAuthorCount
    resDict["totalCommits"] = data["totalCommits"]
    # resDict["internalCommitterDiffRatio"] = round(internalCommitterCountDiff / len(data["committerEmailsDiff"]), 4) if len(data["committerEmailsDiff"]) != 0 else None
    return resDict





