import os
import json
import datetime
import requests
from bs4 import BeautifulSoup

USERNAME = os.environ.get("EPROJECT_USER")
PASSWORD = os.environ.get("EPROJECT_PASS")

LOGIN_URL = "http://www.e-project.doae.go.th/loginPageAct.php"
CHOICE_PAGE_URL = "http://www.e-project.doae.go.th/home.php?page=rpt3_choice&gmod=Mas0503"
REPORT_BASE_URL = "http://www.e-project.doae.go.th/rpt3_choice-report.php"

def clean_num(val):
    if not val:
        return 0.0
    val_str = str(val).replace(',', '').strip()
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def get_all_projects_auto(session, headers):
    """
    ฟังก์ชันดึงรายชื่อและรหัสโครงการทั้งหมดจาก Dropdown ของหน้าฟอร์มโดยอัตโนมัติ
    """
    res = session.get(CHOICE_PAGE_URL, headers=headers)
    res.encoding = res.apparent_encoding or "tis-620"
    soup = BeautifulSoup(res.text, "html.parser")
    
    projects = []
    
    # ค้นหา select ของช่องโครงการ (ปกติ id หรือ name มักเป็น seByproj)
    proj_select = soup.find("select", {"name": "seByproj"}) or soup.find("select", {"id": "seByproj"})
    
    if not proj_select:
        # หากหาชื่อเฉพาะไม่เจอ ให้หา select ทุกอันแล้วดูว่ามี option หรือไม่
        selects = soup.find_all("select")
        for s in selects:
            options = s.find_all("option")
            if len(options) > 2:
                proj_select = s
                break

    if proj_select:
        for opt in proj_select.find_all("option"):
            val = opt.get("value", "").strip()
            text = opt.get_text(strip=True)
            # กรองเฉพาะ option ที่มีรหัสโครงการจริง (ตัดค่าว่างหรือคำว่า --เลือก-- ออก)
            if val and val != "0" and val != "":
                projects.append({"id": val, "name": text})
                
    print(f"ค้นพบโครงการในระบบอัตโนมัติทั้งหมด {len(projects)} โครงการ")
    return projects

def parse_project_table(html_content, project_name):
    """
    สกัดข้อมูลแถวกิจกรรมและงบประมาณจากตาราง HTML
    """
    soup = BeautifulSoup(html_content, "html.parser")
    rows = soup.find_all("tr")
    transformed_rows = []
    i = 0
    
    while i < len(rows):
        row = rows[i]
        cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        
        if len(cols) < 5 or "โครงการ" in cols[0] or "ผลรวม" in cols[0]:
            i += 1
            continue

        act_name = cols[0]
        act_unit = cols[1]
        
        if act_unit != "บาท":
            target = clean_num(cols[3]) if len(cols) > 3 else 0.0
            actual = clean_num(cols[4]) if len(cols) > 4 else 0.0
            p1 = clean_num(cols[5]) if len(cols) > 5 else 0.0
            
            transformed_rows.append({
                "โครงการ/กิจกรรม": f"{act_name} (KPI)",
                "หน่วยนับ": act_unit,
                "เป้าหมาย": target,
                "ผลการดำเนินงานสะสม": actual,
                "แผนไตรมาส1": p1,
                "ผลไตรมาส1": actual,
                "แผนไตรมาส2": clean_num(cols[9]) if len(cols) > 9 else 0.0,
                "ผลไตรมาส2": 0.0,
                "แผนไตรมาส3": 0.0,
                "ผลไตรมาส3": 0.0,
                "แผนไตรมาส4": 0.0,
                "ผลไตรมาส4": 0.0,
                "ปัญหาและอุปสรรค": "",
                "สถานะไตรมาส1": "เป็นไปตามแผน" if actual >= p1 and p1 > 0 else ("ยังไม่ดำเนินการ" if actual == 0 else "ล่าช้า")
            })

            # อ่านบรรทัดงบประมาณที่เป็น 'บาท' ที่อยู่ติดกัน
            if i + 1 < len(rows):
                next_cols = [c.get_text(strip=True) for c in rows[i+1].find_all(["td", "th"])]
                if len(next_cols) >= 5 and (next_cols[0] == "บาท" or next_cols[1] == "บาท"):
                    bg_target = clean_num(next_cols[2]) if next_cols[0] == "บาท" else clean_num(next_cols[3])
                    bg_actual = clean_num(next_cols[3]) if next_cols[0] == "บาท" else clean_num(next_cols[4])
                    bg_p1 = clean_num(next_cols[4]) if next_cols[0] == "บาท" else clean_num(next_cols[5])
                    
                    transformed_rows.append({
                        "โครงการ/กิจกรรม": f"งบประมาณ - {act_name}",
                        "หน่วยนับ": "บาท",
                        "เป้าหมาย": bg_target,
                        "ผลการดำเนินงานสะสม": bg_actual,
                        "แผนไตรมาส1": bg_p1,
                        "ผลไตรมาส1": bg_actual,
                        "แผนไตรมาส2": 0.0,
                        "ผลไตรมาส2": 0.0,
                        "แผนไตรมาส3": 0.0,
                        "ผลไตรมาส3": 0.0,
                        "แผนไตรมาส4": 0.0,
                        "ผลไตรมาส4": 0.0,
                        "ปัญหาและอุปสรรค": "",
                        "สถานะไตรมาส1": "เป็นไปตามแผน" if bg_actual >= bg_p1 and bg_p1 > 0 else "ล่าช้า"
                    })
                    i += 1
        i += 1

    return transformed_rows

def main():
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "http://www.e-project.doae.go.th/home.php"
    }

    # 1. เข้าสู่ระบบ
    payload = {
        "floginName": USERNAME,
        "fuserPwd": PASSWORD,
        "fbgtYear": "2569",
        "Submit": "เข้าสู่ระบบ"
    }
    session.post(LOGIN_URL, data=payload, headers=headers)

    today_str = datetime.date.today().strftime("%d/%m/%Y")

    # 2. ดึงรายชื่อโครงการทั้งหมดจากระบบอัตโนมัติ
    projects_to_scrape = get_all_projects_auto(session, headers)

    master_index = [
        {
            "seq": "0",
            "name": "ภาพรวมกรมส่งเสริมการเกษตร",
            "url": "AUTO_ALL",
            "group": "",
            "opDate": today_str,
            "bgDate": today_str
        }
    ]
    projects_data = {}

    # 3. วนลูปดึงข้อมูลรายงานของทุกโครงการที่ตรวจพบ
    for idx, proj in enumerate(projects_to_scrape, start=1):
        params = {
            "lmYear": "2569",
            "rgAct": "n",
            "seBygov": "",
            "lessJob": "1000000",
            "lessmon": "1000000",
            "seByproj": proj["id"]
        }
        
        res = session.get(REPORT_BASE_URL, params=params, headers=headers)
        res.encoding = res.apparent_encoding or "tis-620"
        
        parsed_rows = parse_project_table(res.text, proj["name"])
        
        master_index.append({
            "seq": str(idx),
            "name": proj["name"],
            "url": "LOCAL",
            "group": "",
            "opDate": today_str,
            "bgDate": today_str
        })
        projects_data[str(idx)] = parsed_rows
        print(f"[{idx}/{len(projects_to_scrape)}] ดึงข้อมูล '{proj['name']}' สำเร็จ")

    # 4. บันทึกผลลัพธ์รวมเป็น JSON
    os.makedirs("data", exist_ok=True)
    with open("data/dashboard_db.json", "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "master_index": master_index,
            "projects_data": projects_data
        }, f, ensure_ascii=False, indent=2)

    print("ประมวลผลโครงการทั้งหมดและสร้าง data/dashboard_db.json สำเร็จเรียบร้อย!")

if __name__ == "__main__":
    main()
