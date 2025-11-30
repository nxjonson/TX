import re
import requests
from pathlib import Path

# --- 配置 ---
source1_url = "https://raw.githubusercontent.com/judy-gotv/iptv/refs/heads/main/smart.m3u"
source1_file = "/tmp/smart.m3u"
allowed_group1 = "GPT-台湾"

source2_url = "http://2099.tv12.xyz/list.txt"
source2_file = "/tmp/4gtv_list.txt"
source2_group = "4Gtv"  # 纯文本URL列表的默认分组

output_file = "1.m3u"
# --- 配置结束 ---

def download_file(url, save_path):
    try:
        print(f"Downloading {url}...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            f.write(response.content)
        print(f"Successfully downloaded to {save_path}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"ERROR downloading {url}: {e}")
        return False

def parse_m3u_robust(file_path, allowed_group):
    """解析标准 M3U 文件（带 #EXTINF 标签）"""
    entries = []
    group_title_regex = re.compile(r'group-title\s*=\s*["\']([^"\']+)["\']')
    
    try:
        encodings = ['utf-8', 'gbk', 'gb18030', 'latin-1']
        content = None
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.readlines()
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            print(f"Error: Could not decode {file_path}")
            return entries

        extinf_line = ""
        for line in content:
            if line.startswith("#EXTINF:"):
                match = group_title_regex.search(line)
                if match and match.group(1) == allowed_group:
                    extinf_line = line
            elif extinf_line and line.strip() and not line.strip().startswith("#"):
                entries.append(f"{extinf_line}{line}")
                extinf_line = ""
            else:
                if not line.startswith("#EXTINF:"):
                    extinf_line = ""
    except FileNotFoundError:
        print(f"Warning: Source file not found at {file_path}")
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
    return entries

def parse_plain_text_urls(file_path, group_name):
    """解析纯文本 URL 列表（每行格式：频道名,URL），提取真实频道名"""
    entries = []
    try:
        encodings = ['utf-8', 'gbk', 'gb18030', 'latin-1']
        content = None
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.readlines()
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            print(f"Error: Could not decode {file_path}")
            return entries

        for line in content:
            line = line.strip()
            # 1. 过滤无效行：空行、注释行、分组标题行（含,#genre#）
            if not line or line.startswith("#") or ",#genre#" in line:
                continue
            # 2. 必须包含逗号（频道名,URL 格式）
            if "," not in line:
                continue
            # 3. 分割频道名和URL（只分割一次）
            channel_name, url = line.split(",", 1)
            channel_name = channel_name.strip()
            url = url.strip()
            # 4. 校验URL有效性（必须以http开头，长度合理）
            if not (url.startswith(("http://", "https://")) and len(url) > 10):
                continue
            # 5. 过滤无意义的频道名（如分组名、太短的名称）
            if channel_name in ["4Gtv", "港台", "内地", "国外"] or len(channel_name) < 2:
                continue
            # 构造标准 M3U 格式
            extinf_line = f'#EXTINF:-1 group-title="{group_name}",{channel_name}\n'
            entries.append(f"{extinf_line}{url}\n")
    except FileNotFoundError:
        print(f"Warning: Source file not found at {file_path}")
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
    return entries

# 下载文件
download_success = True
if not download_file(source1_url, source1_file):
    download_success = False
if not download_file(source2_url, source2_file):
    download_success = False

if not download_success:
    print("Some files failed to download. Exiting.")
    exit(1)

# 读取旧文件URL去重
existing_urls = set()
output_path = Path(output_file)
file_header = "#EXTM3U x-tvg-url=\"https://epg.tv.darwinchow.com/epg.xml\"\n"  # 保留原文件的EPG配置

if output_path.exists():
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # 保留原文件头部（如果存在）
            for line in lines:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith("#"):
                    existing_urls.add(stripped_line)
    except Exception as e:
        print(f"Error reading {output_file}: {e}")
else:
    print(f"'{output_file}' not found, creating new.")

# --- 处理第一个源（标准 M3U）---
print(f"--- Processing {source1_file} for group '{allowed_group1}' ---")
new_entries_source1 = parse_m3u_robust(source1_file, allowed_group1)
print(f"Found {len(new_entries_source1)} entries in '{allowed_group1}'.")

# --- 处理第二个源（纯文本 URL 列表）---
print(f"--- Processing {source2_file} as plain text URLs (group: '{source2_group}') ---")
new_entries_source2 = parse_plain_text_urls(source2_file, source2_group)
print(f"Found {len(new_entries_source2)} entries in '{source2_group}'.")

# 合并去重（在两个分组之间添加两个空行）
all_new_entries = new_entries_source1
if new_entries_source1 and new_entries_source2:
    all_new_entries.append("\n\n")  # 分组间添加两个空行
all_new_entries += new_entries_source2

entries_to_write = []
for entry in all_new_entries:
    # 空行无需去重，直接添加
    if entry.strip() == "":
        entries_to_write.append(entry)
        continue
    # URL去重
    url = entry.splitlines()[-1].strip()
    if url not in existing_urls:
        entries_to_write.append(entry)
        existing_urls.add(url)

# 写入文件（确保头部唯一）
if entries_to_write:
    with open(output_file, "a+", encoding="utf-8") as f_out:
        f_out.seek(0)
        first_line = f_out.readline()
        # 如果文件为空或无头部，添加标准头部
        if not first_line.startswith("#EXTM3U"):
            f_out.write(file_header)
        
        f_out.seek(0, 2)  # 移动到文件末尾
        for entry in entries_to_write:
            f_out.write(entry)
    print(f"\nSUCCESS: Appended {len(entries_to_write)} new entries to '{output_file}'.")
else:
    print("\nINFO: No new unique entries found.")