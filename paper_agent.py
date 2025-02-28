from collections import defaultdict
import json
import logging
import os
import re
from time import sleep
from markitdown import MarkItDown
from typing import Dict, Optional, Set

from llm.base_llm import BaseLLM
from config import PDFAnalyzerConfig

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class PDFAnalyzer:
    def __init__(
        self,
        title: str,
        abstract: str,
        author_names: list[str],
        author_ids: list[str],
        pdf_path: str,
        tldr: str,
        keywords: list[str],
        reference_flag: bool,
        author_flag: bool,
        llm: BaseLLM,
    ):
        if not isinstance(author_names, list):
            raise TypeError("authors must be a list")
        if not isinstance(llm, BaseLLM):
            raise TypeError("llm must be an instance of BaseLLM")
        if not pdf_path.endswith(".pdf"):
            raise ValueError("pdf_path must be a PDF file")
        # 初始化 PDF 处理器 param pdf_path: PDF 文件路径
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"文件 {pdf_path} 不存在!")
        
        self.title = title
        self.abstract = abstract
        self.author_names = author_names
        self.author_ids = author_ids
        self.pdf_path = pdf_path
        self.tldr = tldr
        self.llm = llm
        self.keywords_flag = not keywords
        self.ref_flag = reference_flag
        self.author_flag = author_flag

        self.text = None
        self.authors_augmented_info_dict = {}
        self.references_list = {}
        self.embedding_list = []
        self.conclusion = None
        self.keywords = {}

        # temp variables
        self.text_lines = []
        self.title_indices = {}

    def parse_all(self) -> None:
        """Parses the PDF document to extract structured information.

        The method performs the following steps:
        1. Extracts text from PDF
        2. Identifies section titles
        3. Splits content into sections
        4. Extracts abstract, authors, conclusion, keywords and references
        5. Generates embeddings for text chunks

        Raises:
            FileNotFoundError: If PDF file doesn't exist
            ValueError: If text extraction fails
        """
        # 1. 提取文本
        logger.info("Extracting text from PDF")
        self.text = self.extract_text(self.pdf_path)
        self.text_lines = self.extract_text_lines(self.text)  # 去除空白行

        # 2. 识别标题行
        logger.info("Detecting section titles")
        self.title_indices = self.get_section_title_indices(self.text_lines)

        # 3. 按标题行分块
        logger.info("Splitting content into sections")
        self.section_lines_dict = self.split_text_lines_by_section_title(
            self.text_lines, self.title_indices
        )

        # 4. 提取摘要, 如果没有摘要标题，就提取前面的文字
        logger.info("Extracting abstract from section, since you did not provide one")
        self.abstract = self.extract_abstract_text_from_paper(self.section_lines_dict)

        # 5. 提取作者信息
        if self.author_flag:
            logger.info("Extracting author information")
            self.authors_augmented_info_dict = self.extract_augmented_authors_info(
                self.llm,
                self.text_lines,
                self.title_indices,
                self.author_names,
                self.author_ids,
            )

        # 6. 提取结论
        logger.info("Extracting conclusion")
        self.conclusion = self.extract_conclusion(self.section_lines_dict)

        # 7. 提取参考文献信息 TODO: references的处理非常耗时，建议分开处理，待优化一下调用关系
        if self.ref_flag:
            logger.info("Extracting references")
            self.references_list = self.extract_formated_references_list(
                self.llm, self.section_lines_dict
            )

        # 8. 提取正文内容,并转化为ebedding
        logger.info("Extracting main text and generating embeddings")
        self.embedding_list = self.embed_main_text(self.llm, self.section_lines_dict)

        # 9. 提取关键词
        if self.keywords_flag:
            logger.info("Extracting keywords")
            self.keywords = self.extract_keywords(
                self.llm, self.section_lines_dict, self.tldr, self.abstract, self.conclusion
            )

    @staticmethod
    def inference_text_by_llm(llm: BaseLLM, prompt: str) -> Optional[Dict]:
        try:
            response = llm.generate_response(prompt=prompt)
            if not response:
                logger.error("Empty response from LLM")
                return None

            cleaned_text = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
            json_match = re.search(r"\{.*\}", cleaned_text, re.DOTALL)

            if not json_match:
                logger.warning("No JSON found in response")
                return None
            # 处理字符串：清理换行符、转义字符，并加上数组括号
            cleaned_data = json_match.group(0)
            cleaned_data = f"[{cleaned_data.strip()}]"
            logger.info(
                f"json response from LLM: {json.dumps(cleaned_data, indent=2, ensure_ascii=False)}"
            )
            return json.loads(cleaned_data)

        except Exception as e:
            logger.error(f"Error in LLM inference: {str(e)}")
            return None

    @staticmethod
    def extract_text_lines(text) -> list[str]:
        return [line.strip() for line in text.split("\n") if line.strip()]  # 去除空白行

    @staticmethod
    def extract_abstract_text_from_paper(section_lines: defaultdict) -> str:
        if "abstract" in section_lines:
            return "\n".join(section_lines["abstract"])
        else:
            return "unable to extract abstract from the paper"

    @staticmethod
    def extract_augmented_authors_info(
        llm: BaseLLM, text_lines, title_indices, author_names, author_ids
    ) -> Dict:
        abstract_index = title_indices.get("abstract")  # 获取 Abstract 标题的索引
        author_context_lines = []
        if abstract_index is not None:
            author_context_lines = text_lines[
                :abstract_index
            ]  # 从文档开头到 Abstract 之前的所有行
            logger.info(f"Extracted author info lines: {author_context_lines}")
        else:
            author_context_lines = text_lines[:10]  # 兜底逻辑，取前10行作为作者信息
            logger.warning(
                f"Unable to find abstract title, using first 10 lines for author info"
            )

        # compose a josn format
        author_json = []
        if not author_names:
            author_names = [""]
        if not author_ids:
            author_ids = [""]
        for author_name, author_id in zip(author_names, author_ids):
            author = {
                "name": author_name,
                "author_ids": author_id,
                "affiliation": None,
                "email": None,
                "nationality": "",
            }
            author_json.append(author)

        augment_author_info = PDFAnalyzer.augment_author_info(
            llm, author_context_lines, author_json
        )
        if augment_author_info:
            return augment_author_info
        
        else:
            logger.warning(
                "unable to get the augmented author info, fall back to the default one"
            )
            return author_json

    @staticmethod
    def extract_conclusion(section_lines_dict: defaultdict) -> str:
        if section_lines_dict.get("conclusion"):
            conclusion_lines = section_lines_dict.get("conclusion")
            return "\n".join(conclusion_lines)
        else:
            logger.warning(f"Unable to find conclusion title, skipping conclusion extraction")
            return None

    @staticmethod
    def extract_formated_references_list(
        llm: BaseLLM, section_lines_dict: defaultdict
    ) -> list[Dict]:
        if section_lines_dict.get("references"):
            reference_lines = section_lines_dict.get("references")
            return PDFAnalyzer.argument_reference(llm, reference_lines)
        else:
            logger.warning(f"Unable to find references title, skipping reference extraction")
            return None

    @staticmethod
    def embed_main_text(llm: BaseLLM, section_chunks: defaultdict) -> list:
        main_text_chunks = PDFAnalyzer.split_all_section_to_chunks(
            section_chunks,
            PDFAnalyzerConfig.MAX_LINE_PER_CHUNK,
            PDFAnalyzerConfig.OVERLAP_LINES,
        )
        embedding_list = []
        for chunk in main_text_chunks:
            embedding_list.append(
                [chunk[0], chunk[1], chunk[2], llm.generate_text_embedding(chunk[2])]
            )
        logger.info(f"the main paper content has been slit into {len(embedding_list)} chunks")
        return embedding_list

    @staticmethod
    def extract_keywords(
        llm: BaseLLM, section_chunks: defaultdict, tldr, abstract, conclusion
    ) -> list:
        keyword_text = ""
        if section_chunks.get("keywords"):
            keyword_text = "\n".join(section_chunks["keywords"])
        else:
            logger.warning(
                f"Unable to find keywords section, skipping keyword extraction. Will try to summarize instead"
            )
        return PDFAnalyzer.argument_keywords(llm, tldr, keyword_text, abstract, conclusion)

    @staticmethod
    def extract_text(pdf_path) -> str:
        """
        Extract text from PDF

        Returns:
            str: Extracted text content

        Raises:
            Exception: If text extraction fails
        """
        try:
            md = MarkItDown()
            result = md.convert(pdf_path)
            logger.info(f"Converted PDF to text: {result.text_content[:100]}\n")

            return result.text_content
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            # Should raise exception instead of returning None since return type is str
            raise e

    @staticmethod
    def split_text_lines_by_section_title(lines, title_indices) -> Dict:
        """按照标题行分块"""
        chunks = defaultdict(list)
        sorted_sections = sorted(title_indices.items(), key=lambda x: x[1])  # 按出现顺序排序

        for idx, (section, start_idx) in enumerate(sorted_sections):
            end_idx = (
                sorted_sections[idx + 1][1] if idx + 1 < len(sorted_sections) else len(lines)
            )
            chunks[section] = lines[start_idx:end_idx]

        return chunks

    @staticmethod
    def get_section_title_indices(lines) -> Dict:
        """检测标题行，返回标题索引"""
        title_indices = {}
        section_num = 0  # 对于 summary、limitation 这类标题，可能在多个位置出现，需要全部保留。加一个编码，保证独立
        for i, line in enumerate(lines):
            clean_line = re.sub(r"[^a-zA-Z\s]", "", line).strip().lower()
            for section, keywords in PDFAnalyzerConfig.SECTION_TITLES.items():
                if any(
                    re.match(
                        rf"^\s*(\d+([\.\-）]\d+)*[\.\-）]*\s*)?{re.escape(kw)}\s*$",
                        clean_line,
                        re.IGNORECASE,
                    )
                    for kw in keywords
                ):
                    if section in title_indices:
                        title_indices[section + "_" + str(section_num)] = i
                        section_num += 1
                        logger.info(f"Detected title: {section} at line {i}")
                    else:
                        title_indices[section] = i
                    break
        return title_indices

    # 提取作者信息
    def augment_author_info(llm: BaseLLM, context, author_json) -> Dict:
        prompt = PDFAnalyzerConfig.AUTHOR_AFFILIATION_PROMPT_TEMPLATE.substitute(
            context=context, author_json=author_json
        )
        return PDFAnalyzer.inference_text_by_llm(llm, prompt)

    @staticmethod
    def split_references_with_overlap(
        reference_lines,
        block_size=PDFAnalyzerConfig.REFERENCE_CHUNK_LINE_SIZE,
        overlap=PDFAnalyzerConfig.REFERENCE_OVERLAP_LINES,
    ):
        # 计算每个参考文献块的开始和结束位置，并在相邻块之间添加重反
        reference_chunks = []
        for i in range(0, len(reference_lines), block_size - overlap):
            chunk = "\n".join(reference_lines[i : i + block_size])
            reference_chunks.append(chunk)
        logger.info(f"Split references into {len(reference_chunks)} chunks")
        for i, chunk in enumerate(reference_chunks[:5]):
            logger.debug(f"Reference chunk {i}: {chunk[:100]}")
        logger.debug(f"Reference chunks: {reference_chunks}")
        return reference_chunks[: PDFAnalyzerConfig.REFERENCE_MAX_CHUNK_SIZE]

    @staticmethod
    def argument_reference(llm: BaseLLM, reference_lines) -> list[Dict]:
        # 拆分reference 章节
        reference_chunk = PDFAnalyzer.split_references_with_overlap(
            reference_lines,
            block_size=PDFAnalyzerConfig.REFERENCE_CHUNK_LINE_SIZE,
            overlap=PDFAnalyzerConfig.REFERENCE_OVERLAP_LINES,
        )
        # 用来存储参考文献的列表
        references_result_list = []
        # 用于去重的字典
        title_set = set()
        # TODO 去掉以下约束，当前reference 推理非常耗时，因此只做前2个chunk， 后续改为离线分析。
        for text in reference_chunk[:2]:
            prompt = PDFAnalyzerConfig.REFERENCES_PROMPT_TEMPLATE.substitute(
                reference_chunk_text=text
            )
            reference_info = PDFAnalyzer.inference_text_by_llm(llm, prompt)
            if reference_info:
                for ref in reference_info:
                    title = ref.get("title")
                    if ref.get("title") and title not in title_set:
                        references_result_list.append(ref)
                        # 将 title 加入去重集合
                        title_set.add(title)
                        logger.info(f"Extracted reference: {ref}")
                    else:
                        logger.warning(f"Duplicate or missing title: {title}")
            else:
                logger.warning(f"unable to reasoning the reference")
        return references_result_list

    @staticmethod
    def split_all_section_to_chunks(
        section_chunks: Dict[str, list[str]],
        max_line_per_chunk: int = 25,
        overlap_lines: int = 5,
    ) -> list[list]:
        if max_line_per_chunk <= 0:
            raise ValueError("max_line_per_chunk must be positive")
        if overlap_lines < 0:
            raise ValueError("overlap_lines cannot be negative")
        if overlap_lines >= max_line_per_chunk:
            raise ValueError("overlap_lines must be less than max_line_per_chunk")
        """
        按 Section 拆分文本，并进行 Chunk 切分，考虑标题标记、最大行数和重叠行数。

        :param section_chunks: dict, 以 section title 为 key，存储对应的文本行
        :param max_line_per_chunk: int, 每个 chunk 最大行数
        :param overlap_lines: int, 允许的上下文重叠行数
        :return: list[str]，每个 chunk 作为字符串存入列表
        """
        text_chunks = []
        chunk_id = 0
        current_chunk = []
        for section_title, content_lines in section_chunks.items():
            if section_title in {
                "authors",
                "acknowledgments",
                "references",
                "appendix",
            }:  # 跳过作者, 感谢，附录和参考文献， 只提取正文，用于RAG
                continue

            current_chunk = []
            for i, line in enumerate(content_lines):
                current_chunk.append(line)

                # 当达到 max_line_per_chunk 时，存储当前 chunk，并留出 overlap
                if len(current_chunk) >= max_line_per_chunk or i == len(content_lines) - 1:
                    text_chunks.append(
                        [chunk_id, section_title, "\n".join(current_chunk).strip()]
                    )
                    chunk_id += 1

                    # 重叠部分：保留最后 overlap_lines 行作为下一个 chunk 的起点
                    current_chunk = current_chunk[-overlap_lines:] if overlap_lines > 0 else []

        # process the last chunk
        if current_chunk:
            text_chunks.append([chunk_id, section_title, "\n".join(current_chunk).strip()])

        logger.info(f"Split text into {len(text_chunks)} chunks")

        return text_chunks

    @staticmethod
    def argument_keywords(
        llm: BaseLLM,
        tldr_text: str,
        initial_keywords: str,
        abstract_text: str,
        conclusion_text: str,
    ) -> list:
        """
        生成关键词列表

        :param text: str, 输入文本
        :return: list[str]，关键词列表
        """
        prompt = PDFAnalyzerConfig.KEYWORDS_PROMPT_TEMPLATE.substitute(
            tldr_text=tldr_text,
            initial_keywords=initial_keywords,
            abstract_text=abstract_text,
            conclusion_text=conclusion_text,
        )
        return PDFAnalyzer.inference_text_by_llm(llm, prompt)
