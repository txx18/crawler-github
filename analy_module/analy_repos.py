import os

from util.FileUtils import readJsonFile


def getReposData(owner):
    repoJson = readJsonFile(os.path.join(os.getcwd(), "..", "repos", owner + ".json"))
    createTimeDict = {}
    updateTimeDict = {}
    for repo in repoJson:
        createTimeDict[repo["name"]] = repo["created_at"][:10]
        updateTimeDict[repo["name"]] = repo["updated_at"][:10]
    return {
        "createTimeDict": createTimeDict,
        "updateTimeDict": updateTimeDict
    }

def readForkOwner(owner, forkRepo):
    repoDir = os.path.join(os.path.join(os.getcwd(), "..", "forks", owner, forkRepo))
    forkOwnerList = []
    for pageJsonFile in os.listdir(repoDir):
        json = readJsonFile(os.path.join(repoDir, pageJsonFile))
        for forkRepo in json:
            forkOwnerList.append(forkRepo["owner"]["login"])
    return forkOwnerList

def readStatsContributors(owner, repo):
    res = {}
    res.setdefault("contributorCount", 0)
    res.setdefault("commitCount", 0)
    contributorCount = 0
    commitCount = 0
    repoDir = os.path.join(os.path.join(os.getcwd(), "..", "statsContributors", owner, repo))
    for jsonFile in os.listdir(repoDir):
        json = {}
        try:
            json = readJsonFile(os.path.join(repoDir, jsonFile))
        except Exception as e:
            print(e)
            print("read jsonFile failed")
        for dic in json:
            if dic.__contains__('total') is False:
                print("no total attr")
                return res
            contributorCount += 1
            commitCount += dic["total"]
    res["contributorCount"] = contributorCount
    res["commitCount"] = commitCount
    return res

def statStatsContributors():
    res = {}
    statsContributorsDir = os.path.join(os.getcwd(), "..", "statsContributors")
    for ownerFolder in os.listdir(statsContributorsDir):
        ownerDir = os.path.join(os.path.join(statsContributorsDir, ownerFolder))
        contributorCount = 0
        commitCount = 0
        for repoFolder in os.listdir(ownerDir):
            print(ownerFolder + "/" + repoFolder)
            res[repoFolder] = {}
            oneRepoRes = readStatsContributors(ownerFolder, repoFolder)
            contributorCount += oneRepoRes["contributorCount"]
            commitCount += oneRepoRes["commitCount"]
            res[repoFolder]["contributorCount"] = contributorCount
            res[repoFolder]["commitCount"] = commitCount
    return res

