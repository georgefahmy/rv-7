import os
from dotmap import DotMap


def read_checklist(checklist):
    checklist_dict = DotMap()
    with open(checklist_folder + checklist, mode="r", encoding="utf-8") as fp:
        checklist_dict.filename = checklist
        checklist_dict.raw = fp.read()
        initial_list = checklist_dict.raw.split("\n\n")
        for section in initial_list:
            lines = section.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("#"):
                    checklist_dict.comments[f"line{i}"] = line
                else:
                    if "TITLE" in line:
                        checklist_dict.sections[section.split(".")[0]].TITLE = line.split(", ")[-1]
                    if "LINE" in line:
                        value = line.split(", ")[-1].strip() if len(line.split(",")[-1]) > 1 else ""
                        checklist_dict.sections[section.split(".")[0]][f"LINE{i}"] = value
    return checklist_dict


def create_checklist(checklist_dict):
    i = 0
    while True:
        if checklist_dict.sections[f"CHKLST{i}"].TITLE:
            print(checklist_dict.sections[f"CHKLST{i}"].TITLE)
        else:
            section_title = input("New Section Title: ")
            if section_title == "":
                break
            checklist_dict.sections[f"CHKLST{i}"].TITLE = section_title
        j = 1
        while True:
            checklist_item = input("New Checklist Item: ")
            if checklist_item == "":
                break
            checklist_dict.sections[f"CHKLST{i}"][f"LINE{j}"] = checklist_item
            j += 1
        i += 1

    return checklist_dict


def write_checklist(filename):
    with open(checklist_folder + filename, "w", encoding="utf-8") as fp:
        lines = []
        for key, value in checklist_dict.sections.items():
            lines.append("")
            for key2, line in value.items():
                if type(line) == DotMap:
                    continue
                lines.append(key + "." + key2 + ", " + str(line))
        fp.write("\n".join(lines))


checklist_folder = "/Users/GFahmy/Desktop/RV-7_Plans/SkyView/checklists/"

if not os.path.isdir(checklist_folder):
    os.mkdir(checklist_folder)


checklists = os.listdir(checklist_folder)

checklist = checklists[0]
checklist_dict = read_checklist(checklist)

checklist_dict = create_checklist(checklist_dict)

checklist_dict.sections.pprint("json")

filename = "checklist2.txt"
write_checklist(filename)
