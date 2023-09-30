import os
import re
import zipfile

import PySimpleGUI as pg
import requests
from bs4 import BeautifulSoup as bs
from bs4 import SoupStrainer as ss

# TODO update script so that it doesnt download things twice. download once,
# then move files to approrpriate drives (download to HD then move?)


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


def download_dynon(database_url, software_update_url, drive, full=False):
    print("\nDownloading Dynon Software and Databases")
    if full:
        download_urls = [
            link["href"]
            for link in bs(
                requests.get(software_update_url).content,
                "html.parser",
                parse_only=ss("a"),
            )
            if ".duc" in link.get("href") and "HDX1100" in link.get("href")
        ]
    else:
        download_urls = []

    database_link = [
        link["href"]
        for link in bs(
            requests.get(database_url).content, "html.parser", parse_only=ss("a")
        )
        if ".duc" in link.get("href")
    ]
    download_urls.extend(database_link)
    existing_files = [
        file
        for file in os.listdir(drive)
        if file.startswith("FAA") or file.startswith("SkyView")
    ]

    for link in download_urls:
        file = link.split("/")[-1]
        filename = drive + file
        download_url = "https://dynonavionics.com" + link

        if file.startswith("SkyView"):
            version = "".join(re.split("(_)", file)[1:-3])

            skip = any(
                [
                    True if version in existing_file else False
                    for existing_file in existing_files
                ]
            )

        if file in existing_files or skip:
            existing_files.remove(file)
            print(f"{file} already exists...skipping")

        else:
            print(f"\nDownloading files to {drive} ...")
            with open(filename, "wb+") as out_file:
                content = requests.get(download_url, stream=True).content
                out_file.write(content)
                print(f"Saved {file}")

    for file in existing_files:
        os.remove(drive + file)
        print(f"Archived {file}")

    return True


def download_skyview_docs(documentation_url):
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
    drive = "/Users/GFahmy/Desktop/RV-7_Plans/SkyView/PDFs/"

    existing_files = [file for file in os.listdir(drive)]

    for link in documentation_links:
        file = link.split("/")[-1]
        filename = drive + file
        download_url = "https://dynonavionics.com/" + link
        if file in existing_files:
            existing_files.remove(file)
            print(f"{file} already exists...skipping")
        else:
            print(f"\nDownloading files to {drive} ...")
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

    existing_files = [file for file in os.listdir(drive) if file.startswith("G5")]

    if file in existing_files:
        existing_files.remove(file)
        print(f"{file} already exists...skipping")
    else:
        print(f"\nDownloading files to {drive} ...")
        with open(drive + file, "wb+") as out_file:
            content = requests.get(garmin_software, stream=True).content
            out_file.write(content)
            with zipfile.ZipFile(drive + file, "r") as zip_ref:
                zip_ref.extractall(drive)

            print(f"File saved to {drive} {file}")

    for file in existing_files:
        os.remove(drive + file)
        print(f"Archived {file}")

    return True


CHECK_URL = "https://dynonavionics.com/us-aviation-obstacle-data.php"
SW_URL = "https://www.dynonavionics.com/skyview-hdx-software-updates-us-packages.php"
DOCUMENTATION_URL = "https://www.dynonavionics.com/skyview-documentation.php"
GARMIN_G5_URL = "https://www8.garmin.com/support/download_details.jsp?id=10354"
GARMIN_GPS_175_URL = (
    "https://www8.garmin.com/support/download_details.jsp?id=15281"  # Needs Windows
)

volumes = [
    "/Volumes/" + drive + "/" for drive in os.listdir("/Volumes/") if "DYNON" in drive
]
if not volumes:
    print("No Dynon drives inserted, saving to internal drive")
    folder = pg.popup_get_folder(
        "Select SkyView SW folder",
        initial_folder="/Users/GFahmy/Desktop/RV-7_Plans/SkyView/sotware_updates/",
        no_window=True,
        history=True,
    )
    if folder:
        volumes = [folder + "/"]
    else:
        volumes = []

for drive in volumes:
    success = download_dynon(CHECK_URL, SW_URL, drive)

download_skyview_docs(DOCUMENTATION_URL)

# Garmin stuff
volumes = [
    "/Volumes/" + drive + "/"
    for drive in os.listdir("/Volumes/")
    if "GARMIN_G5" in drive
]
if not volumes:
    print("No Garmin drives inserted, saving to internal drive")
    folder = pg.popup_get_folder(
        "Select Garmin SW Folder",
        initial_folder="/Users/GFahmy/Desktop/RV-7_Plans/garmin/",
        no_window=True,
        history=True,
    )
    if folder:
        volumes = [folder + "/"]
    else:
        volumes = []

for drive in volumes:
    success = download_garmin(GARMIN_G5_URL, drive)
