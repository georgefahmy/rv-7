import os
import shutil
import tempfile
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


def get_existing_versions():
    return DotMap(
        dynon_sw=DotMap(
            files=[
                file
                for file in os.listdir(
                    "/Users/GFahmy/Desktop/RV-7_Plans/SkyView/sotware_updates/"
                )
                if file.startswith("SkyView")
            ],
            current=False,
        ),
        dynon_db=DotMap(
            files=[
                file
                for file in os.listdir(
                    "/Users/GFahmy/Desktop/RV-7_Plans/SkyView/sotware_updates/"
                )
                if file.startswith("FAA")
            ],
            current=False,
        ),
        garming_g5=DotMap(
            files=[
                file
                for file in os.listdir("/Users/GFahmy/Desktop/RV-7_Plans/garmin/")
                if file.startswith("G5")
            ],
            current=False,
        ),
    )


def compare_version(existing_versions, current_versions):
    for file in existing_versions.dynon_sw.files:
        if file in current_versions.available_sw_versions:
            print("Existing Dynon SW is latest version")
            existing_versions.dynon_sw.current = True
        else:
            existing_versions.dynon_sw.current = False
    for file in existing_versions.dynon_db.files:
        if file in current_versions.available_database_versions:
            print("Existing Database is latest version")
            existing_versions.dynon_db.current = True
        else:
            existing_versions.dynon_db.current = False
    for file in existing_versions.garming_g5.files:
        if file in current_versions.available_g5_sw_version:
            print("Existing G5 SW is latest version")
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
    current_versions = get_available_versions()
    existing_versions = get_existing_versions()

    existing_versions = compare_version(existing_versions, current_versions)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = tmp + "/"
        for sw_category in existing_versions.need_to_update.files:
            if sw_category == "dynon_sw":
                download_dynon(CHECK_URL, SW_URL, tmp, sw=True)
                # If we're updating software we're checking for new documentation and saving to HD
                download_skyview_docs(DOCUMENTATION_URL)
                for file in os.listdir(tmp):
                    shutil.copyfile(
                        tmp + file,
                        f"/Users/GFahmy/Desktop/RV-7_Plans/SkyView/sotware_updates/{file}",
                    )
                    for vol in dynon_volumes:
                        shutil.copyfile(tmp + file, f"{vol}/{file}")
                        print(f"Saved {file} to {vol}")

            if sw_category == "dynon_db":
                download_dynon(CHECK_URL, SW_URL, tmp, db=True)
                for file in os.listdir(tmp):
                    shutil.copyfile(
                        tmp + file,
                        f"/Users/GFahmy/Desktop/RV-7_Plans/SkyView/sotware_updates/{file}",
                    )
                    for vol in dynon_volumes:
                        shutil.copyfile(tmp + file, f"{vol}/{file}")
                        print(f"Saved {file} to {vol}")

            if sw_category == "garmin_g5":
                download_garmin(GARMIN_G5_URL, tmp)
                for file in os.listdir(tmp):
                    shutil.copyfile(
                        tmp + file, f"/Users/GFahmy/Desktop/RV-7_Plans/garmin/{file}"
                    )
                    for vol in garmin_volumes:
                        shutil.copyfile(tmp + file, f"{vol}/{file}")
                        print(f"Saved {file} to {vol}")
