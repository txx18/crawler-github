# -*- coding: utf-8 -*-
def _init():
    global _global_dict
    _global_dict = {}


def set_value(key, value):
    """ 定义一个全局变量字典 """
    _global_dict[key] = value


def get_value(key, defValue=None):
    """
    获得一个全局变量,不存在则返回默认值
    :param key:
    :param defValue:
    :return:
    """
    try:
        return _global_dict[key]
    except KeyError:
        return defValue
