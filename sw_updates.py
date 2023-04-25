import requests
import os
import zipfile
from bs4 import BeautifulSoup as bs, SoupStrainer as ss


dynon_url = "https://www.dynonavionics.com/skyview-hdx-software-updates-us-packages.php"
garmin_url = "https://www8.garmin.com/support/download_details.jsp?id=10354"


def archive_old_sw_updates():
    sw_updates_path = f"/Users/GFahmy/Desktop/RV-7_Plans/SkyView/sotware_updates/software/"
    archive_folder = (
        "/Users/GFahmy/Desktop/RV-7_Plans/SkyView/sotware_updates/software/archived_sw_updates/"
    )
    existing_sw_files = [file for file in os.listdir(sw_updates_path) if file.startswith("SkyView")]
    if not existing_sw_files:
        print("No SW to archive")
        return
    for file in existing_sw_files:
        os.rename(sw_updates_path + file, archive_folder + file)
    print("Archived old SW versions")
    return


def generate_download_url(download_href):
    dn = f"https://dynonavionics.com/{download_href}"
    fn = f"/Users/GFahmy/Desktop/RV-7_Plans/SkyView/sotware_updates/software/{download_href.split('/')[-1]}"
    return (dn, fn)


for link in bs(requests.get(garmin_url).content, "html.parser", parse_only=ss("a")):
    if link.has_attr("href"):
        if ".zip" in link["href"]:
            garmin_software = link["href"]

for link in bs(requests.get(dynon_url).content, "html.parser", parse_only=ss("a")):
    if link.has_attr("href"):
        if ".duc" in link["href"] and "HDX1100" in link["href"]:
            if "hw4" in link["href"]:
                hw4_download_url = link["href"]
            else:
                non_hw4_download_url = link["href"]

download_non_hw4_url, non_hw4_filename = generate_download_url(non_hw4_download_url)
download_hw4_url, hw4_filename = generate_download_url(hw4_download_url)


archive_old_sw_updates()

print(f"\nDownloading {non_hw4_filename.split('/')[-1]}")
with open(non_hw4_filename, "wb+") as out_file:
    content = requests.get(download_non_hw4_url, stream=True).content
    out_file.write(content)
    print(f"Success!\nFile saved to {non_hw4_filename}")

print(f"\nDownloading {hw4_filename.split('/')[-1]}")
with open(hw4_filename, "wb+") as out_file:
    content = requests.get(download_hw4_url, stream=True).content
    out_file.write(content)
    print(f"Success!\nFile saved to {hw4_filename}")

print(f"\nDownloading latest Garmin G5 software")
with open(
    "/Users/GFahmy/Desktop/RV-7_Plans/garmin/" + garmin_software.split("/")[-1], "wb+"
) as out_file:
    content = requests.get(garmin_software, stream=True).content
    out_file.write(content)
    with zipfile.ZipFile(
        "/Users/GFahmy/Desktop/RV-7_Plans/garmin/" + garmin_software.split("/")[-1], "r"
    ) as zip_ref:
        zip_ref.extractall("/Users/GFahmy/Desktop/RV-7_Plans/garmin/")
    print(
        f"Success!\nFile saved to "
        + "/Users/GFahmy/Desktop/RV-7_Plans/garmin/"
        + garmin_software.split("/")[-1]
    )
