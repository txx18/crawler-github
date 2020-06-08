import os
import json

# 将结果写入文件
def writeFile(fileDir, file, data):
    if not os.path.exists(fileDir):
        os.makedirs(fileDir)
    with open(file, 'w', encoding="utf-8") as outfile:
        # json.dump(data, outfile)
        outfile.write(data)

def writeFileAppend(fileDir, file, data):
    if not os.path.exists(fileDir):
        os.makedirs(fileDir)
    with open(file, 'a', encoding="utf-8") as outfile:
        # json.dump(data, outfile)
        outfile.write(data)

def writeJsonFile(fileDir, file, data):
    if not os.path.exists(fileDir):
        os.makedirs(fileDir)
    with open(file, 'w') as outfile:
        json.dump(data, outfile)
        # outfile.write(data)

# 读取json result
def readJsonFile(filepath):
    with open(filepath, 'r', encoding="utf-8") as f:
        # str1 = f.read()
        r = json.load(f)
        return r