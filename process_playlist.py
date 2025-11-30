import re
import requests
from pathlib import Path

# --- 核心配置 ---
source1_url = "https://raw.githubusercontent.com/judy-gotv/iptv/refs/heads/main/smart.m3u"
source1_file = "/tmp/smart.m3u"
allowed_group1 = "GPT-台湾"

source2_url = "http://2099.tv12.xyz/list.txt"
source2_file = "/tmp/4gtv_list.txt"
source2_group = "4Gtv"
INVALID_CHANNEL_NAMES = ["4Gtv", "港台", "内地", "国外"]
KEYWORD = "新闻"  # 只保留含该关键词的频道
output_file = "1.m3u"
file_header = "#EXTM3U x-tvg-url=\"https://epg.tv.darwinchow.com/epg.xml\"\n"
# --- 配置结束 ---

def download_file(url, save_path):
    try:
        print(f"正在下载 {url}...")
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            f.write(response.content)
        print(f"下载成功：{save_path}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"下载失败：{url} → {str(e)}")
        return False

def parse_m3u(file_path, allowed_group):
    entries = []
    group_regex = re.compile(r'group-title\s*=\s*["\']([^"\']+)["\']')
    try:
        # 多编码尝试，避免解码失败
        encodings = ['utf-8', 'gbk', 'gb18030', 'latin-1']
        lines = None
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    lines = f.readlines()
                break
            except UnicodeDecodeError:
                continue
        if lines is None:
            print(f"解析失败：{file_path} 无法解码")
            return entries
        
        extinf_line = ""
        for line in lines:
            if line.startswith("#EXTINF:"):
                match = group_regex.search(line)
                if match and match.group(1) == allowed_group:
                    extinf_line = line
            elif extinf_line and line.strip() and not line.startswith("#"):
                # 过滤含新闻关键词的频道
                if KEYWORD in extinf_line:
                    entries.append(f"{extinf_line}{line}")
                extinf_line = ""
        print(f"GPT-台湾 新闻频道数量：{len(entries)}")
    except Exception as e:
        print(f"解析 M3U 失败：{str(e)}")
    return entries

def parse_plain_text(file_path, group_name):
    entries = []
    try:
        # 多编码尝试
        encodings = ['utf-8', 'gbk', 'gb18030', 'latin-1']
        lines = None
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    lines = f.readlines()
                break
            except UnicodeDecodeError:
                continue
        if lines is None:
            print(f"解析失败：{file_path} 无法解码")
            return entries
        
        in_4gtv_group = False
        for line in lines:
            line = line.strip()
            # 标记 4Gtv 分组开始
            if line == "4Gtv,#genre#":
                in_4gtv_group = True
                continue
            # 分组结束条件：遇到下一个分组标记（不含空行！）
            if in_4gtv_group and line.endswith(",#genre#"):
                break
            # 只处理分组内的有效条目（跳过空行，但不终止）
            if in_4gtv_group and line:
                if not line.startswith("#") and "," in line:
                    channel_name, url = line.split(",", 1)
                    channel_name = channel_name.strip()
                    url = url.strip()
                    # 过滤条件
                    if (KEYWORD in channel_name 
                        and url.startswith(("http://", "https://")) 
                        and channel_name not in INVALID_CHANNEL_NAMES 
                        and len(channel_name) >= 2):
                        entries.append(f'#EXTINF:-1 group-title="{group_name}",{channel_name}\n{url}\n')
        print(f"4Gtv 新闻频道数量：{len(entries)}")
    except Exception as e:
        print(f"解析纯文本失败：{str(e)}")
    return entries

# 主逻辑
print("=== 开始处理 IPTV 播放列表 ===")
# 下载文件
if not (download_file(source1_url, source1_file) and download_file(source2_url, source2_file)):
    print("下载失败，退出程序")
    exit(1)

# 解析频道
entries1 = parse_m3u(source1_file, allowed_group1)
entries2 = parse_plain_text(source2_file, source2_group)

# 去重
existing_urls = set()
if Path(output_file).exists():
    with open(output_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                existing_urls.add(line)
    print(f"已存在的有效 URL 数量：{len(existing_urls)}")

# 合并条目
final_entries = []
# 添加 GPT-台湾 频道
for entry in entries1:
    url = entry.splitlines()[-1].strip()
    if url not in existing_urls:
        final_entries.append(entry)
        existing_urls.add(url)

# 分组间空两行
if entries1 and entries2:
    final_entries.append("\n\n")

# 添加 4Gtv 频道
for entry in entries2:
    url = entry.splitlines()[-1].strip()
    if url not in existing_urls:
        final_entries.append(entry)
        existing_urls.add(url)

# 写入文件
with open(output_file, "w", encoding="utf-8") as f:
    f.write(file_header)
    f.writelines(final_entries)

print(f"\n=== 处理完成 ===")
print(f"最终写入频道总数：{len(final_entries)}")
print(f"文件路径：{output_file}")