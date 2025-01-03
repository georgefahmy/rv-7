import json
import re

import xmltodict
from bs4 import BeautifulSoup as bs
from dotmap import DotMap
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def flatten_dict(d, parent_key="", sep="_"):
    items = []
    for k, v in d.items():
        if "index" in k:
            continue
        if "title" in k:
            parent_key = v
            continue
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def create_pdf(data, filename):
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    flat_data = flatten_dict(data)

    for key, value in flat_data.items():
        if not value:
            continue

        story.extend((Paragraph(f"{key}: {value}", styles["Normal"]), Spacer(1, 12)))
    doc.build(story)


o = xmltodict.parse(
    open(
        "rv-7n890gf.wordpress.2025-01-03.000.xml",
        "rb",
    )
)
raw = DotMap(o)["rss"]["channel"]
d = DotMap(
    title=raw.title, link=raw.link, description=raw.description, content=raw.item
)


def getpath(nested_dict, value, prepath=()):
    for k, v in nested_dict.items():
        path = prepath + (k,)
        if v == value:  # found value
            return path
        elif hasattr(v, "items"):  # v is a dict
            p = getpath(v, value, path)  # recursive call
            if p is not None:
                return p


clean = DotMap()
images = DotMap()
for i, item in enumerate(d.content):
    if item["wp:post_type"] == "post":
        print(item.title)
        content = bs(item["content:encoded"])
        clean[item.title] = DotMap(
            index=i,
            title=item.title,
            post_date=item["wp:post_date"],
            text=re.sub("\n+", "\n\n", content.text.strip()),
            url=item.link,
            post_id=item["wp:post_id"],
            images=[
                a.get("href")
                for a in content.find_all("a")
                if "wp-content" in a.get("href")
            ],
            links=[
                a.get("href")
                for a in content.find_all("a")
                if "wp-content" not in a.get("href")
            ],
        )

for i, item in enumerate(d.content):
    if item["wp:post_type"] == "attachment":
        try:
            clean_key = getpath(clean, item["wp:post_parent"])
            clean[clean_key[0]]["images"].append(item["wp:attachment_url"])
        except Exception:
            # print(item["wp:post_parent"])
            continue
        images[item["wp:post_parent"]][item.title] = DotMap(
            index=i,
            title=item.title,
            post_id=item["wp:post_id"],
            url=item["wp:attachment_url"],
            status=item["wp:comment_status"],
        )


for key in clean.keys():
    clean[key].images = list(set(clean[key].images))

with open("full.json", "w") as fp:
    json.dump(clean.toDict(), fp, indent=4, sort_keys=False)

create_pdf(clean.toDict(), "output.pdf")
