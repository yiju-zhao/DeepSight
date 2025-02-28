import os
import logging
import openreview
import csv
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OpenReviewClient:
    def __init__(self, pdf_path: str):
        self.base_url = "https://openreview.net"
        self.client = openreview.api.OpenReviewClient(
            baseurl="https://api2.openreview.net"
        )
        self.csv_path = os.getenv("CSV_FILE_PATH")
        self.pdf_path = pdf_path

    def load_metadata_to_csv(self, conference: str, year: str):
        """
        Instantiate the OpenReview client, fetch conference papers for NeurIPS 2024,
        and save their metadata to a CSV file.
        """
        venue_id = f"{conference}.cc/{year}/Conference"

        # Retrieve all submissions of NeurIPS 2024
        try:
            submissions = self.client.get_all_notes(content={"venueid": venue_id})
        except Exception as e:
            logger.error("Error retrieving submissions: %s", e)
            return

        # Process each submission to extract details
        metadata = []
        for submission in submissions:
            content = submission.content
            paper_title = content.get("title", {}).get("value", "N/A")
            authorids = content.get("authorids", {}).get("value", [])
            authors = content.get("authors", {}).get("value", [])
            venue = content.get("venue", {}).get("value", "N/A")
            research_area = content.get("primary_area", {}).get("value", "N/A")
            keywrods = submission.content.get("keywords", {}).get("value", "")
            tldr = content.get("TLDR", {}).get("value", "N/A")
            abstract = content.get("abstract", {}).get("value", "N/A")

            pdf = content.get("pdf", {}).get("value", "")
            pdf_url = f"{self.base_url}{pdf}" if pdf else "N/A"

            bibtex_entry = submission.content.get("_bibtex", {}).get("value", "")
            url = bibtex_entry.split("url={")[1].split("}")[0].strip()
            paper_id = url.split("?id=")[1].split("&")[0]
            attachment_url = (
                f"{self.base_url}/attachment?id={paper_id}&name=supplementary_material"
            )

            data_path = os.path.join(self.pdf_path, f"{paper_id}.pdf")

            metadata.append(
                [
                    paper_title,
                    authorids,
                    authors,
                    venue,
                    research_area,
                    keywrods,
                    tldr,
                    abstract,
                    url,
                    pdf_url,
                    attachment_url,
                    data_path,
                ]
            )

        if metadata:
            try:
                with open(self.csv_path, "w", newline="", encoding="utf-8") as file:
                    writer = csv.writer(file)
                    writer.writerow(
                        [
                            "paper_title",
                            "author_ids",
                            "author_names",
                            "venue",
                            "research_area",
                            "keywords",
                            "tldr",
                            "abstract",
                            "url",
                            "pdf_url",
                            "attachment_url",
                            "pdf_path",
                        ]
                    )
                    writer.writerows(metadata)
                logger.info("Data has been successfully saved to %s", self.csv_path)
            except Exception as e:
                logger.error("Error writing to CSV file: %s", e)
        else:
            logger.info("No data found to write to CSV.")
