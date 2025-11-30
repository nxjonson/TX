import re
import requests
from pathlib import Path
import os

# --- 核心配置 ---
source1_url = "https://raw.githubusercontent.com/judy-gotv/iptv/refs/heads/main/smart.m3u"
source1_file = "/tmp/smart.m3u"
allowed_group1 = "GPT-台湾"

source2_url = "http://2099.tv12.xyz/list.txt"
source2_file = "/tmp/4gtv_list.txt"
source2_group = "4Gtv"
INVALID_CHANNEL_NAMES = ["4Gtv", "港台", "内地", "国外"]
KEYWORD = "新闻"
output_file = "1.m3u"
file_header = "#EXTM3U x-tvg-url=\"https://epg.tv.darwinchow.com/epg.xml\"\n"
# --- 配置结束 ---

# 强制创建输出文件（避免空文件）
open(output_file, 'a').close()

def download_file(url, save_path):
    try:
        print(f"[下载] 正在获取 {url}...")
        response = requests.get(url, timeout=20, verify=False)  # 跳过SSL验证，避免下载失败
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            f.write(response.content)
        print(f"[下载] 成功：{save_path}")
        return True
    except Exception as e:
        print(f"[下载] 失败：{url} → {str(e)}")
        return False

def parse_m3u(file_path, allowed_group):
    entries = []
    group_regex = re.compile(r'group-title\s*=\s*["\']([^"\']+)["\']')
    try:
        encodings = ['utf-8', 'gbk', 'gb18030', 'latin-1']
        lines = None
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    lines = f.readlines()
                break
            except:
                continue
        if lines is None:
            print(f"[解析] M3U文件无法解码")
            return entries
        
        extinf_line = ""
        for line in lines:
            if line.startswith("#EXTINF:"):
                match = group_regex.search(line)
                if match and match.group(1) == allowed_group:
                    extinf_line = line
            elif extinf_line and line.strip() and not line.startswith("#"):
                if KEYWORD in extinf_line:
                    entries.append(f"{extinf_line}{line}")
                extinf_line = ""
        print(f"[解析] GPT-台湾 新闻频道：{len(entries)} 个")
    except Exception as e:
        print(f"[解析] M3U失败：{str(e)}")
    return entries

def parse_plain_text(file_path, group_name):
    entries = []
    try:
        encodings = ['utf-8', 'gbk', 'gb18030', 'latin-1']
        lines = None
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    lines = f.readlines()
                break
            except:
                continue
        if lines is None:
            print(f"[解析] 纯文本文件无法解码")
            return entries
        
        in_4gtv_group = False
        for line in lines:
            line = line.strip()
            if line == "4Gtv,#genre#":
                in_4gtv_group = True
                continue
            if in_4gtv_group and line.endswith(",#genre#"):
                break
            if in_4gtv_group and line:
                if not line.startswith("#") and "," in line:
                    try:
                        channel_name, url = line.split(",", 1)
                        channel_name = channel_name.strip()
                        url = url.strip()
                        if (KEYWORD in channel_name 
                            and url.startswith(("http://", "https://")) 
                            and channel_name not in INVALID_CHANNEL_NAMES 
                            and len(channel_name) >= 2):
                            entries.append(f'#EXTINF:-1 group-title="{group_name}",{channel_name}\n{url}\n')
                    except:
                        continue
        print(f"[解析] 4Gtv 新闻频道：{len(entries)} 个")
    except Exception as e:
        print(f"[解析] 纯文本失败：{str(e)}")
    return entries

# 主逻辑
print("="*50)
print("=== 开始处理 IPTV 播放列表 ===")
print("="*50)

# 下载文件（允许单个源失败，至少保留一个分组）
download1 = download_file(source1_url, source1_file)
download2 = download_file(source2_url, source2_file)
if not download1 and not download2:
    print("=== 所有源下载失败，写入默认提示 ===")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(file_header)
        f.write("# 所有源下载失败，暂无频道\n")
    exit(1)

# 解析频道
entries1 = parse_m3u(source1_file, allowed_group1) if download1 else []
entries2 = parse_plain_text(source2_file, source2_group) if download2 else []

# 去重
existing_urls = set()
try:
    with open(output_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                existing_urls.add(line)
except:
    existing_urls = set()
print(f"[去重] 已存在有效URL：{len(existing_urls)} 个")

# 合并条目
final_entries = []
for entry in entries1:
    url = entry.splitlines()[-1].strip()
    if url not in existing_urls:
        final_entries.append(entry)
        existing_urls.add(url)

if entries1 and entries2:
    final_entries.append("\n\n")

for entry in entries2:
    url = entry.splitlines()[-1].strip()
    if url not in existing_urls:
        final_entries.append(entry)
        existing_urls.add(url)

# 强制写入（即使只有一个分组，也确保文件有内容）
with open(output_file, "w", encoding="utf-8") as f:
    f.write(file_header)
    if final_entries:
        f.writelines(final_entries)
    else:
        f.write("# 未抓取到有效新闻频道，请检查源文件\n")

print(f"\n" + "="*50)
print(f"=== 处理完成 ===")
print(f"最终写入频道数：{len(final_entries)}")
print(f"文件大小：{os.path.getsize(output_file)} 字节")
print("="*50)