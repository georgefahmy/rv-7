import itertools
import json
import os
import shutil
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
        dynon=DotMap(
            software=DotMap(
                files=[
                    file
                    for file in os.listdir(dynon_folder)
                    if file.startswith("SkyView")
                ],
                current=False,
            ),
            database=DotMap(
                files=[
                    file for file in os.listdir(dynon_folder) if file.startswith("FAA")
                ],
                current=False,
            ),
        ),
        garmin_g5=DotMap(
            files=[file for file in os.listdir(garmin_folder) if file.startswith("G5")],
            current=False,
        ),
    )


def compare_version(existing_versions, current_versions):
    for file in current_versions.available_sw_versions:
        if file in existing_versions.dynon.software.files:
            print(f"Existing {file} is latest version")
            existing_versions.dynon.current = True
            existing_versions.dynon.software.current = True
            existing_versions.dynon.software.download = False

        else:
            existing_versions.dynon.current = False
            existing_versions.dynon.software.current = False
            existing_versions.dynon.software.download = True

    for file in current_versions.available_database_versions:
        if file in existing_versions.dynon.database.files:
            print(f"Existing {file} Database is latest version")
            existing_versions.dynon.current = True
            existing_versions.dynon.database.current = True
            existing_versions.dynon.database.download = False

        else:
            existing_versions.dynon.current = False
            existing_versions.dynon.database.current = False
            existing_versions.dynon.database.download = True

    for file in existing_versions.garmin_g5.files:
        if file in current_versions.available_g5_sw_version:
            print(f"Existing {file} is latest version")
            existing_versions.garmin_g5.current = True
            existing_versions.garmin_g5.download = False

        else:
            existing_versions.garmin_g5.current = False
            existing_versions.garmin_g5.download = True
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

        print(f"ZIP file saved to {drive} {file}")

    with zipfile.ZipFile(drive + file, "r") as zip_ref:
        zip_ref.extractall(drive)

    return drive


def compare_file_dates(f1: DotMap, f2: DotMap):
    if f1.ctime < f2.ctime:
        return f1.name
    else:
        return f2.name


def remove_old(dynon_folder):
    db_files = [
        dynon_folder + file
        for file in os.listdir(dynon_folder)
        if file.startswith("FAA")
    ]
    sw_hw4_files = [
        dynon_folder + file
        for file in os.listdir(dynon_folder)
        if file.startswith("SkyView") and "hw4" in file
    ]

    sw_files = [
        dynon_folder + file
        for file in os.listdir(dynon_folder)
        if file.startswith("SkyView") and "hw4" not in file
    ]

    for x, y in itertools.pairwise(db_files):
        f1 = DotMap(name=x, ctime=os.stat(x).st_birthtime)
        f2 = DotMap(name=y, ctime=os.stat(y).st_birthtime)
        remove_file = compare_file_dates(f1, f2)
        os.remove(remove_file)

    for x, y in itertools.pairwise(sw_hw4_files):
        f1 = DotMap(name=x, ctime=os.stat(x).st_birthtime)
        f2 = DotMap(name=y, ctime=os.stat(y).st_birthtime)
        remove_file = compare_file_dates(f1, f2)
        os.remove(remove_file)

    for x, y in itertools.pairwise(sw_files):
        f1 = DotMap(name=x, ctime=os.stat(x).st_birthtime)
        f2 = DotMap(name=y, ctime=os.stat(y).st_birthtime)
        remove_file = compare_file_dates(f1, f2)
        os.remove(remove_file)


if __name__ == "__main__":
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
    print(uid)

    config_file = json.load(open("sw_folder_config.json", "r"))
    config = (
        config_file.get(uid)
        if uid in config_file.keys()
        else {
            "main_path": None,
        }
    )

    main_folder = (
        config.get("main_path")
        if config.get("main_path") is not None
        else input("Path to SW Folder: ")
    )
    if not main_folder.endswith("/"):
        main_folder = main_folder + "/"

    dynon_folder = main_folder + "sv_software/"
    garmin_folder = main_folder + "garmin_software/"
    dynon_documentation_folder = main_folder + "documentation/"

    [
        os.mkdir(folder)
        for folder in [dynon_folder, garmin_folder, dynon_documentation_folder]
        if not os.path.isdir(folder)
    ]

    current_versions = get_available_versions()
    existing_versions = get_existing_versions(
        dynon_folder=dynon_folder,
        garmin_folder=garmin_folder,
    )

    existing_versions = compare_version(existing_versions, current_versions)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = tmp + "/"
        for sw_category in existing_versions.need_to_update.files:
            if "dynon" in sw_category:
                download_dynon(
                    CHECK_URL,
                    SW_URL,
                    tmp,
                    db=existing_versions.dynon.database.download,
                    sw=existing_versions.dynon.software.download,
                )
                # If we're updating software we're checking for new documentation and saving to HD
                shutil.copytree(tmp, dynon_folder, dirs_exist_ok=True)
                download_skyview_docs(DOCUMENTATION_URL, dynon_documentation_folder)

            if sw_category == "garmin_g5":
                tmp = download_garmin(GARMIN_G5_URL, tmp)
                shutil.copytree(tmp, garmin_folder, dirs_exist_ok=True)

    # Copy the newly downloaded software to their respective aircraft drives and SD cards
    for folder in os.listdir(main_folder):
        if folder == "sv_software":
            shutil.copytree(main_folder + folder, "TEST", dirs_exist_ok=True)
            for vol in dynon_volumes:
                shutil.copytree(folder, f"{vol}", dirs_exist_ok=True)

        if folder == "garmin_software":
            for vol in garmin_volumes:
                shutil.copytree(
                    main_folder + "garmin_software/" + "Garmin/", f"{vol}/Garmin/"
                )

    remove_old(dynon_folder)
    config_file[uid] = {
        "main_path": main_folder,
    }
    with open("sw_folder_config.json", "w+") as fp:
        json.dump(config_file, fp, indent=4)
