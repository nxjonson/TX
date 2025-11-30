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
# 无效频道名列表（用于清理旧条目）
INVALID_CHANNEL_NAMES = ["4Gtv", "港台", "内地", "国外"]
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
            if channel_name in INVALID_CHANNEL_NAMES or len(channel_name) < 2:
                continue
            # 构造标准 M3U 格式
            extinf_line = f'#EXTINF:-1 group-title="{group_name}",{channel_name}\n'
            entries.append(f"{extinf_line}{url}\n")
    except FileNotFoundError:
        print(f"Warning: Source file not found at {file_path}")
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
    return entries

def clean_old_invalid_entries(output_file):
    """清理旧文件中的无效条目（4Gtv、港台等）"""
    if not Path(output_file).exists():
        return set()  # 文件不存在，返回空集合
    
    valid_entries = []
    valid_urls = set()
    current_extinf = ""
    
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                line_stripped = line.strip()
                if line.startswith("#EXTINF:"):
                    # 检查是否为无效频道名
                    channel_match = re.search(r',([^,]+)$', line)
                    if channel_match and channel_match.group(1) in INVALID_CHANNEL_NAMES:
                        current_extinf = ""  # 标记为无效，后续URL不保留
                    else:
                        current_extinf = line
                elif line_stripped and not line_stripped.startswith("#") and current_extinf:
                    # 有效URL，添加到列表和去重集合
                    valid_entries.append(f"{current_extinf}{line}")
                    valid_urls.add(line_stripped)
                elif line.startswith("#EXTM3U"):
                    # 保留文件头部
                    valid_entries.append(line)
    except Exception as e:
        print(f"Error cleaning old entries: {e}")
        return set()
    
    # 重写清理后的文件
    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(valid_entries)
    
    print(f"Cleaned old invalid entries. Kept {len(valid_entries)} valid lines.")
    return valid_urls

# 下载文件
download_success = True
if not download_file(source1_url, source1_file):
    download_success = False
if not download_file(source2_url, source2_file):
    download_success = False

if not download_success:
    print("Some files failed to download. Exiting.")
    exit(1)

# 清理旧文件中的无效条目，并获取有效URL（用于去重）
existing_urls = clean_old_invalid_entries(output_file)
output_path = Path(output_file)
file_header = "#EXTM3U x-tvg-url=\"https://epg.tv.darwinchow.com/epg.xml\"\n"

# 确保文件头部存在
if output_path.exists():
    with open(output_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        if not lines or not lines[0].startswith("#EXTM3U"):
            lines.insert(0, file_header)
            with open(output_file, "w", encoding="utf-8") as f_out:
                f_out.writelines(lines)
else:
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(file_header)
    print(f"'{output_file}' not found, created new file with header.")

# --- 处理第一个源（标准 M3U）---
print(f"--- Processing {source1_file} for group '{allowed_group1}' ---")
new_entries_source1 = parse_m3u_robust(source1_file, allowed_group1)
print(f"Found {len(new_entries_source1)} entries in '{allowed_group1}'.")

# --- 处理第二个源（纯文本 URL 列表）---
print(f"--- Processing {source2_file} as plain text URLs (group: '{source2_group}') ---")
new_entries_source2 = parse_plain_text_urls(source2_file, source2_group)
print(f"Found {len(new_entries_source2)} entries in '{source2_group}'.")

# 合并条目（确保分组间空两行）
final_entries = []
# 添加第一个分组有效条目
final_entries.extend(new_entries_source1)
# 两个分组都有内容时，插入两个空行
if new_entries_source1 and new_entries_source2:
    final_entries.append("\n\n")
# 添加第二个分组有效条目
final_entries.extend(new_entries_source2)

# 去重并收集新条目
entries_to_write = []
for entry in final_entries:
    if entry.strip() == "":
        entries_to_write.append(entry)
        continue
    url = entry.splitlines()[-1].strip()
    if url not in existing_urls:
        entries_to_write.append(entry)
        existing_urls.add(url)

# 追加新条目到文件
if entries_to_write:
    with open(output_file, "a", encoding="utf-8") as f_out:
        f_out.writelines(entries_to_write)
    print(f"\nSUCCESS: Appended {len(entries_to_write)} new entries to '{output_file}'.")
else:
    print("\nINFO: No new unique entries found.")