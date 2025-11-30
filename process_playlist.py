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
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return True
    except requests.exceptions.RequestException:
        return False

def parse_m3u(file_path, allowed_group):
    entries = []
    group_regex = re.compile(r'group-title\s*=\s*["\']([^"\']+)["\']')
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        extinf_line = ""
        for line in lines:
            if line.startswith("#EXTINF:"):
                match = group_regex.search(line)
                if match and match.group(1) == allowed_group:
                    extinf_line = line
            elif extinf_line and line.strip() and not line.startswith("#"):
                # 过滤 GPT-台湾 分组中含“新闻”的频道
                if KEYWORD in extinf_line:
                    entries.append(f"{extinf_line}{line}")
                extinf_line = ""
    except:
        pass
    return entries

def parse_plain_text(file_path, group_name):
    entries = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # 只处理 4Gtv,#genre# 分组下的内容
        in_4gtv_group = False
        for line in lines:
            line = line.strip()
            # 标记分组开始/结束
            if line == "4Gtv,#genre#":
                in_4gtv_group = True
                continue
            if in_4gtv_group and (line.endswith(",#genre#") or not line):
                break  # 遇到下一个分组或空行，停止处理
            
            if in_4gtv_group and line:
                if not line.startswith("#") and "," in line:
                    channel_name, url = line.split(",", 1)
                    channel_name = channel_name.strip()
                    url = url.strip()
                    # 过滤条件：含新闻关键词 + 有效URL + 无意义频道名
                    if (KEYWORD in channel_name 
                        and url.startswith(("http://", "https://")) 
                        and channel_name not in INVALID_CHANNEL_NAMES 
                        and len(channel_name) >= 2):
                        entries.append(f'#EXTINF:-1 group-title="{group_name}",{channel_name}\n{url}\n')
    except:
        pass
    return entries

# 下载两个源文件
if not (download_file(source1_url, source1_file) and download_file(source2_url, source2_file)):
    exit(1)

# 解析两个源的有效条目（仅含新闻频道）
entries1 = parse_m3u(source1_file, allowed_group1)  # GPT-台湾 新闻频道
entries2 = parse_plain_text(source2_file, source2_group)  # 4Gtv 新闻频道

# 读取现有URL去重
existing_urls = set()
if Path(output_file).exists():
    with open(output_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                existing_urls.add(line)

# 合并条目（分组间空两行）
final_entries = []
for entry in entries1:
    url = entry.splitlines()[-1].strip()
    if url not in existing_urls:
        final_entries.append(entry)
        existing_urls.add(url)

if entries1 and entries2:
    final_entries.append("\n\n")  # 分组间空两行

for entry in entries2:
    url = entry.splitlines()[-1].strip()
    if url not in existing_urls:
        final_entries.append(entry)
        existing_urls.add(url)

# 写入文件（确保头部正确）
with open(output_file, "w", encoding="utf-8") as f:
    f.write(file_header)
    f.writelines(final_entries)

print(f"生成完成：{len(entries1)} 个 GPT-台湾 新闻频道，{len(entries2)} 个 4Gtv 新闻频道")