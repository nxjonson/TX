import os
import re
import argparse

FILE1 = "2024.json"
LIVE_FILE = "li.m3u"
OK_DIR = "./ok"

# 从 live.m3u 第二行提取 UA：
UA_PATTERNS = [
    r'设置为\s*([^\s，,]+)',                    
    r'[Uu]ser-?[Aa]gent[:：]?\s*([^\s，,]+)',   
    r'\bUA\b[:：]?\s*([^\s，,]+)',             
]

PNG_OLD_PATH_PATTERN = r"\./ok/ok\d{4}\.png"
UA_VALUE_PATTERN = re.compile(r'("ua"\s*:\s*")([^"]*)(")')  

def read_file_lines(path):
    if not os.path.exists(path):
        print(f"[WARN] 文件未找到: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()

def write_file_lines(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)

def extract_ua_from_line(line):
    if not line:
        return None
    for pat in UA_PATTERNS:
        m = re.search(pat, line)
        if m:
            return m.group(1).strip()
    return None

def replace_ua_value_in_line6_or_file(path, new_ua):
    lines = read_file_lines(path)
    if not lines:
        return False, None, None

    # 先尝试第6行
    if len(lines) >= 6:
        line6 = lines[5]
        m6 = UA_VALUE_PATTERN.search(line6)
        if m6:
            old_val = m6.group(2)
            if old_val == new_ua:
                print(f"[INFO] UA 在 {path} 的第6行已与 live.m3u 一致，无需更新")
                return False, old_val, 'line6'
            new_line6 = UA_VALUE_PATTERN.sub(rf'\1{new_ua}\3', line6, count=1)
            if new_line6 != line6:
                lines[5] = new_line6
                write_file_lines(path, lines)
                print(f"[SYNC] 已在 {path} 的第6行更新 UA：{old_val} → {new_ua}")
                return True, old_val, 'line6'
            return False, old_val, 'line6'
        else:
            print(f"[INFO] {path} 的第6行未包含 ua 字段，改为在整文件内尝试一次替换")

    # 再尝试在整文件中替换首个 ua 值
    content = "".join(lines)
    m_any = UA_VALUE_PATTERN.search(content)
    if m_any:
        old_val = m_any.group(2)
        if old_val == new_ua:
            print(f"[INFO] {path} 文件内首个 UA 已与 live.m3u 一致，无需更新")
            return False, old_val, 'file'
        content_new = UA_VALUE_PATTERN.sub(rf'\1{new_ua}\3', content, count=1)
        if content_new != content:
            write_file_lines(path, content_new.splitlines(keepends=True))
            print(f"[SYNC] 已在 {path} 的文件内首个 UA 处更新：{old_val} → {new_ua}")
            return True, old_val, 'file'
        return False, old_val, 'file'
    else:
        print(f"[WARN] {path} 未发现任何 ua 字段，跳过 UA 替换")
        return False, None, None

def update_png_path(json_file, latest_png_path):
    lines = read_file_lines(json_file)
    if not lines:
        return False
    content = "".join(lines)
    if re.search(PNG_OLD_PATH_PATTERN, content):
        content_new = re.sub(PNG_OLD_PATH_PATTERN, latest_png_path, content)
        if content_new != content:
            write_file_lines(json_file, content_new.splitlines(keepends=True))
            print(f"[SYNC] PNG 路径已更新到 {json_file} -> {latest_png_path}")
            return True
        else:
            print(f"[INFO] {json_file} 中 PNG 路径已是最新")
            return False
    else:
        print(f"[INFO] {json_file} 中未检测到旧 PNG 路径，跳过替换")
        return False

def main(update_ua=False, update_png=False):
    changed = False
    ua_changed = False
    png_changed = False

    if update_ua:
        # ---- 读取 live.m3u 第二行并提取 UA ----
        ua = None
        live_lines = read_file_lines(LIVE_FILE)
        if len(live_lines) >= 2:
            line2 = live_lines[1].strip()
            ua = extract_ua_from_line(line2)
            if ua:
                print(f"[INFO] 从 live.m3u 提取到 UA: {ua}")
            else:
                print(f"[WARN] live.m3u 第二行未发现 UA 字符串，跳过 UA 同步")
        else:
            print("[WARN] live.m3u 少于 2 行，跳过 UA 更新")

        # ---- 同步 UA（仅 2024.json）----
        if ua:
            did, old, scope = replace_ua_value_in_line6_or_file(FILE1, ua)
            if did:
                changed = True
                ua_changed = True

    if update_png:
        # ---- 最新 PNG 文件同步 ----
        png_files = []
        if os.path.isdir(OK_DIR):
            png_files = [f for f in os.listdir(OK_DIR) if re.match(r"ok\d{4}\.png", f)]
        if not png_files:
            print("[INFO] ok 目录未找到 PNG 文件，跳过 PNG 同步")
        else:
            latest_png_full = max((os.path.join(OK_DIR, f) for f in png_files), key=os.path.getmtime)
            latest_png_path = latest_png_full.replace("\\", "/")
            print(f"[INFO] 最新 PNG 文件：{latest_png_path}")
            if update_png_path(FILE1, latest_png_path):
                changed = True
                png_changed = True

    # ---- 总结 ----
    if changed:
        print(f"[SUMMARY] 检测到变化：UA 更新={ua_changed}, PNG 更新={png_changed}")
    else:
        print("[SUMMARY] 未检测到任何变化，无需提交")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync JSON files with UA or PNG updates")
    parser.add_argument('--update-ua', action='store_true', help='Update UA in JSON files')
    parser.add_argument('--update-png', action='store_true', help='Update PNG path in JSON files')
    args = parser.parse_args()
    main(update_ua=args.update_ua, update_png=args.update_png)
