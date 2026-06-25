from bs4 import BeautifulSoup
import pandas as pd

with open("iit_delhi_courses.html", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

rows = []

college_name = "IIT Delhi"
college_url = "https://collegedunia.com/university/25455-iit-delhi-indian-institute-of-technology-iitd-new-delhi"

# College-level information
rating = "4.3"
rank = "#2"

tables = soup.find_all("table")

for table in tables:

    trs = table.find_all("tr")

    if len(trs) < 2:
        continue

    heading = trs[0].get_text(" ", strip=True)

    degree = ""
    duration = ""
    course_type = ""

    if "B.Tech" in heading:
        degree = "B.Tech"
        duration = "4 Years"
        course_type = "Full Time"

    elif "M.Tech" in heading:
        degree = "M.Tech"
        duration = "2 Years"
        course_type = "Full Time"

    elif "MBA" in heading:
        degree = "MBA"
        duration = "2 Years"
        course_type = "Full Time"

    elif "M.Sc" in heading:
        degree = "M.Sc"
        duration = "2 Years"
        course_type = "Full Time"

    elif "B.Des" in heading:
        degree = "B.Des"
        duration = "4 Years"
        course_type = "Full Time"

    elif "M.Des" in heading:
        degree = "M.Des"
        duration = "2 Years"
        course_type = "Full Time"

    elif "Ph.D" in heading:
        degree = "Ph.D"
        duration = "3 Years"
        course_type = "Full Time"

    if degree == "":
        continue

    for tr in trs[1:]:

        tds = tr.find_all("td")

        if len(tds) < 2:
            continue

        course_name = tds[0].get_text(" ", strip=True)
        fees = tds[1].get_text(" ", strip=True)

        # Remove degree name from course name
        if course_name.startswith(degree):
            course_name = course_name.replace(degree, "", 1).strip()

        rows.append({
            "College Name": college_name,
            "Degree Name": degree,
            "Course Name": course_name,
            "College URL": college_url,
            "Total Fees": fees,
            "Course Type": course_type,
            "Duration": duration,
            "Rating": rating,
            "Rank": rank
        })

df = pd.DataFrame(rows)

df.to_excel("iit_delhi_courses.xlsx", index=False)

print(df.head())
print("Done!")