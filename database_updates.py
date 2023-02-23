import requests
import re
import os
from bs4 import BeautifulSoup


check_url = "https://dynonavionics.com/us-aviation-obstacle-data.php"


def archive_old_sw_databases():
    databases_folder = f"/Users/GFahmy/Desktop/RV-7_Plans/SkyView/sotware_updates/databases/"
    archive_folder = (
        "/Users/GFahmy/Desktop/RV-7_Plans/SkyView/sotware_updates/databases/archived_databases/"
    )
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
        cycles[0].replace(")", "").split("Cycle:")[-1].strip(),
        cycles[1].replace(")", "").split("Cycle:")[-1].strip(),
    ]
    dn = f"https://dynonavionics.com/downloads/Software/Us-av-ob/FAA_av{av_cycle}_ob{ob_cycle}.duc"
    fn = f"/Users/GFahmy/Desktop/RV-7_Plans/SkyView/sotware_updates/databases/FAA_av{av_cycle}_ob{ob_cycle}.duc"
    return (dn, fn)


soup = BeautifulSoup(requests.get(check_url).content, "html.parser")

current_data = soup.find_all(string=re.compile("Current Data", flags=re.I))[0]
cur_av_cycle, cur_ob_cycle = current_data.parent.parent.find_all(string=re.compile("Cycle:"))

new_data = soup.find_all(string=re.compile("Upcoming Data", flags=re.I))[0]
new_av_cycle, new_ob_cycle = new_data.parent.parent.find_all(string=re.compile("Cycle:"))

download_url_current, cur_filename = generate_download_url((cur_av_cycle, cur_ob_cycle))
download_url_new, new_filename = generate_download_url((new_av_cycle, new_ob_cycle))


flag = input("Download upcoming databases (no will download current databases) Y/n: ")
database_choice = "Upcomming" if flag == "Y" else "Current"

print(f"\nDownloading {database_choice} database...")
download_url = download_url_new if database_choice == "Upcomming" else download_url_current
filename = new_filename if database_choice == "Upcomming" else cur_filename

archive_old_sw_databases()

with open(filename, "wb+") as out_file:
    content = requests.get(download_url, stream=True).content
    out_file.write(content)
    print(f"Success!\nFile saved to {filename}")
