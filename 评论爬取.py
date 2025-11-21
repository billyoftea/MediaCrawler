# 1.帖子本体数据读取
import json
import asyncio
import os
import time
from datetime import datetime
from pathlib import Path

# MediaCrawler相关导入
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from media_platform.xhs import XiaoHongShuCrawler
from tools import utils

# 配置文件路径
POST_DATA_PATH = r"C:\Users\Lenovo\Desktop\TenCent_Fintech\MediaCrawler\data\xhs\json\posts_to_crawl_蚂蚁_黑卡.json"
PROGRESS_FILE = r"C:\Users\Lenovo\Desktop\TenCent_Fintech\MediaCrawler\comment_crawl_progress_add.json"
COMMENT_OUTPUT_DIR = r"C:\Users\Lenovo\Desktop\TenCent_Fintech\MediaCrawler\data\xhs\comments"

# 确保输出目录存在
os.makedirs(COMMENT_OUTPUT_DIR, exist_ok=True)

# 读取帖子数据
with open(POST_DATA_PATH, "r", encoding="utf-8") as file:
    post_data = json.load(file)

print(f"共加载 {len(post_data)} 条帖子数据")

# 将post_data转换为以note_id为键的字典，方便后续查找
post_dict = {post['note_id']: post for post in post_data}

def load_progress():
    """加载爬取进度"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'notes_progress': {},  # {note_id: {'comment_ids': [], 'status': 'pending/in_progress/completed', 'last_update': timestamp}}
        'last_note_id': None,
        'last_update': None
    }

def save_progress(note_id, comment_ids=None, status='completed'):
    """保存爬取进度
    
    Args:
        note_id: 笔记ID
        comment_ids: 已爬取的评论ID列表
        status: 状态 (pending/in_progress/completed)
    """
    progress = load_progress()
    
    # 更新笔记进度
    if note_id not in progress['notes_progress']:
        progress['notes_progress'][note_id] = {
            'comment_ids': [],
            'status': 'pending',
            'last_update': None
        }
    
    # 更新评论ID列表
    if comment_ids is not None:
        progress['notes_progress'][note_id]['comment_ids'] = comment_ids
    
    # 更新状态
    progress['notes_progress'][note_id]['status'] = status
    progress['notes_progress'][note_id]['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    progress['last_note_id'] = note_id
    progress['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    
    completed_count = len([n for n in progress['notes_progress'].values() if n['status'] == 'completed'])
    comment_count = len(progress['notes_progress'][note_id]['comment_ids']) if comment_ids else 0
    print(f"进度已保存: {completed_count}/{len(post_data)} 完成 | 笔记 {note_id}: {comment_count} 条评论")

def get_note_comments(note_id):
    """获取已爬取的评论ID列表"""
    progress = load_progress()
    if note_id in progress['notes_progress']:
        return progress['notes_progress'][note_id].get('comment_ids', [])
    return []

async def crawl_comments_for_notes():
    """爬取所有帖子的评论"""
    # 加载进度
    progress = load_progress()
    
    # 获取已完成的笔记ID
    completed_notes = set([nid for nid, info in progress['notes_progress'].items() if info['status'] == 'completed'])
    
    # 过滤出还未爬取的帖子
    remaining_posts = [post for post in post_data if post['note_id'] not in completed_notes]
    
    print(f"已完成: {len(completed_notes)} 条")
    print(f"剩余: {len(remaining_posts)} 条")
    
    # 显示部分笔记的评论数量
    for note_id, info in list(progress['notes_progress'].items())[:3]:
        print(f"  - {note_id}: {len(info.get('comment_ids', []))} 条评论 ({info['status']})")
    
    if not remaining_posts:
        print("所有帖子评论已爬取完成！")
        return
    
    # 临时修改config配置用于评论爬取
    original_crawler_type = config.CRAWLER_TYPE
    original_note_list = config.XHS_SPECIFIED_NOTE_URL_LIST if hasattr(config, 'XHS_SPECIFIED_NOTE_URL_LIST') else []
    original_enable_comments = config.ENABLE_GET_COMMENTS
    
    try:
        # 设置为详情爬取模式
        config.CRAWLER_TYPE = "detail"
        config.ENABLE_GET_COMMENTS = True
        config.ENABLE_GET_SUB_COMMENTS = True
        
        # 初始化爬虫
        crawler = XiaoHongShuCrawler()
        
        for idx, post in enumerate(remaining_posts, 1):
            note_id = post['note_id']
            xsec_token = post.get('xsec_token', '')
            xsec_source = post.get('xsec_source', '')
            
            print(f"\n[{idx}/{len(remaining_posts)}] 开始爬取笔记 {note_id} 的评论...")
            
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # 标记为进行中
                    save_progress(note_id, status='in_progress')
                    
                    # 构造完整的笔记URL
                    note_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source={xsec_source}"
                    
                    # 设置当前要爬取的笔记
                    config.XHS_SPECIFIED_NOTE_URL_LIST = [note_url]
                    
                    # 启动爬虫爬取该笔记
                    await crawler.start()
                    
                    # 从存储中读取实际爬取到的评论ID
                    from store.xhs import XhsStoreFactory
                    store = XhsStoreFactory.create_store()
                    crawled_comment_ids = []
                    
                    # 根据存储类型读取评论ID
                    if hasattr(store, 'writer') and hasattr(store.writer, 'existing_ids'):
                        # JSON/CSV存储方式
                        comment_file = store.writer._get_file_path('json', 'comments')
                        if os.path.exists(comment_file) and os.path.getsize(comment_file) > 0:
                            try:
                                with open(comment_file, 'r', encoding='utf-8') as f:
                                    all_comments = json.load(f)
                                    crawled_comment_ids = [
                                        c['comment_id'] for c in all_comments 
                                        if isinstance(c, dict) and c.get('note_id') == note_id
                                    ]
                            except Exception as e:
                                print(f"读取评论文件时出错: {e}")
                    
                    # 保存进度（标记为完成）
                    save_progress(note_id, comment_ids=crawled_comment_ids, status='completed')
                    
                    print(f"笔记 {note_id} 评论爬取完成，共 {len(crawled_comment_ids)} 条评论")
                    
                    # 间隔休息，避免被限制
                    # sleep_time = config.CRAWLER_MAX_SLEEP_SEC
                    sleep_time = 8
                    print(f"休息 {sleep_time} 秒...")
                    await asyncio.sleep(sleep_time)
                    
                    # 成功完成，跳出重试循环
                    break
                    
                except Exception as e:
                    error_msg = str(e)
                    retry_count += 1
                    
                    # 检测是否遇到验证码或限制
                    if "验证" in error_msg or "captcha" in error_msg.lower() or "限制" in error_msg:
                        print(f"\n⚠️ 检测到验证码或访问限制 (重试 {retry_count}/{max_retries})")
                        print(f"错误信息: {error_msg}")
                        
                        if retry_count < max_retries:
                            wait_time = 30 * retry_count  # 递增等待时间
                            print(f"等待 {wait_time} 秒后重试...")
                            await asyncio.sleep(wait_time)
                            
                            # 重新初始化爬虫，重新登录
                            try:
                                if hasattr(crawler, 'close'):
                                    await crawler.close()
                                crawler = XiaoHongShuCrawler()
                            except Exception:
                                pass
                        else:
                            print(f"笔记 {note_id} 重试次数已达上限，跳过该笔记")
                            # 标记为待处理状态，下次运行时继续
                            save_progress(note_id, status='pending')
                    else:
                        # 其他错误，直接记录并继续下一个
                        print(f"爬取笔记 {note_id} 时出错: {error_msg}")
                        break
        
        print("\n✅ 评论爬取任务完成！")
        
    except Exception as e:
        print(f"\n❌ 爬虫运行出错: {e}")
        
    finally:
        # 恢复原始配置
        config.CRAWLER_TYPE = original_crawler_type
        config.XHS_SPECIFIED_NOTE_URL_LIST = original_note_list
        config.ENABLE_GET_COMMENTS = original_enable_comments
        
        # 关闭爬虫
        if hasattr(crawler, 'close'):
            await crawler.close()

def main():
    """主函数"""
    print("=" * 60)
    print("小红书评论爬取工具 (带断点续传)")
    print("=" * 60)
    
    try:
        # 运行异步爬虫
        asyncio.run(crawl_comments_for_notes())
    except KeyboardInterrupt:
        print("\n\n用户中断程序")
    except Exception as e:
        print(f"\n\n程序异常: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n程序结束")

if __name__ == "__main__":
    main()