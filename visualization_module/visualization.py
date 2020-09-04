from matplotlib import pyplot as plt
from matplotlib import font_manager

import pandas as pd

font = font_manager.FontProperties(fname=r"D:\Disk_software\pingfangziti\苹方黑体-中粗-简.ttf")

def ForkReposBarh(forkReposAnalyRes):
    y = list(forkReposAnalyRes.keys())
    valuesList = list(forkReposAnalyRes.values())

    x_contributorCount = list(value["contributorCount"] for value in valuesList)
    x_commitCount = list(value["commitCount"] for value in valuesList)

    plt.figure(figsize=(20, 8), dpi=80)
    # 绘制条形图
    barWidth = 0.3
    _y_contributorCount = range(len(y))
    _y_commitCount = list(i + barWidth for i in _y_contributorCount)
    plt.barh(_y_contributorCount, x_contributorCount, height=barWidth, color="blue")
    plt.barh(_y_commitCount, x_commitCount, height=barWidth, color="orange")
    # 设置y轴labels
    plt.yticks(_y_contributorCount, y, fontproperties=font)

    plt.grid(alpha=0.3)

    plt.show()