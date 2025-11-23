"""
个人主页爬取脚本
功能：
1. 读取并合并detail_contents_蚂蚁_黑卡_before_add.json和detail_comments_蚂蚁_黑卡_before_add.json中的user_id
2. 去重后使用creator模式爬取用户主页信息
3. 支持断点续传功能
"""
sleep_sec = 2
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Set
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import config
from base.base_crawler import AbstractCrawler
from media_platform.xhs import XiaoHongShuCrawler
from proxy.proxy_ip_pool import create_ip_pool
from tools import utils
from var import crawler_type_var


# 断点续传进度文件
PROGRESS_FILE = project_root / "creator_crawl_progress.json"


class CrawlerFactory:
    CRAWLERS = {
        "xhs": XiaoHongShuCrawler,
    }

    @staticmethod
    def create_crawler(platform: str) -> AbstractCrawler:
        crawler_class = CrawlerFactory.CRAWLERS.get(platform)
        if not crawler_class:
            raise ValueError(f"Invalid Media Platform: {platform}")
        return crawler_class()


def load_user_ids_from_json(file_path: Path) -> Set[str]:
    """从JSON文件中加载user_id列表"""
    user_ids = set()
    try:
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 数据是数组格式，遍历每个元素提取user_id
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'user_id' in item:
                            user_id = item['user_id']
                            if user_id:
                                user_ids.add(str(user_id))
            print(f"从 {file_path.name} 加载了 {len(user_ids)} 个用户ID")
        else:
            print(f"文件 {file_path} 不存在")
    except Exception as e:
        print(f"读取文件 {file_path} 时出错: {e}")
    return user_ids


def load_all_user_ids() -> List[str]:
    """读取并合并所有JSON文件中的user_id，去重后返回"""
    json_files = [
        project_root / "data" / "xhs" / "json" / "detail_contents_蚂蚁_黑卡_before_add.json",
        project_root / "data" / "xhs" / "json" / "detail_comments_蚂蚁_黑卡_before_add.json",
        project_root / "data" / "xhs" / "json" / "detail_comments_蚂蚁_黑卡.json"
    ]
    
    all_user_ids = set()
    
    for json_file in json_files:
        user_ids = load_user_ids_from_json(json_file)
        all_user_ids.update(user_ids)
    
    print(f"\n总共收集到 {len(all_user_ids)} 个唯一用户ID")
    return sorted(list(all_user_ids))


def load_progress() -> dict:
    """加载断点续传进度"""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                progress = json.load(f)
                print(f"加载断点续传进度: 已完成 {progress.get('completed_count', 0)} 个用户")
                return progress
        except Exception as e:
            print(f"加载进度文件失败: {e}")
    return {
        'completed_user_ids': [],
        'completed_count': 0,
        'last_update': None
    }


def save_progress(completed_user_ids: List[str]):
    """保存断点续传进度"""
    progress = {
        'completed_user_ids': completed_user_ids,
        'completed_count': len(completed_user_ids),
        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    try:
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
        print(f"进度已保存: {len(completed_user_ids)} 个用户已完成")
    except Exception as e:
        print(f"保存进度失败: {e}")


async def crawl_creators(user_ids: List[str]):
    """使用creator模式爬取用户主页信息"""
    # 加载进度
    progress = load_progress()
    completed_user_ids = set(progress.get('completed_user_ids', []))
    
    # 过滤出未完成的用户ID
    remaining_user_ids = [uid for uid in user_ids if uid not in completed_user_ids]
    
    if not remaining_user_ids:
        print("所有用户都已爬取完成！")
        return
    
    print(f"\n开始爬取 {len(remaining_user_ids)} 个用户主页（剩余未完成的）")
    print(f"已完成: {len(completed_user_ids)} 个")
    
    # 临时保存原始配置
    original_crawler_type = config.CRAWLER_TYPE
    original_creator_urls = getattr(config, 'XHS_CREATOR_ID_LIST', [])
    original_enable_media = config.ENABLE_GET_MEIDAS
    original_max_notes = config.CRAWLER_MAX_NOTES_COUNT
    
    # 设置为creator模式，禁用图片和视频下载，不爬取帖子
    config.CRAWLER_TYPE = "creator"
    config.ENABLE_GET_MEIDAS = False  # 禁用媒体下载（图片和视频）
    config.CRAWLER_MAX_NOTES_COUNT = 0  # 不爬取帖子内容
    print("已禁用图片和视频下载，只保存creator信息，不爬取帖子")
    
    # 分批处理用户ID，每次处理一批
    batch_size = 10  # 每批处理5个用户（减少批次大小以提高稳定性）
    
    for i in range(0, len(remaining_user_ids), batch_size):
        batch = remaining_user_ids[i:i+batch_size]
        print(f"\n处理第 {i//batch_size + 1} 批，共 {len(batch)} 个用户")
        print(f"用户ID: {', '.join(batch[:3])}{'...' if len(batch) > 3 else ''}")
        
        # 构建creator URL列表（小红书需要完整的URL）
        # 注意：这里使用简化的URL格式，实际爬取时爬虫会处理
        creator_urls = [f"https://www.xiaohongshu.com/user/profile/{uid}" for uid in batch]
        config.XHS_CREATOR_ID_LIST = creator_urls
        
        # 初始化并运行爬虫
        _crawler = CrawlerFactory.create_crawler(platform=config.PLATFORM)
        crawler_type_var.set(config.CRAWLER_TYPE)
        
        try:
            await _crawler.start()
            
            # 标记这批用户为已完成
            completed_user_ids.update(batch)
            save_progress(list(completed_user_ids))
            
            print(f"第 {i//batch_size + 1} 批完成，总进度: {len(completed_user_ids)}/{len(user_ids)}")
            
            # 短暂休息，避免请求过于频繁
            if i + batch_size < len(remaining_user_ids):
                print(f"等待 {sleep_sec} 秒后继续下一批...")
                await asyncio.sleep(sleep_sec)
                
        except Exception as e:
            print(f"爬取第 {i//batch_size + 1} 批时出错: {e}")
            import traceback
            traceback.print_exc()
            # 即使出错也保存进度
            save_progress(list(completed_user_ids))
            # 继续下一批
            print("继续处理下一批...")
            continue
    
    # 恢复原始配置
    config.CRAWLER_TYPE = original_crawler_type
    config.XHS_CREATOR_ID_LIST = original_creator_urls
    config.ENABLE_GET_MEIDAS = original_enable_media
    config.CRAWLER_MAX_NOTES_COUNT = original_max_notes
    
    print(f"\n爬取完成！总共完成 {len(completed_user_ids)} 个用户")


async def main():
    print("=" * 60)
    print("个人主页爬取工具")
    print("=" * 60)
    
    # 1. 读取并合并JSON，去重
    print("\n步骤1: 读取并合并用户ID...")
    user_ids = load_all_user_ids()
    
    if not user_ids:
        print("未找到任何用户ID，请检查JSON文件！")
        return
    
    # 2. 开始爬取用户主页（带断点续传）
    print("\n步骤2: 开始爬取用户主页...")
    await crawl_creators(user_ids)
    
    print("\n" + "=" * 60)
    print("程序执行完毕！")
    print("=" * 60)


if __name__ == '__main__':
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n程序执行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


