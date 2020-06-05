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
