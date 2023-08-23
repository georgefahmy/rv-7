import datetime
import os

import gspread
from dotmap import DotMap


def make_checklist(worksheets, chklist):
    i = 0
    for sheet in worksheets[:-1]:
        checklist_titles = sheet.get("B1:1")[0]
        all_records = sheet.get_all_records()
        for checklist in checklist_titles:
            blank = 0
            # print(f"CHKLST{i}.TITLE,", checklist)
            chklist.sections[f"CHKLST{i}"].TITLE = checklist.upper()
            for j, row in enumerate(all_records):
                if not row[checklist]:
                    blank += 1
                if blank > 1:
                    continue
                # print(f"CHKLST{i}.LINE{j+1},", row[checklist])
                chklist.sections[f"CHKLST{i}"][f"LINE{j+1}"] = row[checklist]
            i += 1
    chklist.sections[f"CHKLST{i}"].TITLE = "CHECKLIST INFO"
    chklist.sections[f"CHKLST{i}"]["LINE1"] = ""
    chklist.sections[f"CHKLST{i}"]["LINE2"] = (
        "Last Updated: " + chklist.date.split("T")[0]
    )
    chklist.sections.pprint("json")
    return chklist


def write_checklist(chklist):
    with open(chklist.folder + chklist.filename, "w", encoding="utf-8") as fp:
        lines = []
        for key, value in chklist.sections.items():
            lines.append("")
            for key2, line in value.items():
                if type(line) == DotMap:
                    continue
                lines.append(key + "." + key2 + ", " + str(line))
        fp.write("\n".join(lines))


SHEET_ID = "1-EtvM-MdQwJ0Wk8CXvsHwmCrYk3bptP8fpDFwMWMDkc"
DYNON_SHEET = gspread.service_account().open_by_key(SHEET_ID)

filename = input("Enter Filename for Checklist: ")
if not filename.endswith(".txt"):
    filename = filename.split(".")[0] + ".txt"

chklist = DotMap(
    sections=DotMap(),
    filename=filename,
    date=datetime.datetime.now().isoformat(),
    folder="/Users/GFahmy/Desktop/RV-7_Plans/SkyView/checklists/",
)

if not os.path.isdir(chklist.folder):
    os.mkdir(chklist.folder)

chklist = make_checklist(DYNON_SHEET.worksheets(), chklist)
write_checklist(chklist)

print("Done")
os.system(f"Open {chklist.folder}")
