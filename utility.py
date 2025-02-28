import re
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup


def get_date_from_openreview(url: str) -> str:
    """
    Extract the date from the OpenReview URL.
    """
    response = requests.get(url)

    if response.status_code == 200:
        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        # Find the element containing "Published:" text.
        # This lambda searches for any <div> or <span> that includes "Published:" in its text.
        published_element = soup.find(
            lambda tag: tag.name in ["div", "span"] and "Published:" in tag.get_text()
        )

        if published_element:
            # Get the text and remove extra whitespace
            text = published_element.get_text(strip=True)
            # Use regex to extract the date in the format "25 Sep 2024"
            match = re.search(r"Published:\s*(\d+\s+\w+\s+\d+)", text)
            if match:
                published_date = match.group(1)
                date = datetime.strptime(published_date, "%d %b %Y")
            else:
                print("Could not extract the published date from the text:", text)
        else:
            print("Published date element not found.")
    else:
        print("Failed to retrieve the page. Status code:", response.status_code)

    if date:
        return date
    return None


def extract_conference_and_year(text: str):
    """
    Extracts the conference name and year from a venue string.

    Example:
        text = "NeuripS 2024 oral"
        returns ("NeuripS", 2024)
    """
    # The pattern captures non-digit characters (conference name)
    # followed by whitespace and a 4-digit year.
    pattern = r"^(?P<conference>[^\d]+)\s+(?P<year>\d{4})"
    match = re.search(pattern, text)
    if match:
        conference_name = match.group("conference").strip()
        year = int(match.group("year"))
        return conference_name, year
    return None, None


def check_venue_matches(
    csv_file: str, provided_conference: str, provided_year: int
) -> bool:
    # Read CSV into a DataFrame.
    df = pd.read_csv(csv_file)

    # Get the venue from the first row.
    venue_value = df.iloc[0]["venue"]
    print(f"Extracted venue: {venue_value}")

    # Extract conference name and year from the venue string.
    venue_conference, venue_year = extract_conference_and_year(venue_value)
    if venue_conference is None or venue_year is None:
        print("Could not extract conference or year from venue.")
        return False

    print(f"Extracted conference: {venue_conference}, year: {venue_year}")

    # Compare (case-insensitively for the conference name).
    if (
        venue_conference.lower() == provided_conference.lower()
        and venue_year == provided_year
    ):
        print("Match: Venue matches the provided conference and year.")
        return True
    else:
        print("No match: Venue does not match the provided conference and year.")
        return False


