# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/tools/async_file_writer.py
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

import asyncio
import csv
import json
import os
import pathlib
from typing import Dict, List
import aiofiles
import config
from tools.utils import utils
from tools.words import AsyncWordCloudGenerator

class AsyncFileWriter:
    def __init__(self, platform: str, crawler_type: str):
        self.lock = asyncio.Lock()
        self.platform = platform
        self.crawler_type = crawler_type
        self.wordcloud_generator = AsyncWordCloudGenerator() if config.ENABLE_GET_WORDCLOUD else None
        
        # 构建带关键词和时间范围的文件名标签
        keyword_label = self._sanitize_filename(config.KEYWORDS.replace(' ', '_')[:20])  # 取前20个字符
        
        # 获取时间范围标签
        time_label = ""
        if hasattr(config, 'START_DATE') and hasattr(config, 'END_DATE'):
            if config.START_DATE and config.END_DATE:
                time_label = f"_{config.START_DATE}_to_{config.END_DATE}"
            elif config.START_DATE:
                time_label = f"_from_{config.START_DATE}"
            elif config.END_DATE:
                time_label = f"_to_{config.END_DATE}"
        
        self.file_label = f"{keyword_label}{time_label}"
        
        # 用于存储已存在的ID，避免重复写入
        self.existing_ids = {}
        
        # 启动时立即加载已存在的数据
        self._load_existing_data()
    
    def _load_existing_data(self):
        """在初始化时加载已存在的数据ID"""
        for item_type in ['contents', 'comments']:
            file_path = self._get_file_path('json', item_type)
            
            # 初始化该类型的ID集合
            if item_type not in self.existing_ids:
                self.existing_ids[item_type] = set()
            
            # 如果文件存在且非空,读取并提取ID
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if content:
                            data = json.loads(content)
                            if not isinstance(data, list):
                                data = [data]
                            
                            # 根据item_type确定ID字段名
                            id_field = 'note_id' if item_type == 'contents' else 'comment_id'
                            
                            # 提取所有ID
                            for item in data:
                                if id_field in item:
                                    self.existing_ids[item_type].add(item[id_field])
                            
                            utils.logger.info(f"[AsyncFileWriter] Loaded {len(self.existing_ids[item_type])} existing {item_type} IDs from {file_path}")
                except (json.JSONDecodeError, Exception) as e:
                    utils.logger.warning(f"[AsyncFileWriter] Failed to load existing data from {file_path}: {e}")
    
    def get_comment_note_ids(self) -> set:
        """获取已经爬取过评论的笔记ID集合"""
        if 'comments' not in self.existing_ids:
            return set()
        
        # 从已存在的评论中提取所有独特的 note_id
        comment_note_ids = set()
        file_path = self._get_file_path('json', 'comments')
        
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            try:
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    comments = json.load(f)
                    if isinstance(comments, list):
                        for comment in comments:
                            if 'note_id' in comment:
                                comment_note_ids.add(comment['note_id'])
            except Exception:
                pass
        
        return comment_note_ids

    def _sanitize_filename(self, name: str) -> str:
        """清理文件名，移除非法字符"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        return name

    def _get_file_path(self, file_type: str, item_type: str) -> str:
        base_path = f"data/{self.platform}/{file_type}"
        pathlib.Path(base_path).mkdir(parents=True, exist_ok=True)
        # 新的文件命名格式: search_contents_关键词_时间范围.json
        file_name = f"{self.crawler_type}_{item_type}_{self.file_label}.{file_type}"
        return f"{base_path}/{file_name}"

    async def write_to_csv(self, item: Dict, item_type: str):
        file_path = self._get_file_path('csv', item_type)
        async with self.lock:
            file_exists = os.path.exists(file_path)
            async with aiofiles.open(file_path, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=item.keys())
                if not file_exists or await f.tell() == 0:
                    await writer.writeheader()
                await writer.writerow(item)

    async def write_single_item_to_json(self, item: Dict, item_type: str):
        file_path = self._get_file_path('json', item_type)
        async with self.lock:
            # 初始化该文件类型的ID集合
            if item_type not in self.existing_ids:
                self.existing_ids[item_type] = set()
            
            existing_data = []
            
            # 读取已存在的数据
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        content = await f.read()
                        if content:
                            existing_data = json.loads(content)
                        if not isinstance(existing_data, list):
                            existing_data = [existing_data]
                        
                        # 提取已存在的ID
                        for existing_item in existing_data:
                            # 根据item_type确定ID字段名
                            id_field = 'note_id' if item_type == 'contents' else 'comment_id'
                            if id_field in existing_item:
                                self.existing_ids[item_type].add(existing_item[id_field])
                    except json.JSONDecodeError:
                        existing_data = []
            
            # 检查当前item的ID是否已存在
            id_field = 'note_id' if item_type == 'contents' else 'comment_id'
            item_id = item.get(id_field)
            
            if item_id in self.existing_ids[item_type]:
                utils.logger.info(f"[AsyncFileWriter] Skip duplicate {item_type[:-1]} ID: {item_id}")
                return  # 跳过重复的数据
            
            # 添加新数据
            existing_data.append(item)
            self.existing_ids[item_type].add(item_id)
            utils.logger.info(f"[AsyncFileWriter] Added new {item_type[:-1]} ID: {item_id} (Total: {len(self.existing_ids[item_type])})")

            # 写回文件
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(existing_data, ensure_ascii=False, indent=4))

    async def generate_wordcloud_from_comments(self):
        """
        Generate wordcloud from comments data
        Only works when ENABLE_GET_WORDCLOUD and ENABLE_GET_COMMENTS are True
        """
        if not config.ENABLE_GET_WORDCLOUD or not config.ENABLE_GET_COMMENTS:
            return

        if not self.wordcloud_generator:
            return

        try:
            # Read comments from JSON file
            comments_file_path = self._get_file_path('json', 'comments')
            if not os.path.exists(comments_file_path) or os.path.getsize(comments_file_path) == 0:
                utils.logger.info(f"[AsyncFileWriter.generate_wordcloud_from_comments] No comments file found at {comments_file_path}")
                return

            async with aiofiles.open(comments_file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                if not content:
                    utils.logger.info(f"[AsyncFileWriter.generate_wordcloud_from_comments] Comments file is empty")
                    return

                comments_data = json.loads(content)
                if not isinstance(comments_data, list):
                    comments_data = [comments_data]

            # Filter comments data to only include 'content' field
            # Handle different comment data structures across platforms
            filtered_data = []
            for comment in comments_data:
                if isinstance(comment, dict):
                    # Try different possible content field names
                    content_text = comment.get('content') or comment.get('comment_text') or comment.get('text') or ''
                    if content_text:
                        filtered_data.append({'content': content_text})

            if not filtered_data:
                utils.logger.info(f"[AsyncFileWriter.generate_wordcloud_from_comments] No valid comment content found")
                return

            # Generate wordcloud
            words_base_path = f"data/{self.platform}/words"
            pathlib.Path(words_base_path).mkdir(parents=True, exist_ok=True)
            words_file_prefix = f"{words_base_path}/{self.crawler_type}_comments_{utils.get_current_date()}"

            utils.logger.info(f"[AsyncFileWriter.generate_wordcloud_from_comments] Generating wordcloud from {len(filtered_data)} comments")
            await self.wordcloud_generator.generate_word_frequency_and_cloud(filtered_data, words_file_prefix)
            utils.logger.info(f"[AsyncFileWriter.generate_wordcloud_from_comments] Wordcloud generated successfully at {words_file_prefix}")

        except Exception as e:
            utils.logger.error(f"[AsyncFileWriter.generate_wordcloud_from_comments] Error generating wordcloud: {e}")
