# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/config/xhs_config.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。


# 小红书平台配置

# 排序方式，具体的枚举值在media_platform/xhs/field.py中
# 可选值：
#   "general" - 综合排序（默认）
#   "popularity_descending" - 按热度降序
#   "time_descending" - 按时间降序（最新发布）
# 注：当设置了 START_DATE 或 END_DATE 时，会自动使用 "time_descending" 排序以提高效率
SORT_TYPE = "popularity_descending"

# 发布时间筛选（日期范围）
# 格式："YYYY-MM-DD" 或 空字符串表示不限制
# 示例：
#   START_DATE = "2025-10-01"  # 开始日期
#   END_DATE = "2025-10-10"    # 结束日期
#   如果不需要时间筛选，设置为空字符串: START_DATE = ""
START_DATE = ""  # 开始日期，格式：YYYY-MM-DD，留空表示不限制
END_DATE = ""    # 结束日期，格式：YYYY-MM-DD，留空表示不限制

# 排除创作者黑名单（不爬取这些创作者的笔记）
# 填写创作者的 user_id，可以从笔记详情中的 user_id 字段获取
# 或从创作者主页URL中提取，例如：
#   https://www.xiaohongshu.com/user/profile/5f58bd990000000001003753
#   user_id 就是: 5f58bd990000000001003753
EXCLUDED_CREATOR_IDS = [
    '637db651000000001e00c6db'
    # "5f58bd990000000001003753",  # 示例：要排除的创作者ID
    # "60a071d50000000001006425",  # 可以添加多个
]

# 指定笔记URL列表, 必须要携带xsec_token参数
XHS_SPECIFIED_NOTE_URL_LIST = [
    "https://www.xiaohongshu.com/explore/64b95d01000000000c034587?xsec_token=AB0EFqJvINCkj6xOCKCQgfNNh8GdnBC_6XecG4QOddo3Q=&xsec_source=pc_cfeed"
    # ........................
]

# 指定创作者URL列表，需要携带xsec_token和xsec_source参数

XHS_CREATOR_ID_LIST = [
    "https://www.xiaohongshu.com/user/profile/5f58bd990000000001003753?xsec_token=ABYVg1evluJZZzpMX-VWzchxQ1qSNVW3r-jOEnKqMcgZw=&xsec_source=pc_search"
    # ........................
]
