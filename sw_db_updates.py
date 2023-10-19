import json
import os
import shutil
import sys
import tempfile
import uuid
import zipfile

# import PySimpleGUI as pg
import requests
from bs4 import BeautifulSoup as bs
from bs4 import SoupStrainer as ss
from dotmap import DotMap

CHECK_URL = "https://dynonavionics.com/us-aviation-obstacle-data.php"
SW_URL = "https://www.dynonavionics.com/skyview-hdx-software-updates-us-packages.php"
DOCUMENTATION_URL = "https://www.dynonavionics.com/skyview-documentation.php"
GARMIN_G5_URL = "https://www8.garmin.com/support/download_details.jsp?id=10354"
GARMIN_GPS_175_URL = (
    "https://www8.garmin.com/support/download_details.jsp?id=15281"  # Needs Windows
)


def get_available_versions():
    return DotMap(
        available_sw_versions=[
            link["href"].split("/")[-1]
            for link in bs(
                requests.get(SW_URL).content,
                "html.parser",
                parse_only=ss("a"),
            )
            if ".duc" in link.get("href") and "HDX1100" in link.get("href")
        ],
        available_database_versions=[
            link["href"].split("/")[-1]
            for link in bs(
                requests.get(CHECK_URL).content, "html.parser", parse_only=ss("a")
            )
            if ".duc" in link.get("href")
        ],
        available_g5_sw_version=[
            link["href"].split("/")[-1]
            for link in bs(
                requests.get(GARMIN_G5_URL).content, "html.parser", parse_only=ss("a")
            )
            if link.has_attr("href") and ".zip" in link["href"]
        ],
    )


def get_existing_versions(dynon_folder=None, garmin_folder=None):
    if not dynon_folder:
        dynon_folder = "/Users/GFahmy/Desktop/RV-7_Plans/SkyView/sotware_updates/"
    if not garmin_folder:
        garmin_folder = "/Users/GFahmy/Desktop/RV-7_Plans/garmin/"

    return DotMap(
        dynon_sw=DotMap(
            files=[
                file for file in os.listdir(dynon_folder) if file.startswith("SkyView")
            ],
            current=False,
        ),
        dynon_db=DotMap(
            files=[file for file in os.listdir(dynon_folder) if file.startswith("FAA")],
            current=False,
        ),
        garming_g5=DotMap(
            files=[file for file in os.listdir(garmin_folder) if file.startswith("G5")],
            current=False,
        ),
    )


def compare_version(existing_versions, current_versions):
    for file in existing_versions.dynon_sw.files:
        if file in current_versions.available_sw_versions:
            print(f"Existing {file} is latest version")
            existing_versions.dynon_sw.current = True
        else:
            existing_versions.dynon_sw.current = False
    for file in existing_versions.dynon_db.files:
        if file in current_versions.available_database_versions:
            print(f"Existing {file} Database is latest version")
            existing_versions.dynon_db.current = True
        else:
            existing_versions.dynon_db.current = False
    for file in existing_versions.garming_g5.files:
        if file in current_versions.available_g5_sw_version:
            print(f"Existing {file} is latest version")
            existing_versions.garming_g5.current = True
        else:
            existing_versions.garming_g5.current = False
    existing_versions.need_to_update = DotMap(
        files=[key for key, values in existing_versions.items() if not values.current],
        current=True,
    )
    return existing_versions


def archive_old_sw_databases(drive):
    existing_files = [
        file
        for file in os.listdir(drive)
        if file.startswith("FAA") or file.startswith("SkyView")
    ]
    if not existing_files:
        print("No databases to archive")
    for file in existing_files:
        print(f"Archived {file}")
        os.remove(drive + file)
    return


def download_dynon(database_url, software_update_url, drive, sw=False, db=False):
    print("\nDownloading Dynon Software and Databases")
    if sw:
        sw_urls = [
            link["href"]
            for link in bs(
                requests.get(software_update_url).content,
                "html.parser",
                parse_only=ss("a"),
            )
            if ".duc" in link.get("href") and "HDX1100" in link.get("href")
        ]
    else:
        sw_urls = []
    if db:
        db_urls = [
            link["href"]
            for link in bs(
                requests.get(database_url).content, "html.parser", parse_only=ss("a")
            )
            if ".duc" in link.get("href")
        ]
    else:
        db_urls = []
    download_urls = sw_urls + db_urls
    for link in download_urls:
        file = link.split("/")[-1]
        filename = drive + file
        download_url = "https://dynonavionics.com" + link
        print(f"\nDownloading {file} to {drive} ...")
        with open(filename, "wb+") as out_file:
            content = requests.get(download_url, stream=True).content
            out_file.write(content)
            print(f"Saved {file}")


def download_skyview_docs(documentation_url, drive=None):
    print("\nDownloading Skyview Documentation\n")
    documentation_links = [
        link["href"]
        for link in bs(
            requests.get(documentation_url).content, "html.parser", parse_only=ss("a")
        )
        if ".pdf" in link.get("href")
        and "guide" in link.get("href")
        and "Changes" not in link.get("href")
        and "Classic" not in link.get("href")
        and "SkyView_SE" not in link.get("href")
        and "D10_D100" not in link.get("href")
    ]
    if not drive:
        drive = "/Users/GFahmy/Desktop/RV-7_Plans/SkyView/PDFs/"
    if not os.path.isdir(drive):
        drive = "/Users/gfahmy/Documents/projects/dynon/testing/documentation/"
    existing_files = [file for file in os.listdir(drive)]
    for link in documentation_links:
        file = link.split("/")[-1]
        filename = drive + file
        download_url = "https://dynonavionics.com/" + link
        if file in existing_files:
            existing_files.remove(file)
            print(f"{file} already exists...skipping")
        else:
            print(f"\nDownloading {file} to {drive} ...")
            with open(filename, "wb+") as out_file:
                content = requests.get(download_url, stream=True).content
                out_file.write(content)
                print(f"Saved {file}")


def download_garmin(garmin_url, drive):
    print("\nDownloading Garming SW\n")
    garmin_software = [
        link["href"]
        for link in bs(
            requests.get(garmin_url).content, "html.parser", parse_only=ss("a")
        )
        if link.has_attr("href") and ".zip" in link["href"]
    ][0]
    file = garmin_software.split("/")[-1]
    print(f"\nDownloading {file} to {drive} ...")
    with open(drive + file, "wb+") as out_file:
        content = requests.get(garmin_software, stream=True).content
        out_file.write(content)
        with zipfile.ZipFile(drive + file, "r") as zip_ref:
            zip_ref.extractall(drive)
        print(f"File saved to {drive} {file}")


if __name__ == "__main__":
    sw_flag = sys.argv[-1]

    sw_flag = False if sw_flag != "True" else True
    dynon_volumes = [
        "/Volumes/" + drive + "/"
        for drive in os.listdir("/Volumes/")
        if "DYNON" in drive
    ]
    garmin_volumes = [
        "/Volumes/" + drive + "/"
        for drive in os.listdir("/Volumes/")
        if "GARMIN_G5" in drive
    ]

    urn = f"urn:node:{hex(uuid.getnode())}"

    uid = str(uuid.uuid3(uuid.NAMESPACE_DNS, urn))
    try:
        config = json.load(open("sw_folder_config.json", "r")).get(uid)
    except:
        config = {}

    dynon_folder = (
        config.get("dynon_path")
        if config.get("dynon_path") is not None
        else input("Path to Dynon SW: ")
    )
    garmin_folder = (
        config.get("garmin_path")
        if config.get("garmin_path") is not None
        else input("Path to Garmin SW: ")
    )
    dynon_documentation_folder = (
        config.get("dynon_documentation_folder")
        if config.get("dynon_documentation_folder") is not None
        else input("Path to Documentation Folder: ")
    )

    if not dynon_folder.endswith("/"):
        dynon_folder = dynon_folder + "/"

    if not garmin_folder.endswith("/"):
        garmin_folder = garmin_folder + "/"

    if not dynon_documentation_folder.endswith("/"):
        dynon_documentation_folder = dynon_documentation_folder + "/"

    current_versions = get_available_versions()
    existing_versions = get_existing_versions(
        dynon_folder=dynon_folder,
        garmin_folder=garmin_folder,
    )

    existing_versions = compare_version(existing_versions, current_versions)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = tmp + "/"
        for sw_category in existing_versions.need_to_update.files:
            if sw_category == "dynon_sw":
                download_dynon(CHECK_URL, SW_URL, tmp, sw=sw_flag)
                # If we're updating software we're checking for new documentation and saving to HD
                download_skyview_docs(DOCUMENTATION_URL, dynon_documentation_folder)
                for file in os.listdir(tmp):
                    shutil.copyfile(
                        tmp + file,
                        dynon_folder + file,
                    )
                    for vol in dynon_volumes:
                        shutil.copyfile(tmp + file, f"{vol}/{file}")
                        print(f"Saved {file} to {vol}")

            if sw_category == "dynon_db":
                download_dynon(CHECK_URL, SW_URL, tmp, db=True)
                for file in os.listdir(tmp):
                    shutil.copyfile(
                        tmp + file,
                        dynon_folder + file,
                    )
                    for vol in dynon_volumes:
                        shutil.copyfile(tmp + file, f"{vol}/{file}")
                        print(f"Saved {file} to {vol}")

            if sw_category == "garmin_g5":
                download_garmin(GARMIN_G5_URL, tmp)
                for file in os.listdir(tmp):
                    shutil.copyfile(
                        tmp + file,
                        garmin_folder + file,
                    )
                    for vol in garmin_volumes:
                        shutil.copyfile(tmp + file, f"{vol}/{file}")
                        print(f"Saved {file} to {vol}")

    with open("sw_folder_config.json", "w+") as fp:
        json.dump(
            {
                uid: {
                    "dynon_path": dynon_folder,
                    "garmin_path": garmin_folder,
                    "dynon_documentation_folder": dynon_documentation_folder,
                }
            },
            fp,
            indent=4,
        )
