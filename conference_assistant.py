import os
import re
import ast
import logging
import requests
import pandas as pd
from datetime import datetime

from dotenv import load_dotenv

from db_manager import DBManager
from llm.ollama_model import OllamaModel
from paper_agent import PDFAnalyzer
from repositories import (
    AuthorRepository,
    ConferenceInstanceRepository,
    ConferenceRepository,
    EmbeddingRepository,
    KeywordRepository,
    PaperRepository,
    ReferenceRepository,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

success_log_path = os.getenv("SUCCESS_LOG_PATH")
error_log_path = os.getenv("ERROR_LOG_PATH")


class ConferenceAssistant:
    def __init__(
        self,
        year: int,
        conference: str,
        location: str,
        website: str,
        category: str,
        description: str,
        input_file: str,
        start_date: datetime,
        end_date: datetime,
    ):
        global success_logs_df, error_logs_df
        self.year = year
        self.conference = conference
        self.start_date = start_date
        self.end_date = end_date
        self.location = location
        self.website = website
        self.category = category
        self.description = description
        self.csv_file_path = input_file
        self.instance_id = None
        self.db_manager = DBManager()
        self.llm = OllamaModel()
        self.base_pdf_dir = f"/data00/conference/pdfs/{str(self.conference).strip().lower()}/{str(self.year)}/"
        self.success_logs_df = pd.DataFrame(columns=["index", "title"])
        self.error_logs_df = pd.DataFrame(
            columns=["index", "title", "step", "error_message"]
        )

    def upsert_conference(self):
        session = self.db_manager.get_session()
        conference_repo = ConferenceRepository(session)
        conf = conference_repo.upsert(
            name=self.conference, type=self.category, description=self.description
        )
        self.conference_id = conf.conference_id
        session.close()

    def upsert_instance(self):
        session = self.db_manager.get_session()
        instance_repo = ConferenceInstanceRepository(session)
        instance = instance_repo.upsert(
            conference_id=self.conference_id,
            name=self.conference,
            year=self.year,
            start_date=self.start_date,
            end_date=self.end_date,
            location=self.location,
            website=self.website,
        )
        self.instance_id = instance.instance_id
        session.close()

    def upsert_paper(self):
        # Get a database session from the DBManager
        session = self.db_manager.get_session()
        author_repo = AuthorRepository(session)
        paper_repo = PaperRepository(session)
        keyword_repo = KeywordRepository(session)
        ref_repo = ReferenceRepository(session)

        collection = self.db_manager.get_vdb_collection()
        embedding_repo = EmbeddingRepository(collection)

        metadata = pd.read_csv(self.csv_file_path)

        stage_records = []
        # Iterate through each row in the DataFrame
        for index, row in metadata.iterrows():
            try:
                if index == 50:
                    break

                # Extract data from the row
                # 初始化 Paper 对象并填充基本属性
                # paper_title,author_ids,author_names,venue,research_area,
                # keywords,tldr,abstract,url,pdf_url,attachment_url,pdf_path
                paper_title = row.get("paper_title")
                venue = row.get("venue")
                research_area = row.get("research_area")
                keywords = row.get("keywords")
                tldr = row.get("tldr")
                abstract = row.get("abstract")
                pdf_path = row.get("pdf_path")
                url = row.get("url")
                pdf_url = row.get("pdf_url")
                attachment_url = row.get("attachment_url")

                self.print_start_separator(index=index, title=paper_title)
                stage_records.append("start")

                paper = paper_repo.get_papers(
                    limit=1,
                    offset=None,
                    title=paper_title,
                    instance_id=self.instance_id,
                )
                if paper:
                    logger.warning(
                        f"Found a paper in database with the same title and conference instance. "
                        f"This is not expected, skipping.\nTitle: {paper_title}, Instance ID: {self.instance_id}"
                    )
                    self.write_success(
                        index=index,
                        title=paper_title,
                        message="duplicated with existing db, skipped",
                    )
                    continue

                logger.info(
                    f"this paper is a new paper, processing into the database... titile={paper_title}"
                )

                stage_records.append("Paper instance 初始化完成。下一步处理PDF文件")
                # download the pdf to the directory if can not find it
                if not self.is_valid_pdf_path(pdf_path):
                    pdf_path = self.download_pdf_direct(
                        pdf_title=paper_title, pdf_url=pdf_url
                    )

                stage_records.append("Paper 文件已下载。准备调用PDFAnalyzer")
                # 调用 PDFAnalyzer 提取更多信息
                author_names = (
                    ast.literal_eval(row.get("author_names"))
                    if row.get("author_names")
                    else []
                )
                author_ids = (
                    ast.literal_eval(row.get("author_ids"))
                    if row.get("author_ids")
                    else []
                )
                print(author_ids, author_names)

                keyword_flag = False if row.get("keywords") else True
                reference_flag = False
                author_flag = any(not author_repo.get_author(id) for id in author_ids)

                pdf_analyzer = PDFAnalyzer(
                    title=paper_title,
                    abstract=abstract or "",
                    author_names=author_names,
                    author_ids=author_ids,
                    pdf_path=pdf_path,
                    tldr=tldr or "",
                    keywords=keywords or "",
                    reference_flag=reference_flag,
                    author_flag=author_flag,
                    llm=self.llm,  # 假设 self.llm 是 BaseLLM 实例
                )

                # TODO
                pdf_analyzer.parse_all()
                stage_records.append(
                    "对pdf文件的解析完成，parse_all 完成。准备提取数据"
                )

                # 提取完整文本
                content_raw_text = pdf_analyzer.text
                conclusion = pdf_analyzer.conclusion
                # print(new_paper.content_raw_text[:20])

                # 处理作者信息
                author_dict = pdf_analyzer.authors_augmented_info_dict
                for author, authorid, authorname in zip(
                    author_dict, author_ids, author_names
                ):
                    author_repo.upsert(
                        external_id=authorid,
                        affiliations=author.get("affiliation"),
                        name=author.get("name") or authorname,
                        email=author.get("email", "unknown"),
                        nationality=author.get("nationality", "unknown"),
                    )
                stage_records.append("作者信息提取完成")

                # 处理关键字
                # print(pdf_analyzer.keywords)
                if not keywords:
                    print("keyword not found")
                    for item in pdf_analyzer.keywords:
                        for keyword_name in item.get("keywords", []):
                            keyword_repo.upsert(keyword=keyword_name)

                else:
                    kws = ast.literal_eval(row["keywords"])
                    for kw in kws:
                        keyword_repo.upsert(keyword=kw)

                # 提取abstract, 原来的metadata没有的话
                if not row.get("abstract"):
                    abstract = pdf_analyzer.abstract
                stage_records.append("abstract提取完成")

                # reference 耗时太久了，因此，可以考虑先存储reference 文本
                for reference in pdf_analyzer.references_list:
                    ref_repo.upsert(title=reference)
                stage_records.append("reference 处理完成")

                # 最后提交事务，将paper保存到数据库
                paper = paper_repo.upsert(
                    title=paper_title,
                    instance_id=self.instance_id,
                    year=self.year,
                    external_author_id=author_ids,
                    keywords=kws,
                    venue=venue,
                    research_area=research_area,
                    tldr=tldr,
                    abstract=abstract,
                    conclusion=pdf_analyzer.conclusion,
                    pdf_path=pdf_path,
                    url=url,
                    pdf_url=pdf_url,
                    attachment_url=attachment_url,
                )
                # session.add(new_paper)
                # session.commit()
                stage_records.append("数据库提交处理完成")
                logger.info(
                    f"<<<<<<<<Paper '{paper.title}' inserted successfully with ID: {paper.paper_id}.<<<<<"
                )

                # 向数据库中插入或更新论文
                logger.info(
                    f">>>>>>>insert embedding of Paper '{paper.title}' with ID: {paper.paper_id}.>>>>>>>>"
                )
                embedding_repo.insert_chunks_batch(
                    int(paper.paper_id), pdf_analyzer.embedding_list
                )
                stage_records.append("向量数据库提交处理完成")

                self.write_success(index, paper_title, "all good!")
                self.print_end_separator(index=index, title=paper_title)

            except Exception as e:
                logger.error(
                    f"failed to process pdf file: {index}, {paper_title}, error: {str(e)}"
                )
                self.write_error(
                    index,
                    paper_title,
                    step="\n".join(stage_records),
                    error_message=str(e),
                )
                session.rollback()

        session.close()
        logger.info("!!!!!!!!!     upsert_paper end     !!!!!!!!!.")
        # 在适当的时候调用 flush_logs 一次性写入
        self.flush_logs()

    def parse_title_to_filename(self, title):
        # Remove any non-alphanumeric characters and replace spaces with underscores
        filename = re.sub(r"\W+", "_", title)
        return filename + ".pdf"

    # Function to download a PDF given a URL
    def download_pdf_direct(self, pdf_title, pdf_url):
        try:
            # 验证 pdf_title
            if not isinstance(pdf_title, str) or not pdf_title.strip():
                raise ValueError("PDF title is not valid.")

            pdf_filename = self.parse_title_to_filename(pdf_title)
            pdf_path = os.path.join(self.base_pdf_dir, pdf_filename)

            # Ensure the directory exists; if not, create it
            directory = os.path.dirname(pdf_path)
            if not os.path.exists(directory):
                os.makedirs(directory)
                logger.info(f"Created directory: {directory}")

            if os.path.exists(pdf_path):
                logger.info(f"PDF already exists: {pdf_path}")
                return pdf_path
            else:
                logger.info(f"PDF not found. Downloading to {pdf_path}...")
                # Make a request to the URL
                response = requests.get(pdf_url)
                response.raise_for_status()  # Raise an error for bad responses

                # Save the PDF file locally
                with open(pdf_path, "wb") as file:
                    file.write(response.content)

                print(f"PDF downloaded successfully to {pdf_path}")
                return pdf_path

        except requests.exceptions.RequestException as e:
            print(f"An error occurred while downloading the PDF: {e}")
            return False

    def is_valid_pdf_path(sefl, pdf_path: str) -> bool:
        # 类型和非空检查
        if not isinstance(pdf_path, str) or not pdf_path.strip():
            logger.error("pdf_path must be a non-empty string.")
            return False

        # 清理路径 (去除多余空格)
        pdf_path = pdf_path.strip()

        # 路径合法性检查
        # 检查是否含有非法路径穿越模式
        if ".." in pdf_path or pdf_path.startswith(("/", "\\")):
            logger("pdf_path contains invalid traversal or absolute path.")
            return False

    def write_success(self, index, title, message):
        """写入成功记录（累积在内存中）"""
        new_row = pd.DataFrame([{"index": index, "title": title, "message": message}])
        self.success_logs_df = pd.concat(
            [self.success_logs_df, new_row], ignore_index=True
        )

    def write_error(self, index, title, step, error_message):
        """写入错误记录（累积在内存中）"""
        new_row = pd.DataFrame(
            [
                {
                    "index": index,
                    "title": title,
                    "step": step,
                    "error_message": error_message,
                }
            ]
        )
        self.error_logs_df = pd.concat([self.error_logs_df, new_row], ignore_index=True)

    def flush_logs(self):
        """将所有内存中的记录一次性写入文件"""
        # Ensure the directories for log paths exist
        success_log_dir = os.path.dirname(success_log_path)
        error_log_dir = os.path.dirname(error_log_path)

        if not os.path.exists(success_log_dir):
            os.makedirs(success_log_dir)  # Create the directory if it doesn't exist

        if not os.path.exists(error_log_dir):
            os.makedirs(error_log_dir)  # Create the directory if it doesn't exist

        # Writing the success logs if not empty
        if not self.success_logs_df.empty:
            self.success_logs_df.to_csv(
                success_log_path,
                mode="a",
                header=not pd.io.common.file_exists(success_log_path),
                index=False,
            )

        # Writing the error logs if not empty
        if not self.error_logs_df.empty:
            self.error_logs_df.to_csv(
                error_log_path,
                mode="a",
                header=not pd.io.common.file_exists(error_log_path),
                index=False,
            )

    def print_start_separator(self, index, title):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        separator = (
            "\n" + "=" * 70 + "\n"
            f"🚀 [START PROCESSING] 🚀\n"
            f"📄 Index: {index}\n"
            f'📑 Title: "{title}"\n'
            f"🕒 Timestamp: {timestamp}\n" + "=" * 70
        )
        logger.info(separator)

    def print_end_separator(self, index, title):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        separator = (
            "\n" + "=" * 70 + "\n"
            f"✅ [PROCESS COMPLETED] ✅\n"
            f"📄 Index: {index}\n"
            f'📑 Title: "{title}"\n'
            f"🕒 Finished at: {timestamp}\n" + "=" * 70
        )
        logger.info(separator)

    def run(self):
        logging.info(f"==== Starting New Run at {datetime.now()} ====")
        self.db_manager.create_tables()
        self.upsert_conference()
        self.upsert_instance()
        self.upsert_paper()
        logging.info(f"==== End of Run at {datetime.now()} ====")