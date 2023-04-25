import requests
import os
from bs4 import BeautifulSoup as bs, SoupStrainer as ss


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


def generate_download_url(check_url):
    for link in bs(requests.get(check_url).content, "html.parser", parse_only=ss("a")):
        if link.has_attr("href"):
            if ".duc" in link["href"]:
                print(link)
                download_url = "https://dynonavionics.com" + link["href"]
                if os.path.isdir(DYNON_USB):
                    fileheader = DYNON_USB
                else:
                    fileheader = (
                        "/Users/GFahmy/Desktop/RV-7_Plans/SkyView/sotware_updates/databases/"
                    )
                filename = fileheader + link["href"].split("/")[-1]
    return download_url, filename


CHECK_URL = "https://dynonavionics.com/us-aviation-obstacle-data.php"
DYNON_USB = "/Volumes/DYNON/"

archive_old_sw_databases()

print(f"\nDownloading Current database...")
download_url, filename = generate_download_url(CHECK_URL)

with open(filename, "wb+") as out_file:
    content = requests.get(download_url, stream=True).content
    out_file.write(content)
    print(f"Success!\nFile saved to {filename}")
