import utility
import argparse

from conference_assistant import ConferenceAssistant
from config import CATEGORY, DESCRIPTION, END_DATE, LOCATION, START_DATE, WEBSITE


parser = argparse.ArgumentParser()
parser.add_argument("--input_file", type=str, default="test/papers_metadata.csv")
parser.add_argument("--conference", type=str, default="NeurIPS")
parser.add_argument("--year", type=int, default=2024)
args = parser.parse_args()
year = args.year
conference = args.conference
input_file = args.input_file


if utility.check_venue_matches(input_file, conference, year):
    conf_assitant = ConferenceAssistant(
        year=year,
        conference=conference,
        input_file=input_file,
        location=LOCATION,
        website=WEBSITE,
        category=CATEGORY,
        description=DESCRIPTION,
        start_date=START_DATE,
        end_date=END_DATE,
    )


    conf_assitant.run()

else:
    raise ValueError(
        "Venue mismatch: the input file's venue does not match the provided conference and year."
    )
