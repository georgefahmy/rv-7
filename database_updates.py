import requests
import re
import os
import sys
from bs4 import BeautifulSoup


check_url = "https://dynonavionics.com/us-aviation-obstacle-data.php"

DYNON_USB = "/Volumes/DYNON/"


def archive_old_sw_databases():
    databases_folder = f"/Users/GFahmy/Desktop/RV-7_Plans/SkyView/sotware_updates/databases/"
    archive_folder = (
        "/Users/GFahmy/Desktop/RV-7_Plans/SkyView/sotware_updates/databases/archived_databases/"
    )

    if os.path.isdir(DYNON_USB):
        os.listdir(DYNON_USB)
        usb_existing_db_files = [file for file in os.listdir(DYNON_USB) if file.startswith("FAA")]
        for file in usb_existing_db_files:
            os.remove(DYNON_USB + file)

    existing_db_files = [file for file in os.listdir(databases_folder) if file.startswith("FAA")]
    if not existing_db_files:
        print("No databases to archive")
        return
    for file in existing_db_files:
        os.rename(databases_folder + file, archive_folder + file)
    print("Archived old SW versions")
    return


def generate_download_url(cycles):
    av_cycle, ob_cycle = [
        re.findall(r"[0-9]{4}", cycles[0].replace(")", ""))[0],
        re.findall(r"[0-9]{4}", cycles[1].replace(")", ""))[0],
    ]
    print([av_cycle, ob_cycle])
    dn = f"https://dynonavionics.com/downloads/Software/Us-av-ob/FAA_av{av_cycle}_ob{ob_cycle}.duc"
    if os.path.isdir(DYNON_USB):
        fn = DYNON_USB + f"FAA_av{av_cycle}_ob{ob_cycle}.duc"
    else:
        fn = f"/Users/GFahmy/Desktop/RV-7_Plans/SkyView/sotware_updates/databases/FAA_av{av_cycle}_ob{ob_cycle}.duc"
    return (dn, fn)


soup = BeautifulSoup(requests.get(check_url).content, "html.parser")

current_data = soup.find_all(string=re.compile("Current Data", flags=re.I))[0]
cur_av_cycle, cur_ob_cycle = current_data.parent.parent.find_all(string=re.compile("Cycle:"))

download_url, filename = generate_download_url((cur_av_cycle, cur_ob_cycle))

print(f"\nDownloading Current database...")

archive_old_sw_databases()

with open(filename, "wb+") as out_file:
    content = requests.get(download_url, stream=True).content
    out_file.write(content)
    print(f"Success!\nFile saved to {filename}")
