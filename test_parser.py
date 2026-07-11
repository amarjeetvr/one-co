import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import college_parser as parser

files = {
    "25455": (
        "html/info/25455_iit-delhi-indian-institute-of-technology-iitd-new-delhi.html",
        "html/placements/25455_iit-delhi-indian-institute-of-technology-iitd-new-delhi.html",
        "https://collegedunia.com/university/25455-iit-delhi-indian-institute-of-technology-iitd-new-delhi",
    ),
    "25703": (
        "html/info/25703_iit-bombay-indian-institute-of-technology-iitb-mumbai.html",
        "html/placements/25703_iit-bombay-indian-institute-of-technology-iitb-mumbai.html",
        "https://collegedunia.com/university/25703-iit-bombay-indian-institute-of-technology-iitb-mumbai",
    ),
    "25881": (
        "html/info/25881_iit-madras-indian-institute-of-technology-iitm-chennai.html",
        "html/placements/25881_iit-madras-indian-institute-of-technology-iitm-chennai.html",
        "https://collegedunia.com/university/25881-iit-madras-indian-institute-of-technology-iitm-chennai",
    ),
}

for cid, (info_f, place_f, url) in files.items():
    with open(info_f, "r", encoding="utf-8") as f:
        info_html = f.read()
    with open(place_f, "r", encoding="utf-8") as f:
        place_html = f.read()

    info      = parser.parse_college_info(info_html, cid, url)
    rankings  = parser.parse_rankings(place_html, cid, extra_html=info_html)
    placement = parser.parse_placements(place_html, cid)

    print(f"=== {cid} ===")
    print(f"  Name:     {info['name']}")
    print(f"  City:     {info['city']}")
    print(f"  State:    {info['state']}")
    print(f"  Rankings: {rankings}")
    print(f"  Highest:  {placement['highest_package']}")
    print(f"  Average:  {placement['average_package']}")
    print(f"  Median:   {placement['median_package']}")
    print()
